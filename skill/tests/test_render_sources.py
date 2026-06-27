"""Tests for the drill-to-source read surface (spec 003-source-views)."""

import base64
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import render_sources as RS  # noqa: E402
from schema import Fragment, FragmentCorpus, SourceRef, SourceType  # noqa: E402


def _frag(locator: str, text: str, kind: str = "spec") -> Fragment:
    return Fragment(id=locator, kind=kind, text=text,
                    source=SourceRef(type=SourceType.SPEC, name=locator, locator=locator))


def _corpus(*frags: Fragment) -> FragmentCorpus:
    return FragmentCorpus(project_name="Test", fragments=list(frags))


def _decode_blob(page_html: str) -> str:
    m = re.search(r'data-md="([^"]*)"', page_html)
    assert m, "no embedded markdown blob"
    return base64.b64decode(m.group(1)).decode("utf-8")


CORPUS = _corpus(
    _frag("001-x/spec.md#overview", "# Overview\n\nThe system does X."),
    _frag("001-x/spec.md#detail", "## Detail\n\nMore on X."),
    _frag("001-x/plan.md#plan", "# Plan\n\nBuild X with Y.", kind="plan"),
    _frag("002-y/adr-001.md#decision", "# ADR-001\n\nWe chose Z.", kind="adr"),
)


def test_one_page_per_file():
    pages = RS.render_source_pages(CORPUS)
    assert set(pages) == {"001-x-spec.md.html", "001-x-plan.md.html", "002-y-adr-001.md.html"}


def test_content_and_anchors_are_bundled():
    pages = RS.render_source_pages(CORPUS)
    blob = _decode_blob(pages["001-x-spec.md.html"])
    # both sections' text present (FR-002, copied INTO html) ...
    assert "The system does X." in blob and "More on X." in blob
    # ... each behind its locator anchor (FR-003)
    assert 'id="overview"' in blob and 'id="detail"' in blob


def test_no_content_lost():
    pages = RS.render_source_pages(CORPUS)
    for f in CORPUS.fragments:
        file = RS._loc_parts(f.id)[0]
        blob = _decode_blob(pages[f"{RS._safe(file)}.html"])
        assert f.text.split("\n\n", 1)[-1].strip()[:20] in blob  # the body text made it in


def test_page_is_self_contained_shell():
    page = RS.render_source_pages(CORPUS)["001-x-spec.md.html"]
    assert "markdown-it" in page and "mermaid" in page          # the CDN renderer (FR-006)
    assert "--paper" in page or "grain" in page                 # design-system shell
    assert "<noscript>" in page                                  # readable raw fallback offline
    assert "001-x/spec.md" in page                               # the file is titled


def test_single_repo_resolver():
    r = RS.build_source_resolver(CORPUS)
    ref = SourceRef(type=SourceType.SPEC, name="x", locator="001-x/spec.md#detail")
    assert r(ref) == "sources/001-x-spec.md.html#detail"
    assert r(SourceRef(type=SourceType.SPEC, name="?", locator="zzz/none.md#x")) is None


def test_workspace_resolver_drills_cross_repo():
    docs = _corpus(_frag("docs::g/spec.md#s", "doc spec"))
    backend = _corpus(_frag("backend::svc/plan.md#p", "be plan", kind="plan"))
    r = RS.build_workspace_source_resolver({"docs": docs, "backend": backend})
    # a citation into the docs member ...
    assert r(SourceRef(type=SourceType.SPEC, name="s", locator="docs::g/spec.md#s")) == "sources/docs/g-spec.md.html#s"
    # ... and a cross-repo citation into the backend member resolve to their own source views
    assert r(SourceRef(type=SourceType.SPEC, name="p", locator="backend::svc/plan.md#p")) == "sources/backend/svc-plan.md.html#p"
    # unknown member / file → None
    assert r(SourceRef(type=SourceType.SPEC, name="?", locator="ghost::a/b.md#c")) is None


def test_compose_resolvers_first_non_none_wins():
    r = RS.compose_resolvers(lambda ref: None, lambda ref: "X.html#a", lambda ref: "Y.html")
    assert r(SourceRef(type=SourceType.SPEC, name="n", locator="a#b")) == "X.html#a"
    assert RS.compose_resolvers(lambda ref: None)(SourceRef(type=SourceType.SPEC, name="n", locator="a#b")) is None


def test_deterministic():
    assert RS.render_source_pages(CORPUS) == RS.render_source_pages(CORPUS)


def test_source_page_header_shows_category_band_and_label():
    # spec 011 US2: a drilled source page header carries its source-type band + explicit label,
    # derived from the fragment kind; an unrecognised kind falls back to a neutral default.
    corpus = _corpus(
        _frag("001-a/spec.md#x", "# A\n\nx", kind="spec"),
        _frag("001-a/plan.md#x", "# P\n\nx", kind="plan"),
        _frag("002-b/ADR-001.md#x", "# D\n\nx", kind="adr"),
        _frag("003-c/notes.md#x", "# N\n\nx", kind="design-doc"),
        _frag("004-d/mystery.md#x", "# M\n\nx", kind="weird-kind"),
    )
    pages = RS.render_source_pages(corpus)
    assert "srctype spec" in pages["001-a-spec.md.html"] and "Spec" in pages["001-a-spec.md.html"]
    assert "srctype plan" in pages["001-a-plan.md.html"] and "Plan" in pages["001-a-plan.md.html"]
    assert "srctype adr" in pages["002-b-ADR-001.md.html"]
    assert "srctype narrative" in pages["003-c-notes.md.html"]
    assert "srctype source" in pages["004-d-mystery.md.html"]   # neutral default, never blank
