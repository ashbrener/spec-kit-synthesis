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


def test_docs_specified_by_spec():
    docs = _corpus("guide", [("g.md#x", "This behaviour is required by FR-007.")])
    specs = _corpus("specs", [("s.md#fr7", "FR-007 — the rule.")])
    m = _manifest([("guide", "docs"), ("specs", "spec")])
    edges = dl.discover_identifier_edges(m, {"guide": docs, "specs": specs})
    assert len(edges) == 1 and edges[0].rel is LinkRel.SPECIFIED_BY
    assert edges[0].src.origin == "guide" and edges[0].dst.origin == "specs"


def test_no_edge_when_identifier_not_shared():
    specs = _corpus("specs", [("s#a", "FR-001 only here")])
    code = _corpus("be", [("c#a", "FR-999 only here")])
    m = _manifest([("specs", "spec"), ("be", "code")])
    assert dl.discover_identifier_edges(m, {"specs": specs, "be": code}) == []


def test_declared_edges_are_namespaced_and_trusted():
    m = _manifest([("docs", "docs"), ("specs", "spec")],
                  links=[DeclaredLink(src_origin="docs", src_locator="overview.md#x",
                                      dst_origin="specs", dst_locator="spec.md#y", rel=LinkRel.SPECIFIED_BY)])
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
