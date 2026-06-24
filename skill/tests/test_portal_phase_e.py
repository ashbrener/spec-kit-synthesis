"""Tests for the portal Phase E (spec 002): verify_links gate, chip cross-repo resolver, atlas."""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import render as render_mod  # noqa: E402
import synthesize_atlas as atlas  # noqa: E402
import verify_links as vl  # noqa: E402
from schema import (Altitude, Block, BlockType, DocumentModel, Fragment, FragmentCorpus,  # noqa: E402
                    LinkEdge, LinkEndpoint, LinkEvidenceKind, LinkGraph, LinkRel, Section,
                    SourceRef, SourceType, WorkspaceManifest, WorkspaceMember)


def _edge(so, sl, do, dl, rel, kind, ev):
    return LinkEdge(src=LinkEndpoint(origin=so, locator=sl), dst=LinkEndpoint(origin=do, locator=dl),
                    rel=rel, evidence_kind=kind, evidence=ev)


# ── verify_links gate (fail-closed) ──────────────────────────────────────────

def test_clean_identifier_edge_passes():
    g = LinkGraph(edges=[_edge("be", "be::c#r", "specs", "specs::s#fr", LinkRel.IMPLEMENTS,
                               LinkEvidenceKind.IDENTIFIER, "FR-025")])
    frag = {"be::c#r": "FR-025 implemented", "specs::s#fr": "FR-025 — the rule"}
    assert vl.verify_links(g, frag) == []


def test_dangling_endpoint_fails():
    g = LinkGraph(edges=[_edge("be", "be::missing", "specs", "specs::s#fr", LinkRel.IMPLEMENTS,
                               LinkEvidenceKind.IDENTIFIER, "FR-025")])
    vios = vl.verify_links(g, {"specs::s#fr": "FR-025"})
    assert any(v.check == vl.CHECK_ENDPOINTS_RESOLVE for v in vios)


def test_ungrounded_identifier_fails():
    g = LinkGraph(edges=[_edge("be", "be::c", "specs", "specs::s", LinkRel.IMPLEMENTS,
                               LinkEvidenceKind.IDENTIFIER, "FR-025")])
    vios = vl.verify_links(g, {"be::c": "FR-025 here", "specs::s": "no token here"})
    assert any(v.check == vl.CHECK_EVIDENCE_GROUNDED for v in vios)


def test_qualified_adr_evidence_grounded_by_bare_form_in_text():
    # B1: discovery stores the QUALIFIED ADR id as the edge evidence, but an intra-repo source
    # text often holds only the bare ADR-NNN. The gate must treat the bare form as grounding the
    # qualified evidence — else it rejects ADR cites edges discovery legitimately created
    # (fail-closed → no portal). The qualified id and its bare suffix denote the same decision.
    g = LinkGraph(edges=[_edge("core", "core::plan.md#s", "core", "core::adr/ADR-009.md#d",
                               LinkRel.CITES, LinkEvidenceKind.IDENTIFIER, "CORE-ADR-009")])
    frag = {"core::plan.md#s": "Bound by ADR-009.", "core::adr/ADR-009.md#d": "# ADR-009\nThe decision."}
    assert vl.verify_links(g, frag) == []


def test_adr_edge_still_ungrounded_when_no_adr_id_present():
    # guard: bare-form acceptance must not weaken fabrication detection — an ADR cites edge whose
    # endpoints mention no ADR id at all is still rejected.
    g = LinkGraph(edges=[_edge("core", "core::plan.md#s", "core", "core::adr/x.md#d",
                               LinkRel.CITES, LinkEvidenceKind.IDENTIFIER, "CORE-ADR-009")])
    frag = {"core::plan.md#s": "no decision cited here", "core::adr/x.md#d": "unrelated prose"}
    assert any(v.check == vl.CHECK_EVIDENCE_GROUNDED for v in vl.verify_links(g, frag))


def test_empty_evidence_fails():
    g = LinkGraph(edges=[_edge("a", "a::x", "b", "b::y", LinkRel.REFERENCES, LinkEvidenceKind.PROSE, "")])
    vios = vl.verify_links(g, {"a::x": "...", "b::y": "..."})
    assert any(v.check == vl.CHECK_EVIDENCE_PRESENT for v in vios)


def test_declared_is_trusted_when_endpoints_resolve():
    g = LinkGraph(edges=[_edge("docs", "docs::o#x", "specs", "specs::s#y", LinkRel.REFERENCES,
                               LinkEvidenceKind.DECLARED, "manifest")])
    assert vl.verify_links(g, {"docs::o#x": "anything", "specs::s#y": "anything"}) == []


def test_verify_links_cli_exit_codes(tmp_path):
    g = LinkGraph(edges=[_edge("be", "be::c", "specs", "specs::s", LinkRel.IMPLEMENTS,
                               LinkEvidenceKind.IDENTIFIER, "FR-025")])
    (tmp_path / "lg.json").write_text(g.model_dump_json(), encoding="utf-8")

    def _frag(fid, txt):
        return Fragment(id=fid, source=SourceRef(type=SourceType.CODE, name=fid, locator=fid), kind="code", text=txt)

    ok = FragmentCorpus(project_name="w", fragments=[_frag("be::c", "FR-025"), _frag("specs::s", "FR-025")])
    (tmp_path / "ok.json").write_text(ok.model_dump_json(), encoding="utf-8")
    assert vl.main([str(tmp_path / "lg.json"), str(tmp_path / "ok.json")]) == 0

    bad = FragmentCorpus(project_name="w", fragments=[_frag("be::c", "FR-025"), _frag("specs::s", "nope")])
    (tmp_path / "bad.json").write_text(bad.model_dump_json(), encoding="utf-8")
    assert vl.main([str(tmp_path / "lg.json"), str(tmp_path / "bad.json")]) == 1


# ── chip cross-repo resolver (render.py seam) ────────────────────────────────

def _one_ref_doc(locator):
    return DocumentModel(title="T", project_name="P", sections=[Section(id="s", number=1, title="S", blocks=[
        Block(type=BlockType.PROSE, altitude=Altitude.FUNCTIONAL, prose="x",
              source_refs=[SourceRef(type=SourceType.SPEC, name="n", locator=locator)])])])


def test_chip_resolver_overrides_and_isolates():
    doc = _one_ref_doc("specs::s#fr")
    out = render_mod.render(doc, {}, resolve=lambda r: "svc.html#ref-1" if r.locator == "specs::s#fr" else None)
    assert 'href="svc.html#ref-1"' in out
    out2 = render_mod.render(doc, {})   # no resolver → in-page anchor; no resolver-state leakage
    assert 'href="svc.html#ref-1"' not in out2 and 'href="#ref-' in out2


# ── atlas + build_site ───────────────────────────────────────────────────────

def _manifest():
    return WorkspaceManifest(title="Portal", project_name="p", members=[
        WorkspaceMember(origin="docs", path="d", adapter="doc", role="docs", title="Docs"),
        WorkspaceMember(origin="specs", path="s", adapter="speckit", role="spec", title="Specs")])


def _graph():
    return LinkGraph(edges=[_edge("docs", "docs::o#x", "specs", "specs::s#y", LinkRel.REFERENCES,
                                  LinkEvidenceKind.IDENTIFIER, "FR-007")])


def test_render_map_links_members_and_is_coverage_honest():
    html = atlas.render_map(_manifest(), _graph())
    assert html.startswith("<!DOCTYPE html>")
    assert 'href="docs.html"' in html and 'href="specs.html"' in html
    assert "references" in html and "FR-007" in html
    assert "partial" in html                                  # docs+spec but no code → honest caveat
    assert atlas.render_map(_manifest(), _graph()) == html  # deterministic


def test_render_map_empty_graph_is_honest():
    assert "No cross-repo links discovered yet" in atlas.render_map(_manifest(), LinkGraph(edges=[]))


def test_build_site_with_graph_adds_atlas_resolver_and_index_link():
    site = atlas.build_site(_manifest(), {"docs": _one_ref_doc("docs::o#x")}, link_graph=_graph())
    assert "map.html" in site
    assert 'href="map.html"' in site["index.html"]          # index links the atlas
    assert 'href="specs.html"' in site["docs.html"]           # chip drills cross-repo to dst page (no corpora → page fallback)


def test_build_site_without_graph_is_unchanged():
    site = atlas.build_site(_manifest(), {"docs": _one_ref_doc("docs::o#x")})
    assert "map.html" not in site
    assert 'href="map.html"' not in site["index.html"]


def test_build_site_with_corpora_drills_to_bundled_source():
    import base64
    import re
    docs_corpus = FragmentCorpus(project_name="d", fragments=[
        Fragment(id="docs::o#x", kind="spec", text="# Heading\n\nReal source content.",
                 source=SourceRef(type=SourceType.DESIGN_DOC, name="o", locator="docs::o#x"))])
    site = atlas.build_site(_manifest(), {"docs": _one_ref_doc("docs::o#x")},
                            {"docs": docs_corpus}, link_graph=_graph())
    assert "sources/docs/o.html" in site                              # bundled source page emitted
    assert 'href="sources/docs/o.html#x"' in site["docs.html"]        # chip drills to source content (primary over page-link)
    blob = base64.b64decode(re.search(r'data-md="([^"]*)"', site["sources/docs/o.html"]).group(1)).decode()
    assert "Real source content." in blob                            # the actual source is copied INTO the html
