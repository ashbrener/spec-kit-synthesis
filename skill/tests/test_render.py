"""Golden test for the deterministic renderer.

Asserts STRUCTURAL + BEHAVIOURAL invariants (not byte-equality with the north-star):
the document model renders to valid HTML carrying the depth control, theme toggle,
progressive-disclosure tiers, source-typed citation chips, balanced interactive SVG,
and is fully deterministic. Also checks that a --theme override reaches the output.
"""

import json
from html.parser import HTMLParser
from pathlib import Path

from schema import DocumentModel

from render import DEFAULT_THEME, render

FIXTURE = Path(__file__).parent / "fixtures" / "document_model.json"


def _doc() -> DocumentModel:
    return DocumentModel.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


# ── fixture validity ─────────────────────────────────────────────────────────

def test_fixture_validates_against_schema():
    doc = _doc()
    assert doc.title
    assert len(doc.sections) >= 3
    block_types = {b.type.value for s in doc.sections for b in s.blocks}
    assert {"prose", "table", "callout", "diagram"} <= block_types
    layouts = {b.diagram.layout for s in doc.sections for b in s.blocks if b.diagram}
    assert len(layouts) >= 2
    altitudes = {b.altitude.value for s in doc.sections for b in s.blocks}
    assert {"functional", "technical"} <= altitudes
    ref_types = {r.type.value for s in doc.sections for b in s.blocks for r in b.source_refs}
    assert {"spec", "code"} <= ref_types


# ── HTML well-formedness ─────────────────────────────────────────────────────

class _Collector(HTMLParser):
    """Collects tag/attr structure and tracks SVG tag balance."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.attrs_by_tag: dict[str, list[dict]] = {}
        self.svg_open = 0
        self.svg_close = 0
        self._svg_stack: list[str] = []
        self.svg_balanced = True

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self.attrs_by_tag.setdefault(tag, []).append(d)
        if tag == "svg":
            self.svg_open += 1
            self._svg_stack.append(tag)
        elif self._svg_stack:
            self._svg_stack.append(tag)

    def handle_endtag(self, tag):
        if tag == "svg":
            self.svg_close += 1
        if self._svg_stack:
            # pop until matching (tolerant of void-ish svg children which are all closed)
            if self._svg_stack and self._svg_stack[-1] == tag:
                self._svg_stack.pop()
            elif tag in self._svg_stack:
                # unwind
                while self._svg_stack and self._svg_stack.pop() != tag:
                    pass


def _parse(html_text: str) -> _Collector:
    c = _Collector()
    c.feed(html_text)
    return c


def test_output_parses_as_html():
    out = render(_doc(), {})
    c = _parse(out)
    assert "html" in c.attrs_by_tag
    assert "head" in c.attrs_by_tag
    assert "body" in c.attrs_by_tag
    assert out.startswith("<!DOCTYPE html>")


def test_depth_control_present():
    out = render(_doc(), {})
    assert 'class="seg depth"' in out
    assert 'data-depth="0"' in out  # initial html attribute
    # the three depth buttons
    for d in ("0", "1", "2"):
        assert f'data-d="{d}"' in out


def test_theme_toggle_present():
    out = render(_doc(), {})
    assert 'id="themeBtn"' in out
    assert "localStorage" in out
    assert 'localStorage.setItem("arch-theme"' in out


def test_progress_and_scrollspy_present():
    out = render(_doc(), {})
    assert 'id="progress"' in out
    assert 'nav class="toc"' in out
    assert "IntersectionObserver" in out
    assert "prefers-reduced-motion" in out


def test_progressive_disclosure_tiers():
    out = render(_doc(), {})
    assert 'class="tier tier1"' in out      # Layer-1 technical wrapper
    assert 'class="tier tier2"' in out      # Layer-2 citation strip
    assert 'data-depth="1"] .tier1' in out  # CSS reveal rule
    assert 'data-depth="2"] .tier2' in out


def test_citation_chips_are_source_typed():
    out = render(_doc(), {})
    assert 'class="cite" data-t="spec"' in out
    assert 'class="cite" data-t="code"' in out
    assert "Backed by" in out


def test_diagrams_render_as_balanced_svg():
    out = render(_doc(), {})
    c = _parse(out)
    assert c.svg_open >= 2          # at least two diagram SVGs (plus the theme icon)
    assert c.svg_open == c.svg_close  # balanced open/close


def test_diagram_layouts_exercised():
    out = render(_doc(), {})
    # pipeline + ladder + flow figures all produce figure shells with captions
    assert out.count('<figure class="fig">') >= 3
    assert 'data-cap=' in out       # hover-to-explain
    assert 'data-target="#' in out  # click-to-jump


def test_callout_kinds_styled():
    out = render(_doc(), {})
    assert 'class="box decision"' in out
    assert 'class="box unspec"' in out
    assert 'class="box hist"' in out


def test_no_raw_source_locators_in_narrative_body():
    """The narrative body must not leak machine locators (DESIGN §11.3 #3).

    Citations live only in chip titles/labels; the renderer never injects a
    locator into prose. We assert the fixture's machine locators don't appear
    as bare text in <p>/<td> body content.
    """
    out = render(_doc(), {})
    doc = _doc()
    locators = {r.locator for s in doc.sections for b in s.blocks for r in b.source_refs}
    # locators are like "spec-001#overview" — these should never be emitted at all,
    # since the renderer only ever uses ref.name / ref.anchor, not ref.locator.
    for loc in locators:
        assert loc not in out, f"machine locator leaked into output: {loc}"


# ── determinism ──────────────────────────────────────────────────────────────

def test_render_is_deterministic():
    doc = _doc()
    a = render(doc, {})
    b = render(doc, {})
    assert a == b
    assert a.encode("utf-8") == b.encode("utf-8")


def test_no_timestamps_or_randomness():
    # Two independent loads → identical bytes (no clock, no rng).
    a = render(_doc(), {})
    b = render(_doc(), {})
    assert a == b


# ── theme override ───────────────────────────────────────────────────────────

def test_custom_theme_overrides_token():
    custom = {"accent": "#ff00aa", "paper": "#000102"}
    out = render(_doc(), custom)
    assert "--accent: #ff00aa;" in out
    assert "--paper: #000102;" in out
    # untouched tokens keep their default
    assert f"--ink: {DEFAULT_THEME['ink']};" in out


def test_default_theme_when_no_override():
    out = render(_doc(), {})
    assert f"--accent: {DEFAULT_THEME['accent']};" in out


def test_theme_dict_loaded_from_json_roundtrips(tmp_path):
    theme_file = tmp_path / "theme.json"
    theme_file.write_text(json.dumps({"accent": "#123456"}), encoding="utf-8")
    loaded = json.loads(theme_file.read_text(encoding="utf-8"))
    out = render(_doc(), loaded)
    assert "--accent: #123456;" in out


# ── escaping ─────────────────────────────────────────────────────────────────

def test_text_is_html_escaped():
    doc = _doc()
    # inject a hostile string into a section title and confirm it is escaped
    doc.sections[0].title = '<script>alert("x")</script> & more'
    out = render(doc, {})
    assert "<script>alert" not in out
    assert "&lt;script&gt;alert" in out
    assert "&amp; more" in out


def test_mapping_and_panel_layouts_render_distinctly():
    """mapping + panel are now hand-laid (no longer silent flow fallbacks)."""
    import render as render_mod
    from schema import (Altitude, Block, BlockType, DiagramEdge, DiagramGraph,
                        DiagramNode, DocumentModel, Section)

    mapping = DiagramGraph(layout="mapping",
        nodes=[DiagramNode(id="repo", label="repository"), DiagramNode(id="proj", label="Project"),
               DiagramNode(id="spec", label="spec"), DiagramNode(id="issue", label="Issue")],
        edges=[DiagramEdge(src="repo", dst="proj"), DiagramEdge(src="spec", dst="issue", emphasis=True)])
    panel = DiagramGraph(layout="panel",
        nodes=[DiagramNode(id="a", label="parser", caption="reads specs"),
               DiagramNode(id="b", label="reconcile"), DiagramNode(id="c", label="render"),
               DiagramNode(id="d", label="verify"), DiagramNode(id="e", label="adapter")])
    doc = DocumentModel(title="Demo", sections=[Section(id="s", number=1, title="Diagrams", blocks=[
        Block(type=BlockType.DIAGRAM, altitude=Altitude.FUNCTIONAL, diagram=mapping),
        Block(type=BlockType.DIAGRAM, altitude=Altitude.FUNCTIONAL, diagram=panel),
    ])])
    html = render_mod.render(doc, render_mod.DEFAULT_THEME)
    # mapping draws FROM/TO column labels; panel labels each card
    assert "FROM" in html and "TO" in html
    assert "repository" in html and "Project" in html
    assert "parser" in html and "reads specs" in html
    # balanced svg tags (the page also carries the theme-toggle icon svg)
    assert html.count("<svg") == html.count("</svg>")
    # both diagrams rendered as figures
    assert html.count("<figure") == 2

def test_mapping_panel_are_registered_not_flow_fallback():
    """mapping + panel must be their own layouts, not the flow fallback."""
    import render as render_mod
    assert render_mod._LAYOUTS.get("mapping") is render_mod._layout_mapping
    assert render_mod._LAYOUTS.get("panel") is render_mod._layout_panel
