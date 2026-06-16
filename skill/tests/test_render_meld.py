"""Melded render: per-tier disclosures, build-status fading, human-titled source tables, new diagram
layouts (render.py — spec 006, US1/US2/US4).

Neutral examples only (CORE / API / WEB).
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import render as r  # noqa: E402
from schema import (Altitude, Block, BlockType, DiagramGraph, DiagramNode, DiagramEdge,  # noqa: E402
                    DocumentModel, Section, SourceRef, SourceType)
from source_index import SourceTitle  # noqa: E402


def _ref(origin, locator):
    return SourceRef(type=SourceType.SPEC, origin=origin, name=locator.split("/")[-1],
                     locator=f"{origin}::{locator}")


def _doc():
    func = Block(type=BlockType.PROSE, prose="Four roles, default-deny.", altitude=Altitude.FUNCTIONAL,
                 source_refs=[_ref("docs", "auth/spec.md")])
    be = Block(type=BlockType.PROSE, prose="POST /sessions returns a token.", altitude=Altitude.TECHNICAL,
               tier="backend", build_status="built", source_refs=[_ref("backend", "007-auth/contract.md")])
    be_tbl = Block(type=BlockType.TABLE, table=[["Endpoint", "Method"], ["/sessions", "POST"]],
                   altitude=Altitude.TECHNICAL, tier="backend")
    fe = Block(type=BlockType.PROSE, prose="The loader calls the API.", altitude=Altitude.TECHNICAL,
               tier="frontend", build_status="planned", source_refs=[_ref("frontend", "002-auth/spec.md")])
    seq = Block(type=BlockType.DIAGRAM, altitude=Altitude.FUNCTIONAL,
                diagram=DiagramGraph(layout="sequence", title="Sign-in",
                                     nodes=[DiagramNode(id="c", label="Client"), DiagramNode(id="a", label="API"),
                                            DiagramNode(id="d", label="DB")],
                                     edges=[DiagramEdge(src="c", dst="a", label="POST"), DiagramEdge(src="a", dst="d")]))
    erd = Block(type=BlockType.DIAGRAM, altitude=Altitude.TECHNICAL, tier="backend",
                diagram=DiagramGraph(layout="erd", nodes=[DiagramNode(id="u", label="User"), DiagramNode(id="s", label="Session")],
                                     edges=[DiagramEdge(src="u", dst="s", label="has")]))
    sec = Section(id="auth", number=2, title="Authentication", strap="Identity", subtitle="Sign-in & roles.",
                  build_status="partial", blocks=[func, seq, be, be_tbl, erd, fe])
    return DocumentModel(title="Workspace", sections=[sec])


def _titles():
    return {
        "docs::auth/spec.md": SourceTitle(title="Authentication", artifact_kind="spec", repo="docs"),
        "backend::007-auth/contract.md": SourceTitle(title="Authentication System", artifact_kind="contract", repo="backend"),
        "frontend::002-auth/spec.md": SourceTitle(title="Auth Wiring", artifact_kind="spec", repo="frontend"),
    }


def test_per_tier_disclosures_labeled():
    out = r.render(_doc(), {}, titles=_titles())
    assert 'class="mod tier-mod' in out
    assert ">Backend<" in out and ">Frontend<" in out          # per-tier labels
    # functional prose is inline (outside any details)
    assert "Four roles, default-deny." in out.split("<details")[0]


def test_planned_tier_is_faded_built_is_solid():
    out = r.render(_doc(), {}, titles=_titles())
    assert "tier-mod planned" in out                            # the frontend (planned) tier
    assert 'class="bstatus bs-planned">Planned' in out
    assert 'bs-built">Built' in out and 'bs-partial">Partial' in out  # section + backend grades


def test_human_titled_source_table_not_filenames():
    out = r.render(_doc(), {}, titles=_titles())
    assert 'class="tbl srctbl"' in out
    assert "Authentication System" in out                       # human title, not "contract.md"
    assert "<th>Repo</th>" in out


def test_sources_fall_back_to_chips_without_titles():
    # the single-repo storybook passes no title map → the chip line, unchanged
    out = r.render(_doc(), {})
    assert 'class="tbl srctbl"' not in out      # no source TABLE element emitted
    assert 'class="srcline"' in out             # the legacy chip line instead


def test_new_diagram_layouts_render():
    out = r.render(_doc(), {}, titles=_titles())
    assert "fig-sequence" in out and "fig-erd" in out           # both new layouts present
    assert "<svg" in out
    # the REAL layouts ran (not the flow fallback): sequence draws dashed lifelines, erd a grid
    assert 'stroke-dasharray="4 5"' in out                      # sequence lifelines
    assert "Client" in out and "API" in out and "User" in out  # participants + entities
    assert "anim" in out                                        # staggered reveal hooks


def test_nested_nav_lists_tiers_and_catalog():
    out = r.render(_doc(), {}, titles=_titles(), catalog_href="catalog.html")
    assert 'class="toc-tier"' in out                            # per-tier sub-links (Backend/Frontend)
    assert 'class="toc-catalog"' in out and 'href="catalog.html"' in out
