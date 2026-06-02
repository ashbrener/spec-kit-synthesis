"""spec-kit input adapter — turns spec folders into a source-neutral FragmentCorpus.

DESIGN anchors:
  §4     raw specs are the primary input (workstate is an optional structural
         overlay, NOT required); this adapter consumes only the raw spec files.
  §11.1  the adapter is the source-agnostic seam: it flattens spec folders into
         `Fragment`s so the core never sees a "spec", only fragments.
  §11.2 #2  provenance is source-TYPED from day one — every SourceRef here is
         `SourceType.SPEC`.

This is a deterministic, stdlib-only parse. NO LLM, no network, no new deps.
Same input → byte-identical output (stable, sorted, slug-collision-safe ids).

CLI:
    uv run python skill/scripts/adapter_speckit.py <specs_dir> \
        [--project-name NAME] [--out corpus.json]

It walks `<specs_dir>/NNN-*/` feature folders, splits each markdown artifact
into one fragment per top-level/`##` section (small/headingless files stay
whole), assigns a `kind` from the filename, groups by `feature_key` (the folder
name), and emits a validated `FragmentCorpus` JSON to --out or stdout.
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

# ── what an artifact filename means (DESIGN: source-neutral roles) ──────────
# Maps the canonical spec-kit artifact filenames to the adapter `kind`.
# Anything inside a `contracts/` directory is `contract` regardless of name.
# Files not in this map and not under contracts/ are skipped: tasks.md and
# checklists/ are workstate/process artifacts, not part of the spec corpus the
# core reasons over (DESIGN §4 — raw specs are the primary input).
_FILENAME_KIND = {
    "spec.md": "spec",
    "plan.md": "plan",
    "data-model.md": "data-model",
    "research.md": "research",
    "quickstart.md": "quickstart",
}

_CONTRACTS_DIR = "contracts"
_FEATURE_DIR_RE = re.compile(r"^\d{3}-")  # NNN-* feature folders


def _slugify(text: str) -> str:
    """Deterministic, URL-safe slug for a heading → fragment-id anchor."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "section"


def _kind_for(path: Path, feature_dir: Path) -> Optional[str]:
    """Return the adapter `kind` for a markdown file, or None if it's skipped."""
    rel = path.relative_to(feature_dir)
    # Any markdown under a contracts/ directory is a contract.
    if _CONTRACTS_DIR in rel.parts:
        return "contract"
    if len(rel.parts) == 1:  # top-level artifact file
        return _FILENAME_KIND.get(rel.name)
    return None


def _status_for(text: str, kind: str) -> Optional[str]:
    """Optionally capture a spec.md `**Status**:` line as a lifecycle token."""
    if kind != "spec":
        return None
    m = re.search(r"^\*\*Status\*\*\s*:\s*(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) chunks by top-level/`##` headings.

    A "section boundary" is an H1 (`# `) or H2 (`## `) at column 0. Content
    before the first such heading becomes a leading chunk titled "preamble".
    Deeper headings (### …) stay inside their parent section so fragments
    remain bounded but coherent.

    Returns an ordered list of (heading_text, section_text). `section_text`
    includes the heading line itself so fragments are self-describing.
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
            # strip a trailing markdown decoration like *(mandatory)* from the heading
            raw = m.group(2).strip()
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


def _spec_number(feature_name: str) -> str:
    """`001-spec-kit-linear-bridge` → `001` (for the human chip label)."""
    m = re.match(r"^(\d{3})", feature_name)
    return m.group(1) if m else feature_name


def _fragments_for_file(
    md_path: Path, feature_dir: Path, feature_name: str, kind: str
) -> list[Fragment]:
    text = md_path.read_text(encoding="utf-8")
    rel = md_path.relative_to(feature_dir).as_posix()  # e.g. "spec.md" / "contracts/x.md"
    lifecycle = _status_for(text, kind)
    spec_no = _spec_number(feature_name)

    sections = _split_sections(text)
    single = len(sections) <= 1  # keep small/whole/headingless files as one fragment

    frags: list[Fragment] = []
    seen_slugs: dict[str, int] = {}
    for heading, body in sections:
        if single:
            anchor = heading if heading not in ("preamble", "section") else None
            locator = f"{feature_name}/{rel}"
        else:
            slug = _slugify(heading)
            # disambiguate duplicate headings within one file deterministically
            n = seen_slugs.get(slug, 0)
            seen_slugs[slug] = n + 1
            slug_final = slug if n == 0 else f"{slug}-{n + 1}"
            anchor = heading
            locator = f"{feature_name}/{rel}#{slug_final}"

        # human chip label, spec-number-bearing: "spec-001 · spec.md"
        name = f"spec-{spec_no} · {rel}"
        source = SourceRef(
            type=SourceType.SPEC,
            name=name,
            locator=locator,
            anchor=anchor,
        )
        frags.append(
            Fragment(
                id=locator,
                source=source,
                kind=kind,
                feature_key=feature_name,
                lifecycle=lifecycle,
                text=body,
            )
        )
    return frags


def build_corpus(specs_dir: Path, project_name: Optional[str] = None) -> FragmentCorpus:
    """Walk `<specs_dir>/NNN-*/` and build a validated FragmentCorpus."""
    specs_dir = specs_dir.resolve()
    if not specs_dir.is_dir():
        raise NotADirectoryError(f"specs dir not found: {specs_dir}")

    feature_dirs = sorted(
        p for p in specs_dir.iterdir() if p.is_dir() and _FEATURE_DIR_RE.match(p.name)
    )

    fragments: list[Fragment] = []
    for feature_dir in feature_dirs:
        feature_name = feature_dir.name
        # deterministic order: sort all markdown files within the feature
        md_files = sorted(
            feature_dir.rglob("*.md"),
            key=lambda p: p.relative_to(feature_dir).as_posix(),
        )
        for md_path in md_files:
            kind = _kind_for(md_path, feature_dir)
            if kind is None:
                continue
            fragments.extend(_fragments_for_file(md_path, feature_dir, feature_name, kind))

    if not project_name:
        project_name = _default_project_name(specs_dir, feature_dirs)

    return FragmentCorpus(project_name=project_name, fragments=fragments)


def _default_project_name(specs_dir: Path, feature_dirs: list[Path]) -> str:
    """Derive a sensible display name when --project-name is not given.

    Prefer the repo/parent directory of `specs/`; fall back to the first
    feature's slug stripped of its number; finally the specs dir name.
    """
    parent = specs_dir.parent.name
    if parent and parent not in (".", ""):
        return parent
    if feature_dirs:
        stem = _FEATURE_DIR_RE.sub("", feature_dirs[0].name)
        return stem.replace("-", " ").title() or specs_dir.name
    return specs_dir.name


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Flatten spec-kit spec folders into a source-neutral FragmentCorpus.",
    )
    parser.add_argument("specs_dir", help="Path to the specs/ directory containing NNN-* feature folders.")
    parser.add_argument("--project-name", default=None, help="Display name for the FragmentCorpus.")
    parser.add_argument("--out", default=None, help="Write JSON here (default: stdout).")
    args = parser.parse_args(argv)

    corpus = build_corpus(Path(args.specs_dir), args.project_name)
    payload = corpus.model_dump_json(indent=2)

    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
        print(f"wrote {len(corpus.fragments)} fragments → {args.out}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
