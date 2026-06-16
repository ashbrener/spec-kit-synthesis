"""adapter_code.py — codebase → CODE-typed FragmentCorpus.

The Phase-2 second source (DESIGN §11.4). Deterministic, stdlib-only, NO LLM —
exactly like the spec adapter, just a different input shape feeding the SAME
source-agnostic core. This is the architectural bet: a new adapter, not a rewrite.

It walks a source tree and emits one Fragment per file plus one per top-level
definition (function/method/class), each with a CODE-typed SourceRef whose
locator is `relpath#symbol`. The core never learns it is "code" — it is just
more fragments with `type=code`, so the verify gate, reconcile, and render all
work unchanged.

Granularity is intentionally coarse and language-light: a small set of
definition patterns covers the common cases (shell functions, Python def/class,
JS/TS function/class/const-arrow). Unknown languages still yield file-level
fragments, so the adapter degrades gracefully rather than failing.

Usage:
    uv run python skill/scripts/adapter_code.py <src_dir> [--project-name NAME] \
        [--include EXT[,EXT...]] [--out corpus.json]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

from schema import Fragment, FragmentCorpus, SourceRef, SourceType

# Default source extensions to walk. Extend via --include.
DEFAULT_EXTS = {".sh", ".bash", ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rb", ".rs"}

# Directories never worth walking.
SKIP_DIRS = {"node_modules", "venv", "__pycache__", "dist", "build"}


def _is_skipped(rel_parts, extra: set[str] = frozenset()) -> bool:
    """Skip any path with a HIDDEN part (.git, .venv, .specify, .project-arc, .claude, … — all
    dot-dirs, present and future) or a part in SKIP_DIRS / the caller's extra excludes. This keeps
    vendored extension runtimes, scaffolding, and tooling trees out of the product corpus."""
    return any(part.startswith(".") or part in SKIP_DIRS or part in extra for part in rel_parts)

# Language → ordered (regex, group) patterns for top-level definitions. The
# regex must match at column 0 (top-level) to keep it to genuine definitions.
DEF_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "sh": [re.compile(r"^([A-Za-z_][A-Za-z0-9_:]*)\s*\(\)\s*\{"),          # name() {
           re.compile(r"^function\s+([A-Za-z_][A-Za-z0-9_:]*)")],          # function name
    "py": [re.compile(r"^(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)"),
           re.compile(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)")],
    "js": [re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"),
           re.compile(r"^(?:export\s+)?class\s+([A-Za-z_$][\w$]*)"),
           re.compile(r"^(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(")],
}
LANG_BY_EXT = {".sh": "sh", ".bash": "sh", ".py": "py",
               ".js": "js", ".ts": "js", ".jsx": "js", ".tsx": "js"}


def _defs_for(lang: str) -> list[re.Pattern[str]]:
    return DEF_PATTERNS.get(lang, [])


def _fragment_file(rel: str, text: str) -> Fragment:
    ref = SourceRef(type=SourceType.CODE, name=f"code · {rel}", locator=rel, anchor=None)
    return Fragment(id=rel, source=ref, kind="code", feature_key=rel.split("/")[0], text=text)


def _fragment_symbol(rel: str, symbol: str, body: str) -> Fragment:
    loc = f"{rel}#{symbol}"
    ref = SourceRef(type=SourceType.CODE, name=f"code · {rel} · {symbol}", locator=loc, anchor=symbol)
    return Fragment(id=loc, source=ref, kind="code-symbol", feature_key=rel.split("/")[0], text=body)


def fragments_for_file(path: Path, rel: str) -> list[Fragment]:
    text = path.read_text(encoding="utf-8", errors="replace")
    out: list[Fragment] = [_fragment_file(rel, text)]
    lang = LANG_BY_EXT.get(path.suffix.lower(), "")
    pats = _defs_for(lang)
    if not pats:
        return out  # graceful: file-level only for unknown languages
    lines = text.splitlines()
    # Find each top-level definition line, then slice body until the next one.
    hits: list[tuple[int, str]] = []
    seen: dict[str, int] = {}
    for i, line in enumerate(lines):
        for pat in pats:
            m = pat.match(line)
            if m:
                name = m.group(1)
                seen[name] = seen.get(name, 0) + 1
                if seen[name] > 1:
                    name = f"{name}-{seen[name]}"   # deterministic disambiguation
                hits.append((i, name))
                break
    for idx, (start, name) in enumerate(hits):
        end = hits[idx + 1][0] if idx + 1 < len(hits) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        if body:
            out.append(_fragment_symbol(rel, name, body))
    return out


def build_corpus(src_dir: Path, project_name: Optional[str], exts: set[str],
                 exclude: set[str] = frozenset()) -> FragmentCorpus:
    files: list[Path] = []
    for p in sorted(src_dir.rglob("*")):
        if not p.is_file():
            continue
        if _is_skipped(p.relative_to(src_dir).parts, exclude):
            continue
        if p.suffix.lower() in exts:
            files.append(p)
    frags: list[Fragment] = []
    for p in files:
        rel = p.relative_to(src_dir).as_posix()
        frags.extend(fragments_for_file(p, rel))
    return FragmentCorpus(
        project_name=project_name or src_dir.resolve().name,
        fragments=frags,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Walk a codebase into a CODE-typed FragmentCorpus.")
    parser.add_argument("src_dir", help="Path to the source tree to adapt.")
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--include", default=None, help="Comma-separated extensions (e.g. sh,py) to override defaults.")
    parser.add_argument("--exclude", default=None, help="Comma-separated extra dir names to skip (hidden dot-dirs are always skipped).")
    parser.add_argument("--out", default=None, help="Write JSON here (default: stdout).")
    args = parser.parse_args(argv)

    src = Path(args.src_dir)
    if not src.is_dir():
        print(f"adapter_code: not a directory: {src}", file=sys.stderr)
        return 2
    exts = ({"." + e.lstrip(".").lower() for e in args.include.split(",")}
            if args.include else DEFAULT_EXTS)
    exclude = {e.strip() for e in args.exclude.split(",")} if args.exclude else frozenset()
    corpus = build_corpus(src, args.project_name, exts, exclude=exclude)
    payload = corpus.model_dump_json(indent=2)
    if args.out:
        Path(args.out).write_text(payload)
        n_files = sum(1 for f in corpus.fragments if f.kind == "code")
        n_sym = sum(1 for f in corpus.fragments if f.kind == "code-symbol")
        print(f"wrote {len(corpus.fragments)} fragments ({n_files} files, {n_sym} symbols) → {args.out}",
              file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
