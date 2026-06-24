"""Tests for the portal orchestrator (synthesize_atlas.py — spec 002, Phase C).

Covers: manifest load, per-member adapter fan-out with origin-stamping (cross-repo
collisions vanish), and deterministic index + site rendering.
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import synthesize_atlas as atlas  # noqa: E402
from schema import (Altitude, Block, BlockType, DocumentModel, Section,  # noqa: E402
                    SourceRef, SourceType, WorkspaceManifest)

FIX = Path(__file__).parent / "fixtures" / "workspace"
MANIFEST = FIX / "atlas.workspace.json"


def test_load_manifest():
    m = atlas.load_manifest(MANIFEST)
    assert isinstance(m, WorkspaceManifest)
    assert m.title == "Demo Portal"
    assert {mm.origin for mm in m.members} == {"guide", "svc-a", "svc-b"}
    assert {mm.adapter for mm in m.members} == {"doc", "code"}


def test_member_fanout_namespaces_and_avoids_collision(tmp_path):
    m = atlas.load_manifest(MANIFEST)
    by = {mm.origin: mm for mm in m.members}
    a = atlas.build_member_corpus(by["svc-a"], FIX, tmp_path)
    b = atlas.build_member_corpus(by["svc-b"], FIX, tmp_path)
    assert a.fragments and b.fragments
    # both services have a main.py; origin-stamping makes their locators disjoint
    assert all(f.id.startswith("svc-a::") for f in a.fragments)
    assert all(f.id.startswith("svc-b::") for f in b.fragments)
    assert a.locators().isdisjoint(b.locators()), "cross-repo locator collision not prevented"
    assert all(f.source.origin == "svc-a" for f in a.fragments)


def test_doc_member_adapts(tmp_path):
    m = atlas.load_manifest(MANIFEST)
    guide = next(mm for mm in m.members if mm.origin == "guide")
    c = atlas.build_member_corpus(guide, FIX, tmp_path)
    assert c.fragments
    assert all(f.id.startswith("guide::") for f in c.fragments)


def test_render_index_links_every_member_deterministic():
    m = atlas.load_manifest(MANIFEST)
    html = atlas.render_index(m)
    assert html.startswith("<!DOCTYPE html>")
    assert "Demo Portal" in html
    for fn in ("guide.html", "svc-a.html", "svc-b.html"):
        assert f'href="{fn}"' in html
    assert 'class="role docs"' in html and 'class="role code"' in html  # role badges
    assert "ingestion service" in html                                   # member description
    assert atlas.render_index(m) == html                                 # deterministic


def _doc(title):
    return DocumentModel(title=title, project_name=title.lower(), sections=[
        Section(id="s", number=1, title="S", blocks=[
            Block(type=BlockType.PROSE, altitude=Altitude.FUNCTIONAL, prose="hi",
                  source_refs=[SourceRef(type=SourceType.SPEC, name="x", locator="l")])])])


def test_build_site_emits_pages_and_index():
    m = atlas.load_manifest(MANIFEST)
    models = {"guide": _doc("Guide"), "svc-a": _doc("Service A")}
    site = atlas.build_site(m, models)
    # the index, plus the members that have a document model; svc-b (no model) is omitted
    assert set(site) == {"index.html", "guide.html", "svc-a.html"}
    assert site["guide.html"].startswith("<!DOCTYPE html>")
    assert "svc-b.html" not in site
    assert atlas.build_site(m, dict(models)) == site            # deterministic
