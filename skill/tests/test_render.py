"""Golden test for the deterministic renderer v2 (editorial design system, spec 001).

Asserts STRUCTURAL + BEHAVIOURAL invariants (not byte-equality with the contract):
the document model renders to valid HTML carrying the editorial masthead, sticky TOC,
per-section disclosure (no global depth toggle), source-typed citation chips + a
References appendix, eight hand-laid diagram layouts each with its OWN motion grammar,
light-only theming, and full determinism. Also checks the --theme override reaches output.
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
    assert doc.project_name
    assert doc.title_accent and doc.title_accent in doc.title
    assert doc.kicker and len(doc.kicker) >= 1
    assert doc.meta and all(m.label and m.value for m in doc.meta)
    assert len(doc.sections) >= 4
    assert any(s.strap for s in doc.sections)
    block_types = {b.type.value for s in doc.sections for b in s.blocks}
    assert {"prose", "table", "callout", "diagram"} <= block_types
    layouts = {b.diagram.layout for s in doc.sections for b in s.blocks if b.diagram}
    assert {"pipeline", "ladder", "flow", "hub", "stack", "timeline"} <= layouts
    altitudes = {b.altitude.value for s in doc.sections for b in s.blocks}
    assert {"functional", "technical"} <= altitudes
    ref_types = {r.type.value for s in doc.sections for b in s.blocks for r in b.source_refs}
    assert {"spec", "code", "design_doc"} <= ref_types
    assert any(b.prose_style == "pull" for s in doc.sections for b in s.blocks)


# ── HTML well-formedness ─────────────────────────────────────────────────────

class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.attrs_by_tag: dict[str, list[dict]] = {}
        self.svg_open = 0
        self.svg_close = 0

    def handle_starttag(self, tag, attrs):
        self.attrs_by_tag.setdefault(tag, []).append(dict(attrs))
        if tag == "svg":
            self.svg_open += 1

    def handle_endtag(self, tag):
        if tag == "svg":
            self.svg_close += 1


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


# ── masthead ─────────────────────────────────────────────────────────────────

def test_masthead_present():
    out = render(_doc(), {})
    assert 'header class="mast"' in out
    assert 'class="kicker"' in out
    assert "<span>Architecture Storybook</span>" in out
    assert 'class="dek"' in out                       # lede → dek
    assert 'class="meta-row"' in out
    assert "<em>Linear Bridge</em>" in out            # title_accent
    assert out.count("speckit-linear") >= 2           # brand wordmark (masthead + nav)
    assert 'class="brand-logo"' in out and 'class="brand-mark"' in out


# ── nav / TOC ────────────────────────────────────────────────────────────────

def test_sticky_nav_one_link_per_section():
    doc = _doc()
    out = render(doc, {})
    assert 'nav class="toc"' in out
    assert 'id="toclinks"' in out and 'id="navbtn"' in out and 'id="navcur"' in out
    for s in doc.sections:
        assert f'href="#{s.id}"' in out
    # scrollspy + hamburger machinery is present in JS
    assert "IntersectionObserver" in out
    assert "addEventListener" in out


# ── sections, straps, leads, pull-quotes ─────────────────────────────────────

def test_section_anatomy():
    out = render(_doc(), {})
    assert 'class="sec-num"' in out
    assert "— The picture in one read" in out          # strap on §01
    assert 'class="lead"' in out                        # subtitle → lead
    assert 'class="pull"' in out                        # pull-quote block
    assert '<hr class="divider">' in out                # dividers between sections


# ── per-section disclosure (NOT a global depth toggle) ───────────────────────

def test_per_section_disclosure():
    out = render(_doc(), {})
    assert '<details class="mod"' in out
    assert "Technical detail" in out
    assert 'id="bigpicture-tech"' in out                # technical block tucked per-section
    # keyboard expand/collapse-all
    assert "details.mod" in out


def test_light_only_no_global_depth_or_theme_toggle():
    out = render(_doc(), {})
    for forbidden in ('data-theme', 'data-depth', 'themeBtn', 'seg depth',
                      'Reading depth', 'arch-depth'):
        assert forbidden not in out, f"renderer v2 must not emit {forbidden!r}"
    assert 'name="color-scheme" content="light only"' in out


# ── citations: inline chips + References appendix ────────────────────────────

def test_citation_chips_are_source_typed():
    out = render(_doc(), {})
    assert 'class="srcline"' in out
    assert 'class="cite-t spec"' in out
    assert 'class="cite-t code"' in out
    assert 'class="cite-t narrative"' in out                  # design_doc source present (narrative)


def test_references_appendix_and_colophon():
    out = render(_doc(), {})
    assert 'id="refs"' in out
    assert 'class="reflist"' in out
    assert 'class="reftype spec"' in out
    assert 'class="colophon"' in out
    assert "fail-closed · 6 checks" in out
    # the tool credits itself with a repo hyperlink (fixed chrome)
    assert 'href="https://github.com/ashbrener/spec-kit-atlas"' in out
    assert 'target="_blank"' in out


# ── diagrams: eight layouts, balanced SVG, interactivity ─────────────────────

def test_diagrams_render_balanced_svg():
    out = render(_doc(), {})
    c = _parse(out)
    assert c.svg_open >= 6                              # ≥6 diagram SVGs (+ brand glyphs)
    assert c.svg_open == c.svg_close


def test_all_eight_layout_classes_available():
    # the fixture exercises six distinct layouts; mapping/panel are unit-tested below
    out = render(_doc(), {})
    for lay in ("pipeline", "ladder", "flow", "hub", "stack", "timeline"):
        assert f"fig-{lay}" in out, f"missing fig-{lay}"
    import render as render_mod
    for lay in ("pipeline", "flow", "ladder", "mapping", "panel", "hub", "stack", "timeline"):
        assert lay in render_mod._LAYOUTS, f"layout {lay} not registered"


def test_diagram_interactivity_present():
    out = render(_doc(), {})
    assert "data-cap=" in out                           # hover-to-explain
    assert 'data-target="#' in out                      # click-to-jump
    assert "<figcaption" in out


def test_timeline_is_scroll_scrubbed():
    out = render(_doc(), {})
    assert "data-at=" in out                            # chronological lighting
    assert "fig-timeline" in out
    assert "--p" in out                                 # scrub variable


# ── per-layout motion is NOT one-size-fits-all ───────────────────────────────

def test_diagram_viewboxes_have_uniform_width():
    """Every diagram uses viewBox width 1000 so SVG text scales uniformly across the page —
    a narrow viewBox would stretch to the container and blow the label size up."""
    import re
    out = render(_doc(), {})
    diagram_widths = {w for w in re.findall(r'viewBox="0 0 (\d+) \d+"', out) if int(w) > 100}
    assert diagram_widths == {"1000"}, f"non-uniform diagram widths: {sorted(diagram_widths)}"


def test_diagram_titles_render_in_display_face():
    out = render(_doc(), {})
    assert 'font-size="19"' in out                    # Fraunces diagram-title size
    assert "How a position evolves" in out            # a fixture diagram title


def test_each_layout_has_its_own_motion_rule():
    """Animation is keyed off layout — each layout has a distinct motion grammar."""
    out = render(_doc(), {})
    motions = [
        ".fig-pipeline.in svg .anim",      # stages illuminate
        ".fig-flow.in svg .anim",          # nodes drop in
        ".flow-trace",                      # flow comet
        ".fig-ladder.in svg .anim",        # rungs in order
        ".fig-mapping.in svg .lm-k",       # links draw
        ".fig-panel.in svg .anim",         # cards stagger
        ".fig-hub.in svg .hub-spoke",      # spokes draw out
        ".fig-hub.in svg .hub-core",       # core pops
        ".fig-stack.in svg .stack-layer",  # layers build
        ".fig-timeline svg .tl-line",      # line draws
    ]
    for rule in motions:
        assert rule in out, f"missing per-layout motion rule: {rule}"


def test_motion_is_reduced_motion_and_print_safe():
    out = render(_doc(), {})
    assert "@media (prefers-reduced-motion: reduce)" in out
    assert "@media print" in out
    assert "@media (scripting: none)" in out            # no-JS fallback reveals figures


# ── faithfulness: no machine locators in the body ────────────────────────────

def test_no_raw_source_locators_in_output():
    """The renderer uses ref.name / ref.anchor only — never the machine locator."""
    out = render(_doc(), {})
    doc = _doc()
    locators = {r.locator for s in doc.sections for b in s.blocks for r in b.source_refs}
    locators |= {r.locator for s in doc.sections for b in s.blocks
                 if b.diagram for n in b.diagram.nodes for r in n.source_refs}
    for loc in locators:
        assert loc not in out, f"machine locator leaked into output: {loc}"


# ── determinism ──────────────────────────────────────────────────────────────

def test_citation_chips_resolve_to_appendix_anchors():
    """Phase B (spec 002): a chip links to its EXACT reference entry in the appendix
    (a deterministic #ref-<hash> anchor, not the bare #refs), and that anchor exists once."""
    import re
    out = render(_doc(), {})
    hrefs = set(re.findall(r'<a class="ref" href="#(ref-[0-9a-f]+)"', out))
    assert hrefs, "citation chips no longer resolve to per-reference anchors"
    for a in hrefs:
        assert out.count(f'id="{a}"') == 1, f"appendix anchor {a} missing or duplicated"
    assert 'id="refs"' in out          # the appendix section still exists for back-nav


def test_render_is_deterministic():
    doc = _doc()
    a = render(doc, {})
    b = render(doc, {})
    assert a == b
    assert a.encode("utf-8") == b.encode("utf-8")


# ── theme override (light-only retint layer) ─────────────────────────────────

def test_custom_theme_overrides_token():
    custom = {"gold": "#ff00aa", "paper": "#000102"}
    out = render(_doc(), custom)
    assert "--gold: #ff00aa;" in out
    assert "--paper: #000102;" in out
    assert f"--ink: {DEFAULT_THEME['ink']};" in out     # untouched token keeps default


def test_default_theme_when_no_override():
    out = render(_doc(), {})
    assert f"--gold: {DEFAULT_THEME['gold']};" in out


def test_theme_dict_loaded_from_json_roundtrips(tmp_path):
    theme_file = tmp_path / "theme.json"
    theme_file.write_text(json.dumps({"gold": "#123456"}), encoding="utf-8")
    loaded = json.loads(theme_file.read_text(encoding="utf-8"))
    out = render(_doc(), loaded)
    assert "--gold: #123456;" in out


# ── escaping ─────────────────────────────────────────────────────────────────

def test_text_is_html_escaped():
    doc = _doc()
    doc.sections[0].title = '<script>alert("x")</script> & more'
    doc.sections[0].strap = '<i>strap</i> & "q"'
    out = render(doc, {})
    assert "<script>alert" not in out
    assert "&lt;script&gt;alert" in out
    assert "&amp; more" in out
    assert "<i>strap</i>" not in out                 # section.strap is escaped too
    assert "&lt;i&gt;strap&lt;/i&gt;" in out


def test_escaping_covers_every_model_text_field():
    """Hostile content in EVERY model-derived field must escape — no XSS via any path."""
    from schema import (Altitude, Block, BlockType, DiagramEdge, DiagramGraph,
                        DiagramNode, DocumentModel, MetaPair, Section, SourceRef, SourceType)
    # a unique sentinel tag that can never appear legitimately (unlike <script>,
    # which the page emits for its own JS block).
    bad = '<x7s>"&'
    doc = DocumentModel(
        title="Title", project_name=bad,
        kicker=[bad], meta=[MetaPair(label=bad, value=bad)],
        sections=[Section(id="s", number=1, title="Sec", strap=bad, subtitle=bad, blocks=[
            Block(type=BlockType.PROSE, altitude=Altitude.FUNCTIONAL, prose=bad,
                  source_refs=[SourceRef(type=SourceType.SPEC, name=bad, locator="l1", anchor=bad)]),
            Block(type=BlockType.DIAGRAM, altitude=Altitude.FUNCTIONAL,
                  diagram=DiagramGraph(layout="flow",
                      nodes=[DiagramNode(id="a", label=bad, caption=bad), DiagramNode(id="b", label="b")],
                      edges=[DiagramEdge(src="a", dst="b", label=bad)])),
        ])])
    out = render(doc, {})
    assert "<x7s>" not in out                         # injected into 8 fields; none may leak
    assert "&lt;x7s&gt;" in out


def test_title_accent_escaping():
    doc = _doc()
    doc.title = '<b>X</b> Y'
    doc.title_accent = '<b>X</b>'
    out = render(doc, {})
    assert "<b>X</b>" not in out                      # both halves of the accent split escape
    assert "<em>&lt;b&gt;X&lt;/b&gt;</em>" in out


def test_figure_numbering_is_continuous():
    doc = _doc()
    out = render(doc, {})
    n = sum(1 for s in doc.sections for b in s.blocks if b.type.value == "diagram")
    assert n >= 6
    for i in range(1, n + 1):
        assert f"Fig. {i}" in out
    assert f"Fig. {n + 1}" not in out


def test_kicker_truncated_to_two_spans():
    from schema import DocumentModel, Section
    doc = DocumentModel(title="T", project_name="P", kicker=["AAA", "BBB", "CCC"],
                        sections=[Section(id="s", number=1, title="S")])
    out = render(doc, {})
    assert "<span>AAA</span>" in out and "<span>BBB</span>" in out
    assert "CCC" not in out                           # 3rd+ kicker entry dropped


def test_section_refs_are_deduplicated():
    from schema import (Altitude, Block, BlockType, DocumentModel, Section, SourceRef, SourceType)
    ref = SourceRef(type=SourceType.SPEC, name="dupname", locator="l1", anchor="a")
    doc = DocumentModel(title="T", project_name="P", sections=[
        Section(id="s", number=1, title="S", blocks=[
            Block(type=BlockType.PROSE, altitude=Altitude.FUNCTIONAL, prose="x", source_refs=[ref, ref]),
            Block(type=BlockType.PROSE, altitude=Altitude.FUNCTIONAL, prose="y", source_refs=[ref]),
        ])])
    out = render(doc, {})
    assert out.count(">dupname</a>") == 1             # one chip despite three occurrences


def test_diagram_node_refs_surface_in_sources():
    """A source carried ONLY by a diagram node must reach the sources line + appendix."""
    from schema import (Altitude, Block, BlockType, DiagramGraph, DiagramNode,
                        DocumentModel, Section, SourceRef, SourceType)
    node_ref = SourceRef(type=SourceType.CODE, name="only_on_node.py", locator="loc-node")
    doc = DocumentModel(title="T", project_name="P", sections=[
        Section(id="s", number=1, title="S", blocks=[
            Block(type=BlockType.DIAGRAM, altitude=Altitude.FUNCTIONAL,
                  diagram=DiagramGraph(layout="pipeline",
                      nodes=[DiagramNode(id="a", label="A", source_refs=[node_ref])])),
        ])])
    out = render(doc, {})
    assert "only_on_node.py" in out                   # not silently dropped
    assert out.count("only_on_node.py") >= 2          # sources line + References appendix


def test_panel_caption_truncates_long():
    from schema import (Altitude, Block, BlockType, DiagramGraph, DiagramNode, DocumentModel, Section)
    long = "x" * 60
    doc = DocumentModel(title="T", project_name="P", sections=[
        Section(id="s", number=1, title="S", blocks=[
            Block(type=BlockType.DIAGRAM, altitude=Altitude.FUNCTIONAL,
                  diagram=DiagramGraph(layout="panel", nodes=[DiagramNode(id="a", label="A", caption=long)]))
        ])])
    out = render(doc, {})
    assert ("x" * 45 + "…") in out                    # visible SVG label is truncated
    assert ('data-cap="' + long + '"') in out         # but hover-to-explain keeps the full text


def test_svg_styling_is_inline_not_css_dependent():
    """SVG must carry font/fill/stroke INLINE so diagrams render in ANY viewer (QuickLook,
    mail/preview, PDF) — not only where the document <style> cascades into inline SVG."""
    import re
    svgs = "".join(re.findall(r"<svg.*?</svg>", render(_doc(), {}), re.S))
    assert "font-family=" in svgs                  # text sets its face inline
    assert "var(--" not in svgs                    # no CSS-variable dependence inside SVG
    assert 'class="d-panel"' not in svgs and 'class="d-flow"' not in svgs


def test_no_js_fallback_resets_transform_and_strokes():
    """@media (scripting: none) must reveal, un-scale, AND draw stroke diagrams (no-JS safe)."""
    out = render(_doc(), {})
    seg = out[out.index("@media (scripting: none)"):][:500]
    assert "transform: none !important" in seg       # un-scale timeline nodes
    assert "stroke-dashoffset: 0 !important" in seg   # draw the timeline line with JS off


# ── mapping + panel layouts (not in the fixture; rendered distinctly) ────────

def test_mapping_and_panel_layouts_render_distinctly():
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
    doc = DocumentModel(title="Demo", project_name="demo", sections=[
        Section(id="s", number=1, title="Diagrams", blocks=[
            Block(type=BlockType.DIAGRAM, altitude=Altitude.FUNCTIONAL, diagram=mapping),
            Block(type=BlockType.DIAGRAM, altitude=Altitude.FUNCTIONAL, diagram=panel),
        ])])
    html = render_mod.render(doc, render_mod.DEFAULT_THEME)
    assert "FROM" in html and "TO" in html              # mapping column labels
    assert "repository" in html and "Project" in html
    assert "parser" in html and "reads specs" in html   # panel cards + captions
    assert "fig-mapping" in html and "fig-panel" in html
    assert html.count("<svg") == html.count("</svg>")
    assert html.count("<figure") == 2


def test_mapping_panel_hub_stack_timeline_are_registered():
    import render as render_mod
    assert render_mod._LAYOUTS["mapping"] is render_mod._layout_mapping
    assert render_mod._LAYOUTS["panel"] is render_mod._layout_panel
    assert render_mod._LAYOUTS["hub"] is render_mod._layout_hub
    assert render_mod._LAYOUTS["stack"] is render_mod._layout_stack
    assert render_mod._LAYOUTS["timeline"] is render_mod._layout_timeline
