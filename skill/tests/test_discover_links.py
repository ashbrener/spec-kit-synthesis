"""Tests for cross-repo edge discovery (discover_links.py — spec 002, Phase D)."""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import discover_links as dl  # noqa: E402
from schema import (DeclaredLink, Fragment, FragmentCorpus, LinkEvidenceKind,  # noqa: E402
                    LinkRel, SourceRef, SourceType, WorkspaceManifest, WorkspaceMember)


def _corpus(origin, frags):
    """frags: list of (locator, text). Returns an origin-stamped corpus (like the orchestrator)."""
    fl = [Fragment(id=loc, source=SourceRef(type=SourceType.SPEC, name=loc, locator=loc), kind="spec", text=txt)
          for loc, txt in frags]
    return FragmentCorpus(project_name=origin, fragments=fl).with_origin(origin)


def _kinded_corpus(origin, frags):
    """frags: list of (locator, kind, text). Origin-stamped corpus with per-fragment kinds."""
    fl = [Fragment(id=loc, source=SourceRef(type=SourceType.SPEC, name=loc, locator=loc), kind=kind, text=txt)
          for loc, kind, txt in frags]
    return FragmentCorpus(project_name=origin, fragments=fl).with_origin(origin)


def _manifest(members, links=None):
    return WorkspaceManifest(
        members=[WorkspaceMember(origin=o, path=o, adapter="speckit", role=r) for o, r in members],
        links=links or [],
    )


def test_only_qualified_identifiers_are_extracted():
    c = _corpus("specs", [("spec.md#a", "Implements FR-025 and SC-3 and 001-some-feature. Uses config + database.")])
    toks = set(dl.extract_identifiers(c))
    assert "FR-025" in toks and "SC-3" in toks and "001-some-feature" in toks
    assert "config" not in toks and "database" not in toks   # generic words never qualify


def test_identifier_edge_code_implements_spec():
    specs = _corpus("specs", [("spec.md#fr25", "FR-025: the system screens transactions.")])
    code = _corpus("be", [("screen.py#run", "# FR-025 implemented here\n")])
    m = _manifest([("specs", "spec"), ("be", "code")])
    edges = dl.discover_identifier_edges(m, {"specs": specs, "be": code})
    assert len(edges) == 1
    e = edges[0]
    assert e.rel is LinkRel.IMPLEMENTS                        # code implements spec
    assert e.evidence_kind is LinkEvidenceKind.IDENTIFIER and e.evidence == "FR-025"
    assert e.src.origin == "be" and e.src.locator.startswith("be::")
    assert e.dst.origin == "specs" and e.dst.locator.startswith("specs::")


def test_docs_spec_maps_to_references():
    # the contract has no typed docs↔spec relation → untyped `references` fallback (spec 004)
    docs = _corpus("guide", [("g.md#x", "This behaviour is required by FR-007.")])
    specs = _corpus("specs", [("s.md#fr7", "FR-007 — the rule.")])
    m = _manifest([("guide", "docs"), ("specs", "spec")])
    edges = dl.discover_identifier_edges(m, {"guide": docs, "specs": specs})
    assert len(edges) == 1 and edges[0].rel is LinkRel.REFERENCES
    # stable, origin-sorted direction (no upstream/downstream inferable from a shared id)
    assert {edges[0].src.origin, edges[0].dst.origin} == {"guide", "specs"}


def test_spec_spec_maps_to_derived_from():
    a = _corpus("specs-a", [("a.md#fr", "FR-009 — the rule.")])
    b = _corpus("specs-b", [("b.md#fr", "FR-009 referenced here.")])
    m = _manifest([("specs-a", "spec"), ("specs-b", "spec")])
    edges = dl.discover_identifier_edges(m, {"specs-a": a, "specs-b": b})
    assert len(edges) == 1 and edges[0].rel is LinkRel.DERIVED_FROM


def test_no_edge_when_identifier_not_shared():
    specs = _corpus("specs", [("s#a", "FR-001 only here")])
    code = _corpus("be", [("c#a", "FR-999 only here")])
    m = _manifest([("specs", "spec"), ("be", "code")])
    assert dl.discover_identifier_edges(m, {"specs": specs, "be": code}) == []


def test_declared_edges_are_namespaced_and_trusted():
    m = _manifest([("docs", "docs"), ("specs", "spec")],
                  links=[DeclaredLink(src_origin="docs", src_locator="overview.md#x",
                                      dst_origin="specs", dst_locator="spec.md#y", rel=LinkRel.REFERENCES)])
    edges = dl.declared_edges(m)
    assert len(edges) == 1 and edges[0].evidence_kind is LinkEvidenceKind.DECLARED
    assert edges[0].src.locator == "docs::overview.md#x" and edges[0].dst.locator == "specs::spec.md#y"


def test_build_link_graph_merges_dedups_and_is_deterministic():
    specs = _corpus("specs", [("spec.md#fr25", "FR-025 here.")])
    code = _corpus("be", [("c.py#r", "FR-025 here too.")])
    m = _manifest([("specs", "spec"), ("be", "code")],
                  links=[DeclaredLink(src_origin="be", src_locator="c.py#r",
                                      dst_origin="specs", dst_locator="spec.md#fr25", rel=LinkRel.IMPLEMENTS)])
    g1 = dl.build_link_graph(m, {"specs": specs, "be": code})
    # the declared edge and the discovered identifier edge are the same (src,dst,rel) →
    # deduped to one, and the trusted DECLARED evidence wins.
    assert len(g1.edges) == 1
    assert g1.edges[0].evidence_kind is LinkEvidenceKind.DECLARED
    g2 = dl.build_link_graph(m, {"specs": specs, "be": code})
    assert g1.model_dump_json() == g2.model_dump_json()       # deterministic


# ── cites edges (spec 004 US1) ───────────────────────────────────────────────

def test_cites_edge_plan_to_decision_qualified():
    # a plan (citing kind) cites a qualified decision id held by an adr fragment in another repo
    plan = _kinded_corpus("api", [("plan.md#s", "plan", "Bound by CORE-ADR-001.")])
    core = _kinded_corpus("core", [("adr.md#dec", "adr", "# CORE-ADR-001\nThe write path.")])
    m = _manifest([("api", "spec"), ("core", "spec")])
    edges = dl.discover_adr_edges(m, {"api": plan, "core": core})
    assert len(edges) == 1
    e = edges[0]
    assert e.rel is LinkRel.CITES and e.evidence == "CORE-ADR-001"
    assert e.src.origin == "api" and e.dst.origin == "core"     # plan cites the decision
    assert e.evidence_kind is LinkEvidenceKind.IDENTIFIER


def test_cites_edge_bare_id_qualified_to_namespace():
    # CORE holds a BARE ADR-001; API's plan cites the QUALIFIED CORE-ADR-001 → they resolve
    core = _kinded_corpus("core", [("adr.md#dec", "adr", "# ADR-001\nThe write path.")])
    api = _kinded_corpus("api", [("plan.md#s", "plan", "Bound by CORE-ADR-001.")])
    m = _manifest([("core", "spec"), ("api", "spec")])
    edges = dl.discover_adr_edges(m, {"core": core, "api": api},
                                  namespaces={"core": "CORE", "api": "API"})
    assert len(edges) == 1 and edges[0].rel is LinkRel.CITES
    assert edges[0].evidence == "CORE-ADR-001"
    assert edges[0].dst.origin == "core" and edges[0].src.origin == "api"


def test_bare_id_is_repo_local_no_cross_match():
    # two repos each hold a BARE ADR-001 + a plan citing a bare ADR-001; with distinct
    # namespaces they qualify to CORE-ADR-001 / API-ADR-001 and must NOT cross-match.
    core = _kinded_corpus("core", [("adr.md#d", "adr", "# ADR-001"), ("plan.md#s", "plan", "see ADR-001")])
    api = _kinded_corpus("api", [("adr.md#d", "adr", "# ADR-001"), ("plan.md#s", "plan", "see ADR-001")])
    m = _manifest([("core", "spec"), ("api", "spec")])
    edges = dl.discover_adr_edges(m, {"core": core, "api": api},
                                  namespaces={"core": "CORE", "api": "API"})
    # only intra-repo cites (plan→adr within each repo); never core↔api
    pairs = {(e.src.origin, e.dst.origin) for e in edges}
    assert pairs == {("core", "core"), ("api", "api")}
    assert all(e.evidence in {"CORE-ADR-001", "API-ADR-001"} for e in edges)


def test_qualified_id_resolves_cross_repo():
    # the QUALIFIED form is cross-repo-resolvable: API's plan cites CORE-ADR-001 → edge to core
    core = _kinded_corpus("core", [("adr.md#d", "adr", "# CORE-ADR-001")])
    api = _kinded_corpus("api", [("plan.md#s", "plan", "Bound by CORE-ADR-001.")])
    m = _manifest([("core", "spec"), ("api", "spec")])
    edges = dl.discover_adr_edges(m, {"core": core, "api": api},
                                  namespaces={"core": "CORE", "api": "API"})
    assert len(edges) == 1
    assert (edges[0].src.origin, edges[0].dst.origin) == ("api", "core")


def test_bare_id_without_namespace_mints_no_cross_repo_edge():
    # a repo with no configured namespace: its bare ADR-001 stays repo-local, unqualifiable
    core = _kinded_corpus("core", [("adr.md#d", "adr", "# ADR-001")])
    api = _kinded_corpus("api", [("plan.md#s", "plan", "see ADR-001")])
    m = _manifest([("core", "spec"), ("api", "spec")])
    edges = dl.discover_adr_edges(m, {"core": core, "api": api}, namespaces={})
    assert edges == []                                            # nothing qualifies, no edge


def test_adr_cross_reference_does_not_make_file_a_false_target():
    # B2: ADR-002's file references ADR-018 in its Consequences; a spec also mentions ADR-018.
    # Co-mention ≠ citation — the spec must NOT 'cite' the ADR-002 file as if it were ADR-018.
    # (Here no real ADR-018 file exists, so nothing should resolve.)
    corpus = _kinded_corpus("core", [
        ("adr/ADR-002.md#h", "adr", "# CORE-ADR-002: Event bus\nThe decision."),
        ("adr/ADR-002.md#cons", "adr", "## Consequences\nThis supersedes CORE-ADR-018."),
        ("003/spec.md#s", "spec", "Our core obeys CORE-ADR-018."),
    ])
    m = _manifest([("core", "spec")])
    edges = dl.discover_adr_edges(m, {"core": corpus})
    assert all("ADR-002" not in e.dst.locator for e in edges)   # no false target via co-mention
    assert edges == []                                          # ADR-018 has no decision file → no cite


def test_real_decision_cited_even_when_another_adr_cross_references_it():
    # B2 (representative correctness): when a real ADR-018 file DOES exist, the cite must resolve to
    # it — not to the ADR-002 file that merely cross-references ADR-018 (which sorts earlier).
    corpus = _kinded_corpus("core", [
        ("adr/ADR-002.md#h", "adr", "# CORE-ADR-002: Event bus\nThe decision."),
        ("adr/ADR-002.md#cons", "adr", "## Consequences\nSupersedes CORE-ADR-018."),
        ("adr/ADR-018.md#h", "adr", "# CORE-ADR-018: Legacy queue\nThe decision."),
        ("003/spec.md#s", "spec", "Our core obeys CORE-ADR-018."),
    ])
    m = _manifest([("core", "spec")])
    edges = dl.discover_adr_edges(m, {"core": corpus})
    assert len(edges) == 1
    e = edges[0]
    assert e.rel is LinkRel.CITES and e.evidence == "CORE-ADR-018"
    assert "ADR-018" in e.dst.locator and "ADR-002" not in e.dst.locator


def test_generic_doc_mentioning_adr_id_mints_no_cite():
    # a non-citing kind (design-doc) mentioning an ADR id never mints a citation
    doc = _kinded_corpus("guide", [("g.md#x", "design-doc", "We follow CORE-ADR-001 broadly.")])
    core = _kinded_corpus("core", [("adr.md#d", "adr", "# CORE-ADR-001")])
    m = _manifest([("guide", "docs"), ("core", "spec")])
    assert dl.discover_adr_edges(m, {"guide": doc, "core": core}) == []
