#!/usr/bin/env python3
"""Detect a host project's design tokens and emit a `atlas.theme.json`.

The output is a *flat* JSON dict of {token: value} using a SUBSET of the keys in
``render.DEFAULT_THEME`` — exactly the ``--theme`` format that the existing
renderer accepts. ``render.py`` merges it over its defaults, so a *partial*
detection is always safe: any token we don't detect inherits the default.

Detection is deliberately **fail-soft** (DESIGN.md §6 / §9.6): theming is
cosmetic and strictly downstream of atlas. "Always-correct beats
subtly-wrong" — so we only emit a token when the host source name *clearly*
corresponds, we surface low-confidence guesses as a WARNING on stderr for a
human to review, and if nothing usable is found we emit ``{}`` (the renderer
then uses pure defaults).

No LLM. stdlib only. Deterministic: identical input → identical output.

Usage::

    uv run python skill/scripts/theme_detect.py <project_dir> [--out atlas.theme.json]

Source priority (stop at the first that yields a usable palette):
  1. CSS custom properties — ``:root { --name: value; }`` across ``*.css``
  2. Tailwind config — ``theme.extend.colors`` / ``theme.colors`` (regex-level)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# render.py lives next to this file; ensure it's importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from render import DEFAULT_THEME  # noqa: E402  (after sys.path tweak)

# The only token keys we are allowed to emit (a subset of DEFAULT_THEME).
ALLOWED_TOKENS = set(DEFAULT_THEME.keys())

# Files to ignore entirely when scanning (vendored / generated trees).
_SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "out", ".next", ".cache",
    "vendor", "coverage", "__pycache__", ".venv", "venv",
}

# ── value validation ──────────────────────────────────────────────────────────

# Recognise the value shapes we are willing to map to a colour token.
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_FUNC_COLOR_RE = re.compile(
    r"^(?:rgb|rgba|hsl|hsla|oklch|oklab|lab|lch|color)\([^()]*\)$",
    re.IGNORECASE,
)
_NAMED_COLORS = {
    "black", "white", "transparent", "currentcolor", "red", "green", "blue",
    "gray", "grey", "orange", "yellow", "purple", "teal", "pink", "brown",
    "navy", "maroon", "olive", "lime", "aqua", "fuchsia", "silver",
}


def _is_color_value(value: str) -> bool:
    v = value.strip()
    if not v:
        return False
    if _HEX_RE.match(v):
        return True
    if _FUNC_COLOR_RE.match(v):
        return True
    if v.lower() in _NAMED_COLORS:
        return True
    return False


def _looks_like_font_stack(value: str) -> bool:
    v = value.strip()
    if not v or _is_color_value(v):
        return False
    # A font-family declaration: words/quoted names, commas, common keywords.
    return bool(re.search(r"(serif|sans-serif|monospace|system-ui|[A-Za-z][A-Za-z ]{2,})", v))


# ── semantic name → token mapping ─────────────────────────────────────────────
#
# Each entry: (compiled regex over a *normalised* source name, target token,
# high_confidence). Normalisation strips a leading "--", lowercases, and turns
# any run of non-alphanumerics into a single "-". Order matters: the first
# matching rule wins, so put the most specific patterns first.

def _normalise_name(name: str) -> str:
    n = name.strip().lstrip("-").lower()
    n = re.sub(r"[^a-z0-9]+", "-", n).strip("-")
    return n


# (regex, token, high_confidence)
# Targets the editorial design-system token vocabulary (renderer v2, spec 001):
#   accent → gold, surfaces → paper/paper-2, text → ink, borders → line/line-dk,
#   semantic hues → red/green/blue. (No ink-2/-3, plum/ochre/teal, accent-soft.)
_COLOR_RULES: list[tuple[re.Pattern[str], str, bool]] = [
    # accent / brand → gold — high confidence
    (re.compile(r"^(primary|accent|brand)(-(color|colour|default|500|600|main|base))?$"), "gold", True),
    (re.compile(r"^(primary|accent|brand)-(dark|700|800|900|d|hover|active|bright|light)$"), "gold-bright", True),
    # background / surface → paper
    (re.compile(r"^(background|bg|surface|paper|canvas|base)(-(color|colour|default|primary|0|50|100))?$"), "paper", True),
    (re.compile(r"^(background|bg|surface)-(2|secondary|alt|subtle|muted|raised)$"), "paper-2", False),
    # foreground / text / ink
    (re.compile(r"^(foreground|fg|text|ink|content|copy|body)(-(color|colour|default|primary|900|base))?$"), "ink", True),
    # borders / dividers → line
    (re.compile(r"^(border|hairline|hair|divider|rule|outline|stroke)(-(color|colour|default|primary))?$"), "line", True),
    (re.compile(r"^(border|divider)-(2|strong|dark|secondary)$"), "line-dk", False),
    # semantic hues (best-effort, low confidence)
    (re.compile(r"^(danger|error|destructive|red)$"), "red", False),
    (re.compile(r"^(success|green)$"), "green", False),
    (re.compile(r"^(info|blue)$"), "blue", False),
    (re.compile(r"^(warning|amber|ochre)$"), "gold-bright", False),
]

# Font-family source names → token. (regex, token, high_confidence)
_FONT_RULES: list[tuple[re.Pattern[str], str, bool]] = [
    (re.compile(r"(mono|code|tt)"), "font-mono", True),
    (re.compile(r"(serif|display|heading|head|title)"), "font-display", False),
    (re.compile(r"(sans|body|base|text|default|ui)"), "font-body", True),
    (re.compile(r"(font|family|type|typeface)"), "font-body", False),
]


def _map_color_name(norm: str) -> tuple[str, bool] | None:
    for rx, token, high in _COLOR_RULES:
        if rx.match(norm):
            return token, high
    return None


def _map_font_name(norm: str) -> tuple[str, bool] | None:
    for rx, token, high in _FONT_RULES:
        if rx.search(norm):
            return token, high
    return None


# ── detection result plumbing ─────────────────────────────────────────────────

class Detection:
    """Accumulates token assignments with confidence + provenance for reporting."""

    def __init__(self) -> None:
        # token -> (value, high_confidence, source_name)
        self._tokens: dict[str, tuple[str, bool, str]] = {}

    def add(self, token: str, value: str, high: bool, source_name: str) -> None:
        if token not in ALLOWED_TOKENS:
            return
        if not isinstance(value, str) or not value.strip():
            return
        existing = self._tokens.get(token)
        # Prefer a high-confidence assignment over a low-confidence one; once a
        # token has any assignment, keep the first (deterministic, scan-order)
        # unless we can upgrade its confidence.
        if existing is not None:
            _, existing_high, _ = existing
            if existing_high or not high:
                return
        self._tokens[token] = (value.strip(), high, source_name)

    def __bool__(self) -> bool:
        return bool(self._tokens)

    def theme(self) -> dict[str, str]:
        return {tok: val for tok, (val, _high, _src) in sorted(self._tokens.items())}

    def high_confidence_tokens(self) -> list[str]:
        return sorted(t for t, (_v, high, _s) in self._tokens.items() if high)

    def low_confidence(self) -> list[tuple[str, str, str]]:
        """(token, value, source_name) for low-confidence guesses, sorted."""
        return sorted(
            (t, v, s) for t, (v, high, s) in self._tokens.items() if not high
        )

    def has_palette(self) -> bool:
        """A 'usable palette' = at least one core color token was detected."""
        core = {"paper", "ink", "gold"}
        return any(t in self._tokens for t in core)


# ── file discovery ────────────────────────────────────────────────────────────

def _iter_files(root: Path, *, suffixes: tuple[str, ...], names: tuple[str, ...] = ()):
    """Yield matching files under root, skipping vendored/generated dirs.

    Results are sorted (shallowest first, then lexicographically) for
    determinism.
    """
    matches: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.relative_to(root).parts[:-1])
        if parts & _SKIP_DIRS:
            continue
        if path.suffix.lower() in suffixes or path.name in names:
            matches.append(path)
    matches.sort(key=lambda p: (len(p.relative_to(root).parts), str(p).lower()))
    return matches


# ── source 1: CSS custom properties ───────────────────────────────────────────

# Match `:root { ... }` (and similar top-level token blocks). We grab the body
# and then pull `--name: value;` declarations from it.
_ROOT_BLOCK_RE = re.compile(
    r"(?::root|:where\(:root\)|\[data-theme[^\]]*\]|html)\s*\{([^{}]*)\}",
    re.IGNORECASE | re.DOTALL,
)
_DECL_RE = re.compile(r"--([A-Za-z0-9-_]+)\s*:\s*([^;]+);")
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_css_comments(text: str) -> str:
    return _COMMENT_RE.sub(" ", text)


def detect_from_css(root: Path) -> Detection | None:
    det = Detection()
    found_any_var = False
    for css in _iter_files(root, suffixes=(".css",)):
        try:
            text = _strip_css_comments(css.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        # Collect declarations from :root-like blocks (deterministic order).
        for block in _ROOT_BLOCK_RE.findall(text):
            for raw_name, raw_value in _DECL_RE.findall(block):
                found_any_var = True
                value = raw_value.strip()
                # Skip values that just reference another var — we can't resolve.
                if value.startswith("var("):
                    continue
                norm = _normalise_name(raw_name)
                color_hit = _map_color_name(norm)
                if color_hit and _is_color_value(value):
                    token, high = color_hit
                    det.add(token, value, high, f"--{raw_name}")
                    continue
                font_hit = _map_font_name(norm)
                if font_hit and _looks_like_font_stack(value):
                    token, high = font_hit
                    det.add(token, value, high, f"--{raw_name}")
    if det.has_palette():
        return det
    return det if (det and found_any_var) else None


# ── source 2: Tailwind config ─────────────────────────────────────────────────

# Extract the `colors: { ... }` object body (handles nested braces) from a
# `theme.extend.colors` or `theme.colors` region. We do NOT execute JS.
_COLORS_KEY_RE = re.compile(r"\bcolors\s*:\s*\{", re.IGNORECASE)
# string color literal: 'value' or "value"
_STR = r"""['"]([^'"]+)['"]"""
# `key: 'value'`  where key may be quoted or bare
_KV_STR_RE = re.compile(
    rf"""['"]?([A-Za-z0-9_-]+)['"]?\s*:\s*{_STR}""",
)
# `key: { ... }` nested scale (e.g. primary: { DEFAULT: '#..', 500: '#..' })
_KV_OBJ_RE = re.compile(r"""['"]?([A-Za-z0-9_-]+)['"]?\s*:\s*\{""")

_FONT_KEY_RE = re.compile(r"\bfontFamily\s*:\s*\{", re.IGNORECASE)


def _extract_balanced_object(text: str, open_brace_index: int) -> str:
    """Return the substring inside the braces starting at open_brace_index ('{')."""
    depth = 0
    start = open_brace_index
    for i in range(open_brace_index, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
            if depth == 1:
                start = i + 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
    return text[start:]


def _scale_pick(body: str) -> str | None:
    """From a nested color-scale body, pick the most representative value.

    Prefers DEFAULT, then 500/600 (typical brand mid-tone), else first literal.
    """
    pairs = _KV_STR_RE.findall(body)
    if not pairs:
        return None
    table = {k.lower(): v for k, v in pairs}
    for key in ("default", "500", "600", "400", "700"):
        if key in table and _is_color_value(table[key]):
            return table[key]
    for _k, v in pairs:
        if _is_color_value(v):
            return v
    return None


def detect_from_tailwind(root: Path) -> Detection | None:
    configs = _iter_files(
        root,
        suffixes=(),
        names=(
            "tailwind.config.js", "tailwind.config.ts",
            "tailwind.config.cjs", "tailwind.config.mjs",
        ),
    )
    if not configs:
        return None
    det = Detection()
    for cfg in configs:
        try:
            text = cfg.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        text = _strip_css_comments(text)
        # Find each `colors: {` and extract its balanced body.
        for m in _COLORS_KEY_RE.finditer(text):
            body = _extract_balanced_object(text, text.index("{", m.start()))
            _ingest_tailwind_colors(body, det)
        for m in _FONT_KEY_RE.finditer(text):
            body = _extract_balanced_object(text, text.index("{", m.start()))
            _ingest_tailwind_fonts(body, det)
    if det.has_palette():
        return det
    return det if det else None


def _ingest_tailwind_colors(body: str, det: Detection) -> None:
    # First: nested scale objects (primary: { ... }).
    for m in _KV_OBJ_RE.finditer(body):
        key = m.group(1)
        norm = _normalise_name(key)
        hit = _map_color_name(norm)
        if not hit:
            continue
        nested = _extract_balanced_object(body, body.index("{", m.start()))
        value = _scale_pick(nested)
        if value:
            token, high = hit
            det.add(token, value, high, f"colors.{key}")
    # Then: flat string literals (primary: '#..').
    for key, value in _KV_STR_RE.findall(body):
        norm = _normalise_name(key)
        hit = _map_color_name(norm)
        if hit and _is_color_value(value):
            token, high = hit
            det.add(token, value, high, f"colors.{key}")


def _ingest_tailwind_fonts(body: str, det: Detection) -> None:
    # fontFamily values are typically arrays: sans: ['Inter', 'sans-serif']
    for m in re.finditer(r"""['"]?([A-Za-z0-9_-]+)['"]?\s*:\s*\[([^\]]*)\]""", body):
        key, arr = m.group(1), m.group(2)
        fonts = re.findall(_STR, arr)
        if not fonts:
            continue
        stack = ", ".join(fonts)
        hit = _map_font_name(_normalise_name(key))
        if hit and _looks_like_font_stack(stack):
            token, high = hit
            det.add(token, stack, high, f"fontFamily.{key}")


# ── orchestration ─────────────────────────────────────────────────────────────

# (label, fn) in priority order.
_SOURCES = [
    ("CSS custom properties", detect_from_css),
    ("Tailwind config", detect_from_tailwind),
]


def detect_theme(project_dir: Path) -> tuple[dict[str, str], str | None, Detection | None]:
    """Return (theme_dict, source_label_or_None, detection_or_None).

    Stops at the first source that yields a usable palette.
    """
    for label, fn in _SOURCES:
        det = fn(project_dir)
        if det and det.has_palette():
            return det.theme(), label, det
    return {}, None, None


def _report(source: str | None, det: Detection | None, theme: dict[str, str]) -> None:
    """Write a short human-readable report to stderr."""
    if not theme or det is None or source is None:
        print(
            "theme_detect: no usable design tokens found — emitting {} "
            "(renderer will use pure defaults).",
            file=sys.stderr,
        )
        return
    print(f"theme_detect: source = {source}", file=sys.stderr)
    high = det.high_confidence_tokens()
    if high:
        print(
            "theme_detect: mapped (confident): "
            + ", ".join(f"{t}={theme[t]}" for t in high),
            file=sys.stderr,
        )
    low = det.low_confidence()
    if low:
        details = ", ".join(f"{t}={v} (from {src})" for t, v, src in low)
        print(
            f"WARNING: theme_detect low-confidence guesses — please review: {details}",
            file=sys.stderr,
        )


def _validate_loadable(theme: dict[str, str]) -> None:
    """Confirm render.py would accept the output: a flat str→str dict that
    merges cleanly over DEFAULT_THEME."""
    text = json.dumps(theme)
    loaded = json.loads(text)
    assert isinstance(loaded, dict), "output must be a JSON object"
    merged = {**DEFAULT_THEME, **loaded}
    for k, v in merged.items():
        assert isinstance(k, str) and isinstance(v, str), (
            f"merged theme must be flat str->str; offender: {k!r}={v!r}"
        )


def run(project_dir: Path) -> tuple[dict[str, str], str | None, Detection | None]:
    theme, source, det = detect_theme(project_dir)
    _validate_loadable(theme)
    return theme, source, det


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Detect a host project's design tokens and emit a flat "
            "atlas.theme.json consumable by render.py --theme."
        )
    )
    parser.add_argument("project_dir", help="Path to the host project to scan.")
    parser.add_argument(
        "--out",
        help="Write the theme JSON here (default: stdout).",
    )
    args = parser.parse_args(argv)

    project_dir = Path(args.project_dir)
    if not project_dir.is_dir():
        parser.error(f"project_dir is not a directory: {project_dir}")

    theme, source, det = run(project_dir)
    _report(source, det, theme)

    out_text = json.dumps(theme, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(out_text, encoding="utf-8")
    else:
        sys.stdout.write(out_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
