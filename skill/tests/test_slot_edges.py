"""Reading the governed citation slots → typed declared-tier edges (spec 008).

Neutral examples only (CORE / API / WEB).
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import cluster as cl  # noqa: E402
import discover_links as dl  # noqa: E402
from schema import (Fragment, FragmentCorpus, LinkEvidenceKind, LinkRel,  # noqa: E402
                    SourceRef, SourceType, WorkspaceManifest, WorkspaceMember)


def _frag(origin, locator, feature, text, kind="spec", typ=SourceType.SPEC):
    fid = f"{origin}::{locator}"
    return Fragment(id=fid, kind=kind, feature_key=feature, text=text,
                    source=SourceRef(type=typ, origin=origin, name=locator, locator=fid))


def _ws(api_spec_text, api_plan_text="---\n---\n# Plan\n", docs_spec_text="# Authentication\n\nLayered.\n"):
    docs = FragmentCorpus(project_name="docs", fragments=[
        _frag("docs", "001-auth/spec.md", "001-auth", docs_spec_text),
        _frag("docs", "docs/adr/ADR-001-sessions.md", "ADR-001", "# ADR-001: Durable sessions\n",
              kind="adr", typ=SourceType.ADR),
    ])
    api = FragmentCorpus(project_name="api", fragments=[
        _frag("api", "007-auth/spec.md", "007-auth", api_spec_text),
        _frag("api", "007-auth/plan.md", "007-auth", api_plan_text, kind="plan"),
    ])
    mani = WorkspaceManifest(members=[WorkspaceMember(origin="docs", path=".", role="docs"),
                                      WorkspaceMember(origin="api", path=".", role="spec")])
    return mani, {"docs": docs, "api": api}, {"docs": "CORE", "api": "API"}


def test_derived_from_slot_melds_even_when_slug_absent_from_source_prose():
    mani, corpora, ns = _ws(api_spec_text="---\nderived_from: [docs:001-auth]\n---\n# Auth API\n")
    # the source spec body must NOT contain the slug — the whole point
    assert "001-auth" not in corpora["docs"].fragments[0].text
    g = dl.build_link_graph(mani, corpora, namespaces=ns)
    df = [e for e in g.edges if e.rel is LinkRel.DERIVED_FROM
          and e.src.origin == "api" and e.dst.origin == "docs"]
    assert len(df) == 1
    assert df[0].evidence_kind is LinkEvidenceKind.DECLARED and df[0].evidence == "docs:001-auth"
    # and the two features cluster together
    cs = cl.build_clusters(corpora, g, source_origins={"docs"})
    auth = [c for c in cs.clusters if "001-auth" in str(c.members) and "007-auth" in str(c.members)]
    assert auth


def test_cites_slot_attaches_decision():
    mani, corpora, ns = _ws(api_spec_text="# Auth API\n",
                            api_plan_text="---\ncites: [CORE-ADR-001]\n---\n# Plan\n")
    g = dl.build_link_graph(mani, corpora, namespaces=ns)
    cites = [e for e in g.edges if e.rel is LinkRel.CITES and e.src.origin == "api" and e.dst.origin == "docs"]
    assert cites and cites[0].evidence_kind is LinkEvidenceKind.DECLARED


def test_unresolved_slot_mints_no_edge_but_is_reported():
    mani, corpora, ns = _ws(api_spec_text="---\nderived_from: [docs:999-missing]\n---\n# Auth API\n")
    edges, unresolved = dl.discover_slot_edges(mani, corpora, ns, {})
    assert not edges
    assert any("999-missing" in u for u in unresolved)


def test_slot_edge_supersedes_inferred_for_same_pair():
    # both specs share FR-001 (would mint an identifier derived_from edge) AND the slot is declared
    mani, corpora, ns = _ws(
        api_spec_text="---\nderived_from: [docs:001-auth]\n---\n# Auth API\n\n- FR-001 implemented.\n",
        docs_spec_text="# Authentication\n\n- FR-001 owned here.\n")
    g = dl.build_link_graph(mani, corpora, namespaces=ns)
    df = [e for e in g.edges if e.rel is LinkRel.DERIVED_FROM
          and e.src.origin == "api" and e.dst.origin == "docs"]
    assert len(df) == 1                                   # collapsed to one
    assert df[0].evidence_kind is LinkEvidenceKind.DECLARED   # the declared slot won


def test_no_slots_graph_identical_to_before():
    mani, corpora, ns = _ws(api_spec_text="# Auth API, no front-matter\n",
                            api_plan_text="# Plan, no front-matter\n")
    slot_edges, _ = dl.discover_slot_edges(mani, corpora, ns, {})
    assert slot_edges == []
    # the merged graph equals the pre-slot discovery (declared+identifier+adr) exactly
    baseline = [*dl.declared_edges(mani), *dl.discover_identifier_edges(mani, corpora),
                *dl.discover_adr_edges(mani, corpora, ns)]
    g = dl.build_link_graph(mani, corpora, namespaces=ns)
    assert {dl._key(e) for e in g.edges} == {dl._key(e) for e in baseline}


def test_reproducible():
    mani, corpora, ns = _ws(api_spec_text="---\nderived_from: [docs:001-auth]\n---\n# Auth API\n")
    a = dl.build_link_graph(mani, corpora, namespaces=ns).model_dump_json()
    b = dl.build_link_graph(mani, corpora, namespaces=ns).model_dump_json()
    assert a == b


def test_configured_slot_key_is_honored():
    # a repo whose citation_keys renames the derived_from slot to "derives"
    mani, corpora, ns = _ws(api_spec_text="---\nderives: [docs:001-auth]\n---\n# Auth API\n")
    ck = {"api": {"source_specs": "derives"}}
    edges, _ = dl.discover_slot_edges(mani, corpora, ns, ck)
    assert any(e.rel is LinkRel.DERIVED_FROM and e.evidence == "docs:001-auth" for e in edges)
    # with the DEFAULT key (no override) the renamed slot is not read → no slot edge
    edges_default, _ = dl.discover_slot_edges(mani, corpora, ns, {})
    assert not any(e.rel is LinkRel.DERIVED_FROM for e in edges_default)
