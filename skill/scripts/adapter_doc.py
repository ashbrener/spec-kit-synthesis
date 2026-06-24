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
SKIP_DIRS = {"node_modules", "venv", "__pycache__", "dist", "build"}

# Non-source-of-truth residue (spec 010, R3): archives + repo/agent/process meta are not the
# documented system, so they never become fragments/clusters. Dir match is a substring (catches
# `99_Archive`, `_Audits`, `archive/`); file match is the basename or a `handoff` substring.
_SKIP_DIR_SUBSTR = ("archive", "audit")
_SKIP_META_FILES = {"claude.md", "agents.md", "gemini.md", "copilot-instructions.md",
                    "resume.md", "worktrees.md"}


def _is_skipped(rel: str, extra=frozenset()) -> bool:
    """Skip any path with a HIDDEN part (.git, .venv, .specify, .project-arc, .claude, … — all
    dot-dirs) or a part in SKIP_DIRS, plus the caller's `extra` excludes. An `extra` entry containing
    `/` is a PATH-PREFIX (skip exactly that subtree, spec 007); a bare name matches a path part. Lets a
    source repo's narrative pass skip its specs_dir/adr_dir subtrees (no double-ingest). Also drops
    non-source residue — archive/audit dirs and repo/agent/process meta files (spec 010, R3)."""
    parts = rel.split("/")
    if any(part.startswith(".") or part in SKIP_DIRS for part in parts):
        return True
    low = [p.lower() for p in parts]
    if any(sub in part for part in low[:-1] for sub in _SKIP_DIR_SUBSTR):
        return True                                  # archive/audit directory at any depth
    base = low[-1]
    if base in _SKIP_META_FILES or "handoff" in base:
        return True                                  # repo/agent/process meta file
    for e in extra:
        if "/" in e:
            e = e.rstrip("/")
            if rel == e or rel.startswith(e + "/"):
                return True
        elif e in parts:
            return True
    return False

# ── ADR detection (deterministic, path-based) ───────────────────────────────
# A doc is an ADR if any path part names an ADR location, or the filename is an
# ADR-style numbered record. Two filename shapes are recognised (FR-008):
#   * plain numbered:   0001-use-uv.md, ADR-007-foo.md
#   * governed/namespaced: CORE-ADR-002-event-bus.md, PLAT-ADR-014-thing.md
_ADR_DIR_PARTS = {"adr", "adrs", "decisions", "decision-records"}
_ADR_FILENAME_RE = re.compile(
    r"^(?:[a-z0-9]+[-_])?adr[-_]\d{1,4}[-_].+|^\d{3,4}[-_].+",
    re.IGNORECASE,
)
# Pull a stable ADR id (e.g. 'ADR-005', 'CORE-ADR-002', '0001') out of a filename.
_ADR_ID_RE = re.compile(
    r"^(?P<id>(?:[a-z0-9]+-)?adr-\d{1,4}|\d{3,4})", re.IGNORECASE
)


def _slugify(text: str) -> str:
    """Deterministic, URL-safe slug for a heading → fragment-id anchor."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "section"


def _is_adr(rel: str, adr_root: Optional[str] = None) -> bool:
    """Classify a doc as an ADR by its path/filename (deterministic).

    When `adr_root` is set (a caller-declared ADR directory, e.g. a repo's
    `adr_dir`), every doc at or below it is an ADR regardless of filename shape.
    """
    if adr_root is not None:
        if adr_root in ("", "."):  # the entire walked root is the ADR dir → every doc is an ADR
            return True
        if rel == adr_root or rel.startswith(adr_root + "/"):
            return True
    parts = rel.split("/")
    if any(part.lower() in _ADR_DIR_PARTS for part in parts[:-1]):
        return True
    return bool(_ADR_FILENAME_RE.match(parts[-1]))


def _adr_id(rel: str) -> Optional[str]:
    """Extract a stable ADR id from a filename for use as the feature_key.

    Normalises the matched id to upper-case ('CORE-ADR-002', 'ADR-005'); a bare
    numbered record ('0001-use-uv.md') yields its number ('0001'). Returns None
    when the filename carries no recognisable id (e.g. a README in an adr dir)."""
    m = _ADR_ID_RE.match(Path(rel).name)
    return m.group("id").upper() if m else None


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


def _fragments_for_file(rel: str, text: str, adr_root: Optional[str] = None) -> list[Fragment]:
    is_adr = _is_adr(rel, adr_root)
    kind = "adr" if is_adr else "design-doc"
    chip = "adr" if is_adr else "doc"
    # An ADR groups under its own id (ADR-005 / CORE-ADR-002 — FR-008) when the
    # filename carries one; otherwise it falls back to the dir/stem grouping.
    feature_key = (_adr_id(rel) if is_adr else None) or _feature_key(rel)

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
            type=SourceType.ADR if is_adr else SourceType.DESIGN_DOC,
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
    docs_dir: Path,
    project_name: Optional[str] = None,
    exts: Optional[set[str]] = None,
    adr_dir: Optional[Path] = None,
    exclude: set[str] = frozenset(),
) -> FragmentCorpus:
    """Walk `<docs_dir>` and build a validated DESIGN_DOC FragmentCorpus.

    `adr_dir` (a repo's declared `adr_dir`, e.g. ``docs/adr`` or
    ``02_System_Architecture/ADRs``) forces every markdown doc at or below it to
    `kind="adr"` regardless of filename shape (FR-008). It may be absolute or
    relative to `docs_dir`; if it lies outside the walked tree the docs there are
    still ingested, so a repo whose ADRs live outside its docs tree is reachable.
    """
    docs_dir = docs_dir.resolve()
    if not docs_dir.is_dir():
        raise NotADirectoryError(f"docs dir not found: {docs_dir}")
    exts = exts or DEFAULT_EXTS

    # Roots to walk, each paired with the relpath-prefix that marks an ADR within
    # it (None = use filename/dir heuristics only). The docs tree comes first;
    # an out-of-tree adr_dir is appended as a second root so it is still ingested.
    roots: list[tuple[Path, Optional[str]]] = [(docs_dir, None)]
    adr_resolved: Optional[Path] = None
    if adr_dir is not None:
        adr_resolved = adr_dir if adr_dir.is_absolute() else (docs_dir / adr_dir)
        adr_resolved = adr_resolved.resolve()
        if not adr_resolved.is_dir():
            raise NotADirectoryError(f"adr dir not found: {adr_resolved}")
        try:
            # adr_dir is inside the docs tree → mark it as an ADR-prefix on the docs root.
            in_tree = adr_resolved.relative_to(docs_dir).as_posix()
            roots = [(docs_dir, in_tree)]
        except ValueError:
            # adr_dir is outside the docs tree → walk it as its own ADR root.
            roots.append((adr_resolved, ""))

    frags: list[Fragment] = []
    seen_ids: set[str] = set()
    for root, adr_root in roots:
        files: list[Path] = []
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            if _is_skipped(p.relative_to(root).as_posix(), exclude):
                continue
            if p.suffix.lower() in exts:
                files.append(p)
        # deterministic order across the tree, then stable within each file.
        files.sort(key=lambda p: p.relative_to(root).as_posix())
        for p in files:
            rel = p.relative_to(root).as_posix()
            text = p.read_text(encoding="utf-8", errors="replace")
            for frag in _fragments_for_file(rel, text, adr_root):
                if frag.id in seen_ids:  # de-dup overlapping roots (idempotent)
                    continue
                seen_ids.add(frag.id)
                frags.append(frag)

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
    parser.add_argument(
        "--adr-dir",
        default=None,
        help="A repo's ADR directory (e.g. docs/adr or 02_System_Architecture/ADRs); "
        "every markdown doc at/below it is ingested as kind='adr' (FR-008). "
        "Absolute, or relative to docs_dir.",
    )
    parser.add_argument("--exclude", default=None, help="Comma-separated extra dir names to skip (hidden dot-dirs are always skipped).")
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
    adr_dir = Path(args.adr_dir) if args.adr_dir else None
    exclude = {e.strip() for e in args.exclude.split(",")} if args.exclude else frozenset()
    corpus = build_corpus(docs, args.project_name, exts, adr_dir=adr_dir, exclude=exclude)
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
