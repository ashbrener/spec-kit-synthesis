"""Melded site assembly (synthesize_atlas.build_meld_site — spec 006, US1).

Asserts the portal is ONE melded page + drill-to-source, with no per-repo storybooks and no edge-list
atlas. Neutral examples only (CORE / API / WEB).
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import synthesize_atlas as sa  # noqa: E402
from schema import (Altitude, Block, BlockType, DocumentModel, Fragment, FragmentCorpus,  # noqa: E402
                    Section, SourceRef, SourceType)
from source_index import SourceTitle  # noqa: E402


def _frag(origin, locator, text):
    fid = f"{origin}::{locator}"
    return Fragment(id=fid, kind="spec", feature_key="auth", text=text,
                    source=SourceRef(type=SourceType.SPEC, origin=origin, name=locator, locator=fid))


def _corpora():
    return {
        "docs": FragmentCorpus(project_name="docs", fragments=[_frag("docs", "auth/spec.md", "# Authentication\nbody")]),
        "backend": FragmentCorpus(project_name="backend", fragments=[_frag("backend", "007-auth/contract.md", "# Auth\napi")]),
    }


def _meld_doc():
    func = Block(type=BlockType.PROSE, prose="Roles & sign-in.", altitude=Altitude.FUNCTIONAL,
                 source_refs=[SourceRef(type=SourceType.SPEC, origin="docs", name="spec.md", locator="docs::auth/spec.md")])
    be = Block(type=BlockType.PROSE, prose="POST /sessions.", altitude=Altitude.TECHNICAL, tier="backend",
               source_refs=[SourceRef(type=SourceType.SPEC, origin="backend", name="contract.md", locator="backend::007-auth/contract.md")])
    return DocumentModel(title="Workspace", sections=[Section(id="auth", number=1, title="Authentication", blocks=[func, be])])


def _titles():
    return {
        "docs::auth/spec.md": SourceTitle(title="Authentication", artifact_kind="spec", repo="docs"),
        "backend::007-auth/contract.md": SourceTitle(title="Authentication System", artifact_kind="contract", repo="backend"),
    }


def test_meld_site_is_one_story_plus_sources_no_perrepo_no_atlas():
    site = sa.build_meld_site(_meld_doc(), _corpora(), _titles(), {})
    assert "index.html" in site                                  # the single melded story
    assert any(k.startswith("sources/docs/") for k in site)      # drill-to-source kept
    assert any(k.startswith("sources/backend/") for k in site)
    # no per-repo storybooks, no edge-list atlas
    assert "docs.html" not in site and "backend.html" not in site
    assert "map.html" not in site
    # the hierarchical source index (tree) replaces the graph
    assert "catalog.html" in site
    assert 'class="ixtree"' in site["catalog.html"]
    assert 'href="catalog.html"' in site["index.html"]   # linked from the story nav


def test_meld_index_weaves_tiers_and_human_titles():
    site = sa.build_meld_site(_meld_doc(), _corpora(), _titles(), {})
    idx = site["index.html"]
    assert "Authentication" in idx                               # capability section
    assert ">Backend<" in idx                                    # per-tier disclosure
    assert "Authentication System" in idx                        # human-titled source (not contract.md)


def test_meld_site_deterministic():
    a = sa.build_meld_site(_meld_doc(), _corpora(), _titles(), {})
    b = sa.build_meld_site(_meld_doc(), _corpora(), _titles(), {})
    assert a == b
