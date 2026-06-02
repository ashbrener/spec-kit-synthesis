"""design-doc / ADR input adapter — free-form markdown → DESIGN_DOC FragmentCorpus.

The Phase-3 third source (DESIGN §11.4), proving the source-agnostic seam once
more: a design doc or ADR is a new ADAPTER, not a rewrite. Deterministic,
stdlib-only, NO LLM — exactly like the spec and code adapters, just another
input shape feeding the SAME source-agnostic core. The core never learns it is
a "design doc"; it is just more fragments with `type=design_doc`, so the verify
gate, reconcile, and render all work unchanged.

It walks a docs tree of free-form markdown (architecture notes, RFCs, ADRs),
splits each file into one fragment per top-level/`##` section (preamble before
the first heading is its own fragment; small/headingless files stay whole), and
emits a validated FragmentCorpus. Ids are stable, deterministic `relpath#slug`
keys (duplicate headings within a file get `-2`, `-3`, …).

`kind` is "design-doc", or "adr" when the path/filename looks like an
architecture-decision record (under an `adr`/`decisions/` dir, or an
`NNNN-*.md` ADR-style name). The SourceRef chip label mirrors the kind:
`doc · <relpath>` or `adr · <relpath>`.

CLI:
    uv run python skill/scripts/adapter_doc.py <docs_dir> \
        [--project-name NAME] [--include EXT[,EXT]] [--out corpus.json]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

# schema.py lives alongside this script; make it importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from schema import (  # noqa: E402  (path shim must precede import)
    Fragment,
    FragmentCorpus,
    SourceRef,
    SourceType,
)

# Default doc extensions to walk. Extend/override via --include.
DEFAULT_EXTS = {".md", ".markdown"}

# Directories never worth walking (mirrors adapter_code.SKIP_DIRS).
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", ".synthesis", ".claude",
}

# ── ADR detection (deterministic, path-based) ───────────────────────────────
# A doc is an ADR if any path part names an ADR location, or the filename is an
# ADR-style numbered record (e.g. 0001-use-uv.md, ADR-007-foo.md).
_ADR_DIR_PARTS = {"adr", "adrs", "decisions", "decision-records"}
_ADR_FILENAME_RE = re.compile(r"^(?:adr[-_])?\d{3,4}[-_].+", re.IGNORECASE)


def _slugify(text: str) -> str:
    """Deterministic, URL-safe slug for a heading → fragment-id anchor."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "section"


def _is_adr(rel: str) -> bool:
    """Classify a doc as an ADR by its path/filename (deterministic)."""
    parts = rel.split("/")
    if any(part.lower() in _ADR_DIR_PARTS for part in parts[:-1]):
        return True
    return bool(_ADR_FILENAME_RE.match(parts[-1]))


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) chunks by top-level/`##` headings.

    Mirrors adapter_speckit._split_sections: an H1 (`# `) or H2 (`## `) at
    column 0 is a section boundary; content before the first heading becomes a
    leading "preamble" chunk; deeper headings (### …) stay inside their parent.
    `section_text` includes the heading line so fragments are self-describing.
    Headingless/empty files return a single ("section", text) chunk (or none).
    """
    lines = text.splitlines()
    heading_re = re.compile(r"^(#{1,2})\s+(.*)$")

    chunks: list[tuple[str, list[str]]] = []
    current_heading: Optional[str] = None
    current_lines: list[str] = []

    def _flush() -> None:
        if current_lines and any(ln.strip() for ln in current_lines):
            chunks.append((current_heading or "preamble", current_lines.copy()))

    for line in lines:
        m = heading_re.match(line)
        if m:
            _flush()
            raw = m.group(2).strip()
            # strip a trailing markdown decoration like *(mandatory)* from the heading
            heading = re.sub(r"\s*\*\([^)]*\)\*\s*$", "", raw).strip() or raw
            current_heading = heading
            current_lines = [line]
        else:
            current_lines.append(line)
    _flush()

    if not chunks:  # no qualifying headings, or empty
        body = text.strip()
        return [("section", text)] if body else []
    return [(h, "\n".join(ls).strip()) for h, ls in chunks]


def _feature_key(rel: str) -> str:
    """Source-internal grouping key: top-level dir, else the filename stem."""
    parts = rel.split("/")
    if len(parts) > 1:
        return parts[0]
    return Path(parts[-1]).stem


def _fragments_for_file(rel: str, text: str) -> list[Fragment]:
    is_adr = _is_adr(rel)
    kind = "adr" if is_adr else "design-doc"
    chip = "adr" if is_adr else "doc"
    feature_key = _feature_key(rel)

    sections = _split_sections(text)
    single = len(sections) <= 1  # keep small/whole/headingless files as one fragment

    frags: list[Fragment] = []
    seen_slugs: dict[str, int] = {}
    for heading, body in sections:
        if single:
            anchor = heading if heading not in ("preamble", "section") else None
            locator = rel
        else:
            slug = _slugify(heading)
            # disambiguate duplicate headings within one file deterministically
            n = seen_slugs.get(slug, 0)
            seen_slugs[slug] = n + 1
            slug_final = slug if n == 0 else f"{slug}-{n + 1}"
            anchor = heading
            locator = f"{rel}#{slug_final}"

        source = SourceRef(
            type=SourceType.DESIGN_DOC,
            name=f"{chip} · {rel}",
            locator=locator,
            anchor=anchor,
        )
        frags.append(
            Fragment(
                id=locator,
                source=source,
                kind=kind,
                feature_key=feature_key,
                text=body,
            )
        )
    return frags


def build_corpus(
    docs_dir: Path, project_name: Optional[str] = None, exts: Optional[set[str]] = None
) -> FragmentCorpus:
    """Walk `<docs_dir>` and build a validated DESIGN_DOC FragmentCorpus."""
    docs_dir = docs_dir.resolve()
    if not docs_dir.is_dir():
        raise NotADirectoryError(f"docs dir not found: {docs_dir}")
    exts = exts or DEFAULT_EXTS

    files: list[Path] = []
    for p in sorted(docs_dir.rglob("*")):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.relative_to(docs_dir).parts):
            continue
        if p.suffix.lower() in exts:
            files.append(p)

    # deterministic order across the whole tree, then stable within each file.
    files.sort(key=lambda p: p.relative_to(docs_dir).as_posix())

    frags: list[Fragment] = []
    for p in files:
        rel = p.relative_to(docs_dir).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace")
        frags.extend(_fragments_for_file(rel, text))

    return FragmentCorpus(
        project_name=project_name or docs_dir.name,
        fragments=frags,
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Walk a docs tree of free-form design docs / ADRs into a DESIGN_DOC FragmentCorpus.",
    )
    parser.add_argument("docs_dir", help="Path to the docs directory of markdown design docs / ADRs.")
    parser.add_argument("--project-name", default=None, help="Display name for the FragmentCorpus.")
    parser.add_argument("--include", default=None, help="Comma-separated extensions (e.g. md,markdown) to override defaults.")
    parser.add_argument("--out", default=None, help="Write JSON here (default: stdout).")
    args = parser.parse_args(argv)

    docs = Path(args.docs_dir)
    if not docs.is_dir():
        print(f"adapter_doc: not a directory: {docs}", file=sys.stderr)
        return 2
    exts = (
        {"." + e.lstrip(".").lower() for e in args.include.split(",")}
        if args.include
        else DEFAULT_EXTS
    )
    corpus = build_corpus(docs, args.project_name, exts)
    payload = corpus.model_dump_json(indent=2)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
        n_doc = sum(1 for f in corpus.fragments if f.kind == "design-doc")
        n_adr = sum(1 for f in corpus.fragments if f.kind == "adr")
        print(
            f"wrote {len(corpus.fragments)} fragments ({n_doc} design-doc, {n_adr} adr) → {args.out}",
            file=sys.stderr,
        )
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
