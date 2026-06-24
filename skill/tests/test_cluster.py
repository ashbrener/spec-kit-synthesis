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


def _edge(so, sl, do, dl, rel, ek=LinkEvidenceKind.IDENTIFIER):
    return LinkEdge(src=LinkEndpoint(origin=so, locator=f"{so}::{sl}"),
                    dst=LinkEndpoint(origin=do, locator=f"{do}::{dl}"),
                    rel=rel, evidence_kind=ek, evidence="FR-001")


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


# ── source-anchored multi-membership (spec 009) ──────────────────────────────

def _mstr(c):
    return " ".join(f for fs in c.members.values() for f in fs)


def test_bridging_build_artifact_does_not_merge_sources():
    # US1: a build plan that derives_from TWO source features must NOT fuse them; it joins both
    # capabilities (multi-membership) while the two anchors stay separate.
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth"), _frag("core", "admin/spec.md", "admin")])
    api = _corpus("api", [_frag("api", "002-auth-api/plan.md", "002-auth-api", kind="plan")])
    lg = LinkGraph(edges=[
        _edge("api", "002-auth-api/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM),
        _edge("api", "002-auth-api/plan.md", "core", "admin/spec.md", LinkRel.DERIVED_FROM),
    ])
    cs = cl.build_clusters({"core": core, "api": api}, lg, source_origins={"core"})
    caps = [c for c in cs.clusters if c.kind == "capability" and c.seed]
    assert sorted(c.seed for c in caps) == ["admin", "auth"]          # two capabilities, not one
    assert sum("002-auth-api" in _mstr(c) for c in caps) == 2         # build plan in BOTH (multi-membership)
    for c in caps:
        assert len(c.members.get("core", [])) == 1                   # exactly one source feature per capability


def test_source_anchored_one_capability_per_feature_weak_guard():
    # US1: each source feature anchors exactly one capability; a WEAK references edge between two
    # anchors never merges them.
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth"), _frag("core", "admin/spec.md", "admin")])
    lg = LinkGraph(edges=[_edge("core", "auth/spec.md", "core", "admin/spec.md", LinkRel.REFERENCES)])
    cs = cl.build_clusters({"core": core}, lg, source_origins={"core"})
    assert sorted(c.seed for c in cs.clusters if c.seed) == ["admin", "auth"]


def test_melded_chain_source_spec_code():
    # US1: source <-derived_from- spec <-implements- code all cohere into the one capability.
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth")])
    api = _corpus("api", [_frag("api", "002-auth/plan.md", "002-auth", kind="plan")])
    web = _corpus("web", [_frag("web", "auth.py", None, kind="code", typ=SourceType.CODE)])
    lg = LinkGraph(edges=[
        _edge("api", "002-auth/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM),  # source<->build identifier
        # cross-repo build<->build implements must be DECLARED to confer (spec 010: identifier
        # derived_from/implements only confers source<->build; build<->build needs a declared edge).
        _edge("web", "auth.py", "api", "002-auth/plan.md", LinkRel.IMPLEMENTS, LinkEvidenceKind.DECLARED),
    ])
    cs = cl.build_clusters({"core": core, "api": api, "web": web}, lg, source_origins={"core"})
    cap = [c for c in cs.clusters if c.seed == "auth"][0]
    m = _mstr(cap)
    assert "002-auth" in m and "auth.py" in m


def test_cited_adr_joins_capability_not_singleton():
    # US2: an ADR cited by a capability's spec is a member of that capability, not a singleton.
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth"),
                            _frag("core", "ADR-009.md", "ADR-009", kind="adr", typ=SourceType.ADR)])
    lg = LinkGraph(edges=[_edge("core", "auth/spec.md", "core", "ADR-009.md", LinkRel.CITES)])
    cs = cl.build_clusters({"core": core}, lg, source_origins={"core"})
    cap = [c for c in cs.clusters if c.seed == "auth"][0]
    assert "ADR-009" in _mstr(cap)
    assert not any(c.kind == "decision" and "ADR-009" in _mstr(c) for c in cs.clusters)


def test_shared_adr_does_not_bridge_capabilities():
    # US2 (the key fix): two capabilities' specs both citing the same ADR must NOT become co-members.
    # The ADR is in both (multi-membership); neither spec leaks into the other's capability.
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth"), _frag("core", "admin/spec.md", "admin"),
                            _frag("core", "ADR-011.md", "ADR-011", kind="adr", typ=SourceType.ADR)])
    api = _corpus("api", [_frag("api", "002-auth/plan.md", "002-auth", kind="plan"),
                          _frag("api", "004-admin/plan.md", "004-admin", kind="plan")])
    lg = LinkGraph(edges=[
        _edge("api", "002-auth/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM),
        _edge("api", "004-admin/plan.md", "core", "admin/spec.md", LinkRel.DERIVED_FROM),
        _edge("api", "002-auth/plan.md", "core", "ADR-011.md", LinkRel.CITES),
        _edge("api", "004-admin/plan.md", "core", "ADR-011.md", LinkRel.CITES),
    ])
    cs = cl.build_clusters({"core": core, "api": api}, lg, source_origins={"core"})
    caps = [c for c in cs.clusters if c.kind == "capability" and c.seed]
    assert sorted(c.seed for c in caps) == ["admin", "auth"]          # NOT merged through the shared ADR
    cap_auth = [c for c in caps if c.seed == "auth"][0]
    cap_admin = [c for c in caps if c.seed == "admin"][0]
    assert "ADR-011" in _mstr(cap_auth) and "ADR-011" in _mstr(cap_admin)   # ADR in both
    assert "004-admin" not in _mstr(cap_auth)                        # admin's plan did not leak in
    assert "002-auth" not in _mstr(cap_admin)


def test_build_spec_melds_via_shared_source_decision():
    # US2 (R4): when a source spec OWNS a decision (cites it) and a build spec cites the SAME decision,
    # the build melds into that source's capability — even with no explicit derived_from. But this only
    # works for a decision the SOURCE anchor cites; it must not bridge two anchors (see no-leak below).
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth"),
                            _frag("core", "ADR-001.md", "ADR-001", kind="adr", typ=SourceType.ADR)])
    api = _corpus("api", [_frag("api", "007-auth/plan.md", "007-auth", kind="plan")])
    lg = LinkGraph(edges=[
        _edge("core", "auth/spec.md", "core", "ADR-001.md", LinkRel.CITES),     # source owns ADR-001
        _edge("api", "007-auth/plan.md", "core", "ADR-001.md", LinkRel.CITES),  # build cites the same
    ])
    cs = cl.build_clusters({"core": core, "api": api}, lg, source_origins={"core"})
    cap = [c for c in cs.clusters if c.seed == "auth"][0]
    assert "007-auth" in _mstr(cap) and "ADR-001" in _mstr(cap)   # build + decision melded into the source cap
    assert {"core", "api"} <= set(cap.members)


def test_shared_source_decision_does_not_bridge_two_anchors():
    # R4 guard: two source specs citing the SAME decision are NOT merged (anchors never fuse), even
    # though the decision is a member of both capabilities.
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth"), _frag("core", "report/spec.md", "report"),
                            _frag("core", "ADR-001.md", "ADR-001", kind="adr", typ=SourceType.ADR)])
    lg = LinkGraph(edges=[
        _edge("core", "auth/spec.md", "core", "ADR-001.md", LinkRel.CITES),
        _edge("core", "report/spec.md", "core", "ADR-001.md", LinkRel.CITES),
    ])
    cs = cl.build_clusters({"core": core}, lg, source_origins={"core"})
    assert sorted(c.seed for c in cs.clusters if c.seed) == ["auth", "report"]   # two capabilities
    for seed in ("auth", "report"):
        cap = [c for c in cs.clusters if c.seed == seed][0]
        assert "ADR-001" in _mstr(cap)                          # decision in both (multi-membership)
        other = "report" if seed == "auth" else "auth"
        assert other not in _mstr(cap)                          # but the other source spec did NOT leak in


def test_uncited_adr_and_untied_narrative_stay_honest():
    # US2: an uncited ADR is its own decision; a feature-less, edge-less narrative is unclustered.
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth"),
                            _frag("core", "ADR-050.md", "ADR-050", kind="adr", typ=SourceType.ADR),
                            _frag("core", "notes.md", None, kind="design-doc", typ=SourceType.DESIGN_DOC)])
    cs = cl.build_clusters({"core": core}, LinkGraph(edges=[]), source_origins={"core"})
    assert any(c.kind == "decision" and "ADR-050" in _mstr(c) for c in cs.clusters)
    assert any("notes.md" in u for u in cs.unclustered)


def test_clusterset_is_byte_identical_across_runs():
    # US3: determinism, exercised on a multi-membership workspace.
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth"), _frag("core", "admin/spec.md", "admin"),
                            _frag("core", "ADR-011.md", "ADR-011", kind="adr", typ=SourceType.ADR)])
    api = _corpus("api", [_frag("api", "002-auth/plan.md", "002-auth", kind="plan")])
    lg = LinkGraph(edges=[
        _edge("api", "002-auth/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM),
        _edge("api", "002-auth/plan.md", "core", "admin/spec.md", LinkRel.DERIVED_FROM),
        _edge("api", "002-auth/plan.md", "core", "ADR-011.md", LinkRel.CITES),
    ])
    a = cl.build_clusters({"core": core, "api": api}, lg, source_origins={"core"}).model_dump_json()
    b = cl.build_clusters({"core": core, "api": api}, lg, source_origins={"core"}).model_dump_json()
    assert a == b


def test_every_nonanchor_membership_has_evidence():
    # US3: a capability that reaches beyond its own anchor feature records why.
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth")])
    api = _corpus("api", [_frag("api", "002-auth/plan.md", "002-auth", kind="plan")])
    lg = LinkGraph(edges=[_edge("api", "002-auth/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM)])
    cs = cl.build_clusters({"core": core, "api": api}, lg, source_origins={"core"})
    cap = [c for c in cs.clusters if c.seed == "auth"][0]
    assert len(cap.members) > 1 and cap.evidence            # crossed origins → must be explained


def test_no_membership_without_basis():
    # US3: a build feature with no qualifying edge is never attached to a capability.
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth")])
    api = _corpus("api", [_frag("api", "orphan/plan.md", "orphan", kind="plan")])
    cs = cl.build_clusters({"core": core, "api": api}, LinkGraph(edges=[]), source_origins={"core"})
    cap = [c for c in cs.clusters if c.seed == "auth"][0]
    assert "orphan" not in _mstr(cap)


# ── contract-driven membership: evidence-tier gating + hub flag (spec 010) ───

def test_identifier_build_to_build_confers_no_membership():
    # R1: an identifier-inferred build↔build derived_from edge (shared FR/slug token) must NOT
    # pull one build feature into another's capability.
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth")])
    be = _corpus("be", [_frag("be", "002-auth/plan.md", "002-auth", kind="plan")])
    fe = _corpus("fe", [_frag("fe", "001-scaffold/plan.md", "001-scaffold", kind="plan")])
    lg = LinkGraph(edges=[
        _edge("be", "002-auth/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM),       # source↔build (admitted)
        _edge("fe", "001-scaffold/plan.md", "be", "002-auth/plan.md", LinkRel.DERIVED_FROM),  # build↔build identifier (noise)
    ])
    cs = cl.build_clusters({"core": core, "be": be, "fe": fe}, lg, source_origins={"core"})
    cap = [c for c in cs.clusters if c.seed == "auth"][0]
    assert "002-auth" in _mstr(cap)            # admitted source↔build refinement
    assert "001-scaffold" not in _mstr(cap)    # build↔build identifier did NOT confer membership


def test_identifier_source_to_build_still_confers():
    # R1: an un-governed workspace (no declared slots) still clusters via a source↔build identifier.
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth")])
    be = _corpus("be", [_frag("be", "002-auth/plan.md", "002-auth", kind="plan")])
    lg = LinkGraph(edges=[_edge("be", "002-auth/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM)])
    cs = cl.build_clusters({"core": core, "be": be}, lg, source_origins={"core"})
    assert "002-auth" in _mstr([c for c in cs.clusters if c.seed == "auth"][0])


def test_membership_invariant_to_inferred_noise():
    # R1: adding build↔build identifier + prose edges changes NOTHING (declared drives membership).
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth"), _frag("core", "admin/spec.md", "admin")])
    be = _corpus("be", [_frag("be", "002-auth/plan.md", "002-auth", kind="plan"),
                        _frag("be", "003-admin/plan.md", "003-admin", kind="plan")])
    declared = [
        _edge("be", "002-auth/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM, LinkEvidenceKind.DECLARED),
        _edge("be", "003-admin/plan.md", "core", "admin/spec.md", LinkRel.DERIVED_FROM, LinkEvidenceKind.DECLARED),
    ]
    noise = [
        _edge("be", "002-auth/plan.md", "be", "003-admin/plan.md", LinkRel.DERIVED_FROM),                 # build↔build identifier
        _edge("be", "003-admin/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM, LinkEvidenceKind.PROSE),  # prose
    ]

    def memb(cs):
        return sorted((c.seed, tuple(sorted(f for v in c.members.values() for f in v))) for c in cs.clusters)

    clean = cl.build_clusters({"core": core, "be": be}, LinkGraph(edges=declared), source_origins={"core"})
    noisy = cl.build_clusters({"core": core, "be": be}, LinkGraph(edges=declared + noise), source_origins={"core"})
    assert memb(clean) == memb(noisy)


def test_hub_rendered_faithfully_and_flagged():
    # FR-004: a feature ≥2 others declare derived_from is rendered as the declared capability
    # (not split/re-anchored) and flagged with the dependent count.
    core = _corpus("core", [_frag("core", "arch/spec.md", "arch")])
    be = _corpus("be", [_frag("be", "002-auth/plan.md", "002-auth", kind="plan"),
                        _frag("be", "003-admin/plan.md", "003-admin", kind="plan")])
    lg = LinkGraph(edges=[
        _edge("be", "002-auth/plan.md", "core", "arch/spec.md", LinkRel.DERIVED_FROM, LinkEvidenceKind.DECLARED),
        _edge("be", "003-admin/plan.md", "core", "arch/spec.md", LinkRel.DERIVED_FROM, LinkEvidenceKind.DECLARED),
    ])
    cap = [c for c in cl.build_clusters({"core": core, "be": be}, lg, source_origins={"core"}).clusters
           if c.seed == "arch"][0]
    assert cap.hub_dependents == 2
    assert "002-auth" in _mstr(cap) and "003-admin" in _mstr(cap)   # rendered as declared, not split


def test_planned_and_orphan_have_zero_hub_dependents():
    # FR-004: a feature with no declared dependents has hub_dependents == 0.
    core = _corpus("core", [_frag("core", "auth/spec.md", "auth"), _frag("core", "planned/spec.md", "planned")])
    be = _corpus("be", [_frag("be", "002-auth/plan.md", "002-auth", kind="plan")])
    lg = LinkGraph(edges=[_edge("be", "002-auth/plan.md", "core", "auth/spec.md", LinkRel.DERIVED_FROM, LinkEvidenceKind.DECLARED)])
    cs = cl.build_clusters({"core": core, "be": be}, lg, source_origins={"core"})
    assert [c for c in cs.clusters if c.seed == "planned"][0].hub_dependents == 0
    assert [c for c in cs.clusters if c.seed == "auth"][0].hub_dependents == 1


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
