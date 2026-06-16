"""Deterministic capability clustering (cluster.py — spec 006, US1).

Neutral examples only (CORE / API / WEB).
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import cluster as cl  # noqa: E402
from schema import (Fragment, FragmentCorpus, LinkEdge, LinkEndpoint, LinkGraph,  # noqa: E402
                    LinkRel, LinkEvidenceKind, SourceRef, SourceType)


def _frag(origin, locator, feature, kind="spec", typ=SourceType.SPEC):
    fid = f"{origin}::{locator}"
    return Fragment(id=fid, kind=kind, feature_key=feature, text="x",
                    source=SourceRef(type=typ, origin=origin, name=locator, locator=fid))


def _corpus(origin, frags):
    return FragmentCorpus(project_name=origin, fragments=frags)


def _edge(so, sl, do, dl, rel):
    return LinkEdge(src=LinkEndpoint(origin=so, locator=f"{so}::{sl}"),
                    dst=LinkEndpoint(origin=do, locator=f"{do}::{dl}"),
                    rel=rel, evidence_kind=LinkEvidenceKind.IDENTIFIER, evidence="FR-001")


def _ws():
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth"), _frag("core", "report/spec.md", "report")])
    api = _corpus("api", [_frag("api", "007-auth/plan.md", "007-auth"),
                          _frag("api", "009-report/plan.md", "009-report")])
    return {"core": core, "api": api}


def test_source_feature_seeds_and_build_attaches_via_derived_from():
    corpora = _ws()
    lg = LinkGraph(edges=[_edge("api", "007-auth/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM)])
    cs = cl.build_clusters(corpora, lg, source_origins={"core"})
    auth = [c for c in cs.clusters if c.seed == "auth"]
    assert len(auth) == 1
    c = auth[0]
    assert set(c.members) == {"core", "api"}          # woven across repos
    assert c.tiers[0] == "core"                        # source tier first
    assert c.evidence                                   # join reason recorded


def test_unrelated_features_stay_separate_no_over_merge():
    corpora = _ws()
    # auth derives from auth; report derives from report; plus a WEAK references edge linking the two
    lg = LinkGraph(edges=[
        _edge("api", "007-auth/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM),
        _edge("api", "009-report/plan.md", "core", "report/spec.md", LinkRel.DERIVED_FROM),
        _edge("api", "007-auth/plan.md", "api", "009-report/plan.md", LinkRel.REFERENCES),  # weak — ignored
    ])
    cs = cl.build_clusters(corpora, lg, source_origins={"core"})
    seeds = sorted(c.seed for c in cs.clusters if c.seed)
    assert seeds == ["auth", "report"]                 # two capabilities, not fused into one


def test_orphan_build_feature_stands_alone():
    corpora = _ws()
    lg = LinkGraph(edges=[_edge("api", "007-auth/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM)])
    # 009-report (api) has no edge to any source → orphan capability
    cs = cl.build_clusters(corpora, lg, source_origins={"core"})
    orphans = [c for c in cs.clusters if c.seed is None]
    assert any("009-report" in "".join(f for fs in c.members.values() for f in fs) for c in orphans)


def test_clustering_is_reproducible():
    corpora = _ws()
    lg = LinkGraph(edges=[_edge("api", "007-auth/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM)])
    a = cl.build_clusters(corpora, lg, source_origins={"core"}).model_dump_json()
    b = cl.build_clusters(corpora, lg, source_origins={"core"}).model_dump_json()
    assert a == b


# ── classification: capability / decision / background (spec 007) ────────────

def test_cluster_classification():
    core = _corpus("core", [
        _frag("core", "auth/spec.md", "auth"),                                          # spec
        _frag("core", "ADR-009.md", "ADR-009", kind="adr", typ=SourceType.ADR),         # cited ADR
        _frag("core", "ADR-050.md", "ADR-050", kind="adr", typ=SourceType.ADR),         # uncited ADR
        _frag("core", "01_overview/intro.md", "01_overview", kind="design-doc", typ=SourceType.DESIGN_DOC),  # narrative
    ])
    api = _corpus("api", [_frag("api", "007-auth/plan.md", "007-auth")])
    lg = LinkGraph(edges=[
        _edge("api", "007-auth/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM),
        _edge("core", "auth/spec.md", "core", "ADR-009.md", LinkRel.CITES),             # auth cites ADR-009
    ])
    cs = cl.build_clusters({"core": core, "api": api}, lg, source_origins={"core"})

    def members_str(c):
        return " ".join(f for fs in c.members.values() for f in fs)

    # the auth capability (source spec + build spec + the cited ADR) is a capability
    cap = [c for c in cs.clusters if c.kind == "capability"]
    assert any("auth/spec.md" in members_str(c) and "007-auth" in members_str(c) for c in cap)
    # the cited ADR-009 rides INSIDE the capability — never its own decision
    assert not any("ADR-009" in members_str(c) for c in cs.clusters if c.kind == "decision")
    assert any("ADR-009" in members_str(c) for c in cap)
    # the uncited ADR-050 is a decision; the narrative is background
    assert any("ADR-050" in members_str(c) for c in cs.clusters if c.kind == "decision")
    assert any("01_overview" in members_str(c) for c in cs.clusters if c.kind == "background")
    # capabilities are ordered ahead of decisions/background
    kinds = [c.kind for c in cs.clusters]
    assert kinds == sorted(kinds, key={"capability": 0, "decision": 1, "background": 2}.get)
