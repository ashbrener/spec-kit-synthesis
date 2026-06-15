"""Tests for merged multi-source ingestion in build_member_corpus (spec 005, Foundational).

Neutral examples only (CORE / API / WEB).
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import synthesize_atlas as sa  # noqa: E402
from schema import IngestionSource, WorkspaceMember  # noqa: E402

WS = Path(__file__).parent / "fixtures" / "governed_ws"


def test_merged_member_corpus_has_specs_and_adrs(tmp_path):
    # the API build repo: speckit over its specs + a doc pass over its adr dir, merged into one origin
    base = WS / "core"  # authority dir = base; api locator is ../api
    member = WorkspaceMember(
        origin="api", path="../api", role="spec",
        sources=[IngestionSource(adapter="speckit", path="../api/specs"),
                 IngestionSource(adapter="doc", path="../api/docs/adr", adr_dir=".")])
    corpus = sa.build_member_corpus(member, base, tmp_path)
    kinds = {f.kind for f in corpus.fragments}
    assert "adr" in kinds                                   # the ADR doc pass landed
    assert any(k != "adr" for k in kinds)                   # the speckit specs landed too
    # every fragment id is origin-stamped (workspace federation) and unique
    ids = [f.id for f in corpus.fragments]
    assert all(i.startswith("api::") for i in ids)
    assert len(ids) == len(set(ids))                        # no id collisions across merged sources


def test_legacy_single_adapter_member_unchanged(tmp_path):
    # a member with no `sources` uses the single adapter/path path (back-compat)
    member = WorkspaceMember(origin="web", path="../web/specs", adapter="speckit", role="spec")
    corpus = sa.build_member_corpus(member, WS / "core", tmp_path)
    assert corpus.fragments
    assert all(f.id.startswith("web::") for f in corpus.fragments)
