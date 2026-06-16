"""ADR ingestion contract (FR-008) — ADR documents become first-class corpus
fragments so the source-view renderer can render them and claims can cite them.

Covers both example layouts:
  * ungoverned: a published docs tree, e.g. docs/architecture/ADRs/ADR-005-*.md
  * governed:   docs/adr/<NS>-ADR-NNN-*.md
plus the --adr-dir override (a repo's declared adr_dir forces kind='adr').

The bet (DESIGN §11.1): an ADR is a new INPUT shape feeding the SAME
source-agnostic core — not a schema change. ADRs land as kind='adr',
SourceType.design_doc, one fragment per section, with self-referential
file#section locators the verify gate / source-view renderer resolve.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from schema import FragmentCorpus, SourceType  # noqa: E402
import adapter_doc  # noqa: E402


# ── tiny ADR fixtures (2-3 files), both real-world layouts ──────────────────

UNGOVERNED_ADR = """# ADR-005: Adopt an event bus

## Status

Accepted

## Context

Services were coupled by direct calls.

## Decision

Introduce an internal event bus for cross-service messaging.
"""

GOVERNED_ADR = """# CORE-ADR-002: Single write path

## Status

Accepted

## Decision

All writes go through the command handler.
"""

PLAIN_DOC = """# Architecture Overview

The system is a pipeline of adapters, core, and renderer.
"""


@pytest.fixture()
def repo_docs(tmp_path: Path) -> Path:
    """A docs tree mixing an ungoverned ADR, a governed ADR, and a plain doc."""
    root = tmp_path / "repo"
    (root / "02_System_Architecture" / "ADRs").mkdir(parents=True)
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "02_System_Architecture" / "ADRs" / "ADR-005-event-bus.md").write_text(
        UNGOVERNED_ADR, encoding="utf-8"
    )
    (root / "docs" / "adr" / "CORE-ADR-002-single-write-path.md").write_text(
        GOVERNED_ADR, encoding="utf-8"
    )
    (root / "docs" / "architecture.md").write_text(PLAIN_DOC, encoding="utf-8")
    return root


def test_adrs_become_adr_kind_and_adr_typed(repo_docs: Path):
    corpus = adapter_doc.build_corpus(repo_docs, project_name="Repo")
    FragmentCorpus.model_validate_json(corpus.model_dump_json())  # frozen-schema round-trip

    adr_frags = [f for f in corpus.fragments if f.kind == "adr"]
    assert adr_frags, "both ADRs must be ingested as kind='adr'"
    # every ADR fragment is adr-typed (spec 006 §4) with a self-referential locator + adr chip
    for f in adr_frags:
        assert f.source.type is SourceType.ADR
        assert f.source.locator == f.id, "locator must equal id (resolver invariant)"
        assert f.source.name.startswith("adr · ")
    # the plain doc stays a design-doc, never reclassified as adr
    arch = [f for f in corpus.fragments if f.id.startswith("docs/architecture.md")]
    assert arch and all(f.kind == "design-doc" for f in arch)


def test_both_layouts_detected_and_sectioned(repo_docs: Path):
    corpus = adapter_doc.build_corpus(repo_docs, "Repo")
    by_id = {f.id: f for f in corpus.fragments}

    # ungoverned ADR under an ADRs/ dir, split per ## section with file#section ids
    ung = "02_System_Architecture/ADRs/ADR-005-event-bus.md"
    assert by_id[f"{ung}#status"].kind == "adr"
    assert by_id[f"{ung}#decision"].kind == "adr"
    # governed <NS>-ADR-NNN record under docs/adr
    gov = "docs/adr/CORE-ADR-002-single-write-path.md"
    assert by_id[f"{gov}#status"].kind == "adr"
    assert by_id[f"{gov}#decision"].kind == "adr"


def test_feature_key_is_the_adr_id(repo_docs: Path):
    corpus = adapter_doc.build_corpus(repo_docs, "Repo")
    by_id = {f.id: f for f in corpus.fragments}
    # ADR fragments group under the ADR's own id (FR-008), not the dir/stem
    assert by_id["02_System_Architecture/ADRs/ADR-005-event-bus.md#status"].feature_key == "ADR-005"
    assert by_id["docs/adr/CORE-ADR-002-single-write-path.md#decision"].feature_key == "CORE-ADR-002"


def test_text_preserved_and_locators_resolvable(repo_docs: Path):
    corpus = adapter_doc.build_corpus(repo_docs, "Repo")
    by_id = {f.id: f for f in corpus.fragments}
    locs = corpus.locators()

    decision = by_id["02_System_Architecture/ADRs/ADR-005-event-bus.md#decision"]
    assert "Introduce an internal event bus" in decision.text, "ADR body text preserved verbatim"
    assert decision.source.anchor == "Decision"
    # every fragment's self-locator resolves into the corpus (verify-gate contract)
    for f in corpus.fragments:
        assert f.source.locator in locs


def test_deterministic(repo_docs: Path):
    a = adapter_doc.build_corpus(repo_docs, "Repo")
    b = adapter_doc.build_corpus(repo_docs, "Repo")
    assert a.model_dump_json() == b.model_dump_json()
    ids = [f.id for f in a.fragments]
    assert len(ids) == len(set(ids)), "fragment ids unique"


def test_adr_dir_override_forces_adr_kind(tmp_path: Path):
    """A declared adr_dir forces kind='adr' even for non-ADR-shaped filenames."""
    root = tmp_path / "repo"
    (root / "design").mkdir(parents=True)
    # an arbitrarily-named decision record, NOT matching the ADR filename heuristic
    (root / "design" / "use-postgres.md").write_text(
        "# Use Postgres\n\n## Decision\n\nUse Postgres.\n", encoding="utf-8"
    )
    # heuristic alone: it is a plain design-doc
    plain = adapter_doc.build_corpus(root, "Repo")
    assert all(f.kind == "design-doc" for f in plain.fragments)
    # with --adr-dir pointing at it: forced to adr
    forced = adapter_doc.build_corpus(root, "Repo", adr_dir=Path("design"))
    assert forced.fragments and all(f.kind == "adr" for f in forced.fragments)


def test_adr_dir_outside_docs_tree_is_still_ingested(tmp_path: Path):
    """ADRs living outside the docs tree are reachable via --adr-dir (FR-008)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "overview.md").write_text("# Overview\n\nText.\n", encoding="utf-8")
    adrs = tmp_path / "architecture" / "ADRs"
    adrs.mkdir(parents=True)
    (adrs / "ADR-001-foo.md").write_text("# ADR-001: Foo\n\n## Decision\n\nFoo.\n", encoding="utf-8")

    corpus = adapter_doc.build_corpus(docs, "Repo", adr_dir=adrs)  # absolute, out-of-tree
    kinds = {f.kind for f in corpus.fragments}
    assert "design-doc" in kinds and "adr" in kinds
    adr_ids = [f.id for f in corpus.fragments if f.kind == "adr"]
    assert any(i.startswith("ADR-001-foo.md") for i in adr_ids), "out-of-tree ADR ingested"


def test_cli_with_adr_dir_writes_validated_corpus(repo_docs: Path, tmp_path: Path):
    out = tmp_path / "corpus.json"
    rc = adapter_doc.main(
        [str(repo_docs), "--project-name", "Repo", "--adr-dir", "docs/adr", "--out", str(out)]
    )
    assert rc == 0
    corpus = FragmentCorpus.model_validate_json(out.read_text(encoding="utf-8"))
    assert any(f.kind == "adr" for f in corpus.fragments)
