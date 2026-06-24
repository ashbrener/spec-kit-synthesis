"""Doc adapter tests — the Phase-3 third source, proving the seam once more.

The architectural bet (DESIGN §11.1): a design doc / ADR is a new ADAPTER, not
a rewrite. The source-agnostic core must accept a merged spec+doc corpus with
no locator collisions, exactly as it accepted spec+code.
"""

from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
import sys

sys.path.insert(0, str(SCRIPTS))

from schema import FragmentCorpus, SourceType  # noqa: E402
import adapter_doc  # noqa: E402
import adapter_speckit  # noqa: E402


def test_meta_and_archive_excluded(tmp_path):
    # spec 010 R3: repo-meta + archives are not source-of-truth and must not be ingested.
    (tmp_path / "99_Archive").mkdir()
    (tmp_path / "99_Archive" / "old.md").write_text("# Old draft\nx", encoding="utf-8")
    (tmp_path / "_Audits").mkdir()
    (tmp_path / "_Audits" / "memo.md").write_text("# Audit memo\nx", encoding="utf-8")
    for name in ("CLAUDE.md", "RESUME.md", "BACKEND_HANDOFF.md", "WORKTREES.md", "AGENTS.md"):
        (tmp_path / name).write_text(f"# {name}\nx", encoding="utf-8")
    (tmp_path / "real.md").write_text("# Real architecture doc\nGenuine source content.", encoding="utf-8")

    corpus = adapter_doc.build_corpus(tmp_path, "proj")
    ids = " ".join(f.id for f in corpus.fragments)
    assert "real.md" in ids                                   # genuine source ingested
    for noise in ("99_Archive", "_Audits", "CLAUDE.md", "RESUME.md", "BACKEND_HANDOFF.md",
                  "WORKTREES.md", "AGENTS.md"):
        assert noise not in ids, f"{noise} should be excluded from ingestion"


ARCHITECTURE_MD = """# Architecture Overview

The system is a pipeline.

## Components

Adapters, core, renderer.

## Data Flow

Fragments flow through the core.
"""

ADR_MD = """# 1. Use uv for dependency management

## Status

Accepted

## Context

We need reproducible installs.

## Decision

Use uv.
"""

NOTES_MD = """Just a flat note with no headings at all, kept whole.
"""


@pytest.fixture()
def docs_tree(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    (docs / "adr").mkdir(parents=True)
    (docs / "architecture.md").write_text(ARCHITECTURE_MD, encoding="utf-8")
    (docs / "adr" / "0001-use-uv.md").write_text(ADR_MD, encoding="utf-8")
    (docs / "notes.md").write_text(NOTES_MD, encoding="utf-8")
    # a non-markdown file that must be ignored
    (docs / "diagram.png").write_text("not markdown", encoding="utf-8")
    return docs


def test_corpus_validates(docs_tree: Path):
    corpus = adapter_doc.build_corpus(docs_tree, project_name="Doc System")
    assert isinstance(corpus, FragmentCorpus)
    # round-trip through the frozen schema validator
    FragmentCorpus.model_validate_json(corpus.model_dump_json())
    assert corpus.project_name == "Doc System"
    assert corpus.fragments, "corpus must be non-empty"


def test_fragments_typed_doc_or_adr_with_self_locator(docs_tree: Path):
    corpus = adapter_doc.build_corpus(docs_tree, "Demo")
    for f in corpus.fragments:
        # ADRs are adr-typed (spec 006 §4); all other docs are design_doc-typed
        expected = SourceType.ADR if f.kind == "adr" else SourceType.DESIGN_DOC
        assert f.source.type is expected
        assert f.source.locator == f.id, "locator must equal id (self-referential)"


def test_ids_stable_unique_deterministic(docs_tree: Path):
    a = adapter_doc.build_corpus(docs_tree, "Demo")
    b = adapter_doc.build_corpus(docs_tree, "Demo")
    # deterministic: identical JSON across two runs
    assert a.model_dump_json() == b.model_dump_json()
    ids = [f.id for f in a.fragments]
    assert len(ids) == len(set(ids)), "fragment ids must be unique"
    # stable scheme: relpath#slug
    assert "architecture.md#architecture-overview" in ids
    assert "architecture.md#components" in ids
    assert "architecture.md#data-flow" in ids


def test_heading_split_produces_multiple_fragments(docs_tree: Path):
    corpus = adapter_doc.build_corpus(docs_tree, "Demo")
    arch_frags = [f for f in corpus.fragments if f.id.startswith("architecture.md")]
    assert len(arch_frags) >= 3, "the multi-section doc must split into >=3 fragments"


def test_adr_classification(docs_tree: Path):
    corpus = adapter_doc.build_corpus(docs_tree, "Demo")
    adr_frags = [f for f in corpus.fragments if f.id.startswith("adr/0001-use-uv.md")]
    assert adr_frags, "ADR file must yield fragments"
    assert all(f.kind == "adr" for f in adr_frags), "ADR-style file must be kind='adr'"
    # the chip label reflects the adr kind
    assert all(f.source.name.startswith("adr · ") for f in adr_frags)
    # the architecture doc is a plain design-doc
    arch_frags = [f for f in corpus.fragments if f.id.startswith("architecture.md")]
    assert all(f.kind == "design-doc" for f in arch_frags)
    assert all(f.source.name.startswith("doc · ") for f in arch_frags)


def test_headingless_file_kept_whole(docs_tree: Path):
    corpus = adapter_doc.build_corpus(docs_tree, "Demo")
    notes = [f for f in corpus.fragments if f.id == "notes.md"]
    assert len(notes) == 1, "headingless file must be one whole-file fragment"
    assert notes[0].source.anchor is None


def test_non_markdown_ignored(docs_tree: Path):
    corpus = adapter_doc.build_corpus(docs_tree, "Demo")
    assert not any("diagram" in f.id for f in corpus.fragments)


def test_feature_key_grouping(docs_tree: Path):
    corpus = adapter_doc.build_corpus(docs_tree, "Demo")
    by_id = {f.id: f for f in corpus.fragments}
    # an ADR groups under its own id (FR-008), not its containing dir
    assert by_id["adr/0001-use-uv.md#status"].feature_key == "0001"
    # a plain (non-ADR) top-level file groups under its filename stem
    assert by_id["architecture.md#components"].feature_key == "architecture"


def test_include_override_extension(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# A\n\nbody\n", encoding="utf-8")
    (docs / "b.rst").write_text("just rst\n", encoding="utf-8")
    corpus = adapter_doc.build_corpus(docs, "Demo", exts={".rst"})
    ids = {f.id for f in corpus.fragments}
    assert "b.rst" in ids
    assert "a.md" not in ids and "a.md#a" not in ids


# ── cross-source seam: spec corpus + doc corpus merge cleanly ───────────────

SPEC_MD = """# Feature Specification: Demo

**Status**: Draft

## Overview

The demo system does a thing.

## Requirements

It must do the thing well.
"""


@pytest.fixture()
def specs_tree(tmp_path: Path) -> Path:
    specs = tmp_path / "specs"
    feat = specs / "001-demo"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text(SPEC_MD, encoding="utf-8")
    return specs


def test_cross_source_no_locator_collisions(docs_tree: Path, specs_tree: Path):
    docs = adapter_doc.build_corpus(docs_tree, "Demo")
    specs = adapter_speckit.build_corpus(specs_tree, project_name="Demo")

    doc_locs = docs.locators()
    spec_locs = specs.locators()
    assert doc_locs and spec_locs, "both corpora must be non-empty"

    # disjoint: doc ids are bare relpaths, spec ids are folder/file#slug
    assert doc_locs.isdisjoint(spec_locs), "no locator collisions across sources"

    merged = FragmentCorpus(
        project_name="Demo",
        fragments=[*specs.fragments, *docs.fragments],
    )
    merged_locs = merged.locators()
    # merged locator set is exactly the disjoint union
    assert merged_locs == doc_locs | spec_locs
    assert len(merged_locs) == len(doc_locs) + len(spec_locs)
    # every fragment id remains resolvable into the merged corpus (verify.verify
    # resolves source_ref.locator against exactly this set)
    for f in merged.fragments:
        assert f.source.locator in merged_locs


def test_cli_writes_validated_corpus(docs_tree: Path, tmp_path: Path):
    out = tmp_path / "corpus.json"
    rc = adapter_doc.main([str(docs_tree), "--project-name", "CLI Demo", "--out", str(out)])
    assert rc == 0
    corpus = FragmentCorpus.model_validate_json(out.read_text(encoding="utf-8"))
    assert corpus.project_name == "CLI Demo"
    assert corpus.fragments


def test_adapter_doc_skips_hidden_and_vendored_trees(tmp_path):
    # product content
    (tmp_path / "02_System_Architecture" / "ADRs").mkdir(parents=True)
    (tmp_path / "02_System_Architecture" / "ADRs" / "ADR-001-x.md").write_text("# ADR-001: X\n", encoding="utf-8")
    (tmp_path / "guide.md").write_text("# Guide\n", encoding="utf-8")
    # pollution: a vendored extension runtime + its fixtures, scaffolding, tooling (all dot-dirs)
    for poison in (".specify/extensions/arch-governance/docs/adr", ".specify/extensions/arch-governance/tests/fixtures/x/adr",
                   ".project-arc/template-base", ".claude/skills", ".venv/lib", "node_modules/pkg"):
        d = tmp_path / poison
        d.mkdir(parents=True)
        (d / "ADR-999-poison.md").write_text("# ADR-999: poison\n", encoding="utf-8")
    corpus = adapter_doc.build_corpus(tmp_path, "Repo")
    locs = [f.id for f in corpus.fragments]
    assert any("ADR-001" in loc for loc in locs) and any("guide" in loc for loc in locs)  # product kept
    assert not any(".specify" in loc or ".project-arc" in loc or ".claude" in loc
                   or ".venv" in loc or "node_modules" in loc for loc in locs)            # pollution gone
    assert not any("poison" in loc for loc in locs)


def test_adapter_doc_extra_exclude(tmp_path):
    (tmp_path / "keep").mkdir(); (tmp_path / "keep" / "a.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / "_Audits").mkdir(); (tmp_path / "_Audits" / "b.md").write_text("# B\n", encoding="utf-8")
    corpus = adapter_doc.build_corpus(tmp_path, "Repo", exclude={"_Audits"})
    locs = [f.id for f in corpus.fragments]
    assert any("keep/a.md" in loc for loc in locs)
    assert not any("_Audits" in loc for loc in locs)


def test_adapter_doc_path_prefix_exclude(tmp_path):
    # a path-prefix exclude skips exactly that subtree; a similarly-named leaf elsewhere is kept
    (tmp_path / "specs" / "001-a").mkdir(parents=True)
    (tmp_path / "specs" / "001-a" / "spec.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "adr" / "ADR-001.md").write_text("# ADR-001\n", encoding="utf-8")
    (tmp_path / "specsheet").mkdir()
    (tmp_path / "specsheet" / "y.md").write_text("# Y\n", encoding="utf-8")
    (tmp_path / "guide.md").write_text("# Guide\n", encoding="utf-8")
    corpus = adapter_doc.build_corpus(tmp_path, "Repo", exclude={"specs", "docs/adr"})
    locs = [f.id for f in corpus.fragments]
    assert any("guide" in loc for loc in locs)                       # narrative kept
    assert any("specsheet" in loc for loc in locs)                   # bare-name "specs" != "specsheet"
    assert not any(loc.startswith("specs/") for loc in locs)         # specs subtree excluded (name)
    assert not any("docs/adr" in loc for loc in locs)                # adr subtree excluded (prefix)
