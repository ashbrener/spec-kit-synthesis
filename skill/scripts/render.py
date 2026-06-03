#!/usr/bin/env python3
"""Deterministic HTML renderer for spec-kit-synthesis (DESIGN §6, §11.2 #7).

INPUT  : a `DocumentModel` JSON (the compose output; see schema.py).
OUTPUT : one self-contained, interactive HTML "technical-manuscript" storybook,
         structurally + behaviourally matching examples/speckit-linear-architecture.html.

This module is PURE: stdlib only, NO LLM, NO network, NO timestamps, NO randomness.
Identical input bytes → identical output bytes (the composition is the only source of
prose; the renderer never invents text and never injects source numbers into the body).

Three clean stages are honoured (DESIGN §11.2 #7): composition (the DocumentModel) ≠
markup (this renderer) ≠ theme (a flat dict of CSS custom-property tokens applied at
render). Re-theming requires no re-layout because every diagram coordinate is fixed and
every colour/font is a CSS variable.

CLI:
    uv run python skill/scripts/render.py <document_model.json> [--theme <theme.json>] [--out <out.html>]
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Optional

# schema.py lives beside this file; importable both as a module and as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from schema import (  # noqa: E402
    Altitude,
    Block,
    BlockType,
    CalloutKind,
    DiagramEdge,
    DiagramGraph,
    DiagramNode,
    DocumentModel,
    Section,
    SourceRef,
    SourceType,
)

# ────────────────────────────── default reference theme ─────────────────────
# The north-star's palette/fonts. A --theme JSON is a *flat* dict of these keys;
# any subset overrides the defaults. Keys map 1:1 to CSS custom properties.

DEFAULT_THEME: dict[str, str] = {
    # paper / ink
    "paper": "#faf7f0",
    "paper-2": "#f3efe4",
    "paper-3": "#ece6d7",
    "ink": "#17150f",
    "ink-2": "#56524a",
    "ink-3": "#87827a",
    "hair": "#e1dac9",
    "hair-2": "#d2c9b3",
    # accent
    "accent": "#b3471d",
    "accent-d": "#8f3614",
    "accent-soft": "#f6e6da",
    # three callout hues (decision=accent, unspecified=ochre, evolution=plum)
    "plum": "#6a3a6f",
    "plum-soft": "#efe4f0",
    "ochre": "#9a6b14",
    "ochre-soft": "#f6ecd2",
    "teal": "#1f5048",
    "teal-soft": "#e2ece7",
    # fonts
    "sans": '"Bricolage Grotesque", system-ui, sans-serif',
    "serif": '"Newsreader", Georgia, serif',
    "mono": '"IBM Plex Mono", ui-monospace, Menlo, monospace',
}

# Dark theme is fixed (it is a relationship to the light tokens, not a user token set);
# it always renders so the theme toggle has somewhere to go.
DARK_THEME: dict[str, str] = {
    "paper": "#16150f",
    "paper-2": "#1e1d15",
    "paper-3": "#27251a",
    "ink": "#f3eee1",
    "ink-2": "#b3ad9c",
    "ink-3": "#837d6e",
    "hair": "#322f23",
    "hair-2": "#423d2d",
    "accent": "#e3743f",
    "accent-d": "#f0905f",
    "accent-soft": "#2c2016",
    "plum": "#c79bcb",
    "plum-soft": "#241a26",
    "ochre": "#d7a13f",
    "ochre-soft": "#272013",
    "teal": "#6fb9ab",
    "teal-soft": "#16241f",
}

# SourceType → the citation chip's data-t attribute (drives the typed badge colour).
SOURCE_T = {
    SourceType.SPEC: "spec",
    SourceType.CODE: "code",
    SourceType.DESIGN_DOC: "doc",
}

CALLOUT_CLASS = {
    CalloutKind.DECISION: "decision",
    CalloutKind.UNSPECIFIED: "unspec",
    CalloutKind.EVOLUTION: "hist",
}

CALLOUT_DEFAULT_TAG = {
    CalloutKind.DECISION: "Decision",
    CalloutKind.UNSPECIFIED: "Unspecified",
    CalloutKind.EVOLUTION: "Evolution",
}


def esc(s: Optional[str]) -> str:
    """HTML-escape any text from the model (incl. quotes, for attribute safety)."""
    return html.escape(s or "", quote=True)


# ────────────────────────────────── CSS ─────────────────────────────────────
# Lifted structurally from the north-star: the :root block is generated from the
# theme dict so re-theming is pure data. Everything downstream references vars.

def _theme_vars(theme: dict[str, str]) -> str:
    return "\n".join(f"    --{k}: {v};" for k, v in theme.items())


def build_css(theme: dict[str, str]) -> str:
    root_vars = _theme_vars(theme)
    dark_vars = _theme_vars(DARK_THEME)
    return f"""  :root {{
{root_vars}
    --shadow: 12px 16px 40px -24px rgba(40,28,12,.55);
    --ease: cubic-bezier(.22,.61,.36,1);
  }}
  html[data-theme="dark"] {{
{dark_vars}
    --shadow: 12px 16px 44px -22px rgba(0,0,0,.7);
  }}

  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  @media (prefers-reduced-motion: reduce) {{ html {{ scroll-behavior: auto; }} }}
  body {{
    margin: 0; color: var(--ink);
    background:
      radial-gradient(1200px 600px at 88% -8%, color-mix(in oklab, var(--accent) 9%, transparent), transparent 60%),
      radial-gradient(900px 500px at -5% 6%, color-mix(in oklab, var(--teal) 8%, transparent), transparent 55%),
      var(--paper);
    font-family: var(--serif); font-size: 18px; line-height: 1.72;
    -webkit-font-smoothing: antialiased;
    transition: background-color .35s ease, color .35s ease;
  }}

  #progress {{ position: fixed; top: 0; left: 0; height: 3px; width: 0%; z-index: 60;
    background: linear-gradient(90deg, var(--accent), var(--plum)); transition: width .12s linear; }}

  .controls {{ position: fixed; top: 16px; right: 18px; z-index: 60; display: flex; gap: 10px; align-items: center; }}
  @media (max-width: 720px){{ .controls {{ position: static; justify-content: flex-end; padding: 14px 18px 0; }} }}

  .seg {{ display: inline-flex; border: 1px solid var(--hair-2); border-radius: 999px; overflow: hidden;
    font-family: var(--mono); font-size: 11.5px; background: var(--paper-2); }}
  .seg button {{ background: transparent; border: 0; padding: 7px 13px; color: var(--ink-3); cursor: pointer;
    letter-spacing: .03em; transition: background .2s, color .2s; }}
  .seg button:hover {{ color: var(--ink); }}
  .seg button[aria-pressed="true"] {{ background: var(--accent); color: #fff; }}
  html[data-theme="dark"] .seg button[aria-pressed="true"] {{ color: #16150f; }}

  .toggle {{ font-family: var(--mono); font-size: 12px; letter-spacing: .03em;
    display: inline-flex; align-items: center; gap: 7px;
    background: var(--paper-2); color: var(--ink-2);
    border: 1px solid var(--hair-2); border-radius: 999px; padding: 7px 13px; cursor: pointer;
    transition: color .2s, border-color .2s, transform .2s; }}
  .toggle:hover {{ color: var(--accent); border-color: var(--accent); transform: translateY(-1px); }}
  .toggle svg {{ width: 14px; height: 14px; }}

  .wrap {{ max-width: 1180px; margin: 0 auto; padding: 0 32px; }}
  .layout {{ display: grid; grid-template-columns: 244px minmax(0,1fr); gap: 64px; align-items: start; }}
  @media (max-width: 940px) {{ .layout {{ grid-template-columns: 1fr; gap: 0; }} nav.toc {{ display: none; }} }}

  header.mast {{ padding: 78px 0 40px; border-bottom: 1px solid var(--hair); position: relative; }}
  header.mast .kicker {{ font-family: var(--mono); font-size: 12.5px; letter-spacing: .26em; text-transform: uppercase; color: var(--accent); }}
  header.mast h1 {{ font-family: var(--sans); font-weight: 600; font-size: clamp(40px, 7vw, 78px); line-height: .98; letter-spacing: -.025em; margin: 20px 0 0; }}
  header.mast h1 .amp {{ color: var(--accent); font-weight: 400; }}
  header.mast .lede {{ font-size: clamp(19px, 2.4vw, 23px); line-height: 1.5; color: var(--ink-2); max-width: 36ch; margin: 26px 0 0; }}
  header.mast .depthnote {{ margin-top: 20px; font-family: var(--sans); font-size: 13.5px; color: var(--ink-3); max-width: 60ch; }}
  header.mast .depthnote b {{ color: var(--ink-2); font-weight: 600; }}

  nav.toc {{ position: sticky; top: 0; align-self: start; padding-top: 78px; height: 100vh; overflow-y: auto; }}
  nav.toc .toc-title {{ font-family: var(--mono); font-size: 11px; letter-spacing: .22em; text-transform: uppercase; color: var(--ink-3); margin-bottom: 14px; }}
  nav.toc ol {{ list-style: none; margin: 0; padding: 0; counter-reset: toc; }}
  nav.toc li {{ counter-increment: toc; }}
  nav.toc a {{ font-family: var(--sans); display: grid; grid-template-columns: 22px 1fr; gap: 8px; align-items: baseline;
    padding: 6px 0; color: var(--ink-3); text-decoration: none; font-size: 14px; line-height: 1.3; transition: color .18s; }}
  nav.toc a::before {{ content: counter(toc, decimal-leading-zero); font-family: var(--mono); font-size: 11px; color: var(--hair-2); transition: color .18s; }}
  nav.toc a:hover {{ color: var(--ink); }}
  nav.toc a.active {{ color: var(--accent); }}
  nav.toc a.active::before {{ color: var(--accent); }}

  main {{ padding-top: 56px; padding-bottom: 120px; min-width: 0; }}
  section {{ margin-bottom: 84px; scroll-margin-top: 24px; }}
  .sec-no {{ font-family: var(--mono); font-size: 12.5px; letter-spacing: .2em; color: var(--accent); display: block; margin-bottom: 10px; }}
  h2 {{ font-family: var(--sans); font-weight: 600; font-size: clamp(27px, 3.6vw, 37px); letter-spacing: -.02em; line-height: 1.06; margin: 0; }}
  h3 {{ font-family: var(--sans); font-weight: 600; font-size: 19px; letter-spacing: -.01em; margin: 38px 0 4px; }}
  .section-sub {{ font-style: italic; color: var(--ink-2); font-size: 18px; margin: 12px 0 26px; max-width: 64ch; }}
  p {{ margin: 16px 0; max-width: 68ch; }}
  a {{ color: var(--accent); text-underline-offset: 3px; text-decoration-thickness: 1px; }}
  strong {{ font-weight: 600; }}
  code {{ font-family: var(--mono); font-size: .8em; background: var(--paper-2); border: 1px solid var(--hair); padding: 1px 6px; border-radius: 5px; color: var(--accent-d); white-space: nowrap; }}

  .tbl {{ margin: 22px 0; border: 1px solid var(--hair); border-radius: 12px; overflow: hidden; background: var(--paper-2); }}
  table {{ border-collapse: collapse; width: 100%; font-family: var(--sans); font-size: 14.5px; }}
  th, td {{ text-align: left; padding: 12px 16px; border-bottom: 1px solid var(--hair); vertical-align: top; line-height: 1.45; }}
  th {{ font-family: var(--mono); font-size: 11px; letter-spacing: .1em; text-transform: uppercase; color: var(--ink-3); font-weight: 500; background: var(--paper-3); }}
  tbody tr:last-child td {{ border-bottom: none; }}
  tbody tr:hover {{ background: color-mix(in oklab, var(--accent) 5%, transparent); }}
  td code {{ white-space: normal; }}

  figure {{ margin: 30px 0; }}
  .fig-shell {{ border: 1px solid var(--hair); border-radius: 16px; background:
      linear-gradient(180deg, color-mix(in oklab, var(--paper-2) 70%, transparent), var(--paper-2));
    padding: 22px 22px 18px; box-shadow: var(--shadow); }}
  .fig-head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 14px; margin-bottom: 14px; flex-wrap: wrap; }}
  .fig-head .lab {{ font-family: var(--mono); font-size: 11px; letter-spacing: .18em; text-transform: uppercase; color: var(--ink-3); }}
  .fig svg {{ width: 100%; height: auto; display: block; }}
  figcaption {{ font-family: var(--sans); font-size: 13.5px; color: var(--ink-2); margin-top: 14px; min-height: 1.4em; line-height: 1.5; }}
  figcaption .pin {{ color: var(--accent); font-weight: 600; }}

  /* ---- progressive-disclosure tiers ---- */
  .tier {{ display: grid; grid-template-rows: 0fr; opacity: 0; margin-top: 0;
    transition: grid-template-rows .45s var(--ease), opacity .35s ease, margin-top .45s var(--ease); }}
  .tier > .tier-in {{ overflow: hidden; min-height: 0; }}
  html[data-depth="1"] .tier1, html[data-depth="2"] .tier1 {{ grid-template-rows: 1fr; opacity: 1; margin-top: 22px; }}
  html[data-depth="2"] .tier2 {{ grid-template-rows: 1fr; opacity: 1; margin-top: 16px; }}
  @media (prefers-reduced-motion: reduce) {{ .tier {{ transition: none; }} }}

  .tier1 .tier-in {{ border-left: 2px solid var(--accent); padding: 4px 0 4px 20px; }}
  .tier-lab {{ font-family: var(--mono); font-size: 10.5px; letter-spacing: .18em; text-transform: uppercase; color: var(--accent); display: block; margin-bottom: 10px; }}
  .tier1 p, .tier1 li {{ font-family: var(--sans); font-size: 15px; }}
  .tier1 p {{ max-width: 66ch; }}

  .cites {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
  .cite-lab {{ font-family: var(--mono); font-size: 10.5px; letter-spacing: .16em; text-transform: uppercase; color: var(--ink-3); margin-right: 4px; }}
  .cite {{ font-family: var(--mono); font-size: 11.5px; display: inline-flex; align-items: center; gap: 7px;
    border: 1px solid var(--hair-2); border-radius: 7px; padding: 4px 9px 4px 7px; color: var(--ink-2);
    background: var(--paper-2); cursor: help; transition: border-color .18s, color .18s, transform .18s; }}
  .cite:hover {{ transform: translateY(-1px); color: var(--ink); }}
  .cite::before {{ font-size: 9px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
    padding: 2px 5px; border-radius: 4px; color: #fff; }}
  html[data-theme="dark"] .cite::before {{ color: #16150f; }}
  .cite[data-t="spec"]::before {{ content: "spec"; background: var(--accent); }}
  .cite[data-t="spec"]:hover {{ border-color: var(--accent); }}
  .cite[data-t="code"]::before {{ content: "code"; background: var(--teal); }}
  .cite[data-t="code"]:hover {{ border-color: var(--teal); }}
  .cite[data-t="doc"]::before  {{ content: "doc";  background: var(--plum); }}
  .cite[data-t="doc"]:hover  {{ border-color: var(--plum); }}

  /* coverage matrix (intent vs reality) */
  .coverage {{ border: 1px solid var(--hair-2); border-radius: 12px; overflow: hidden; margin: 22px 0; }}
  .cov-head, .cov-row {{ display: grid; grid-template-columns: 1.4fr .9fr 2fr; gap: 14px; padding: 12px 16px; align-items: start; }}
  .cov-head {{ font-family: var(--mono); font-size: 10.5px; letter-spacing: .14em; text-transform: uppercase; color: var(--ink-3); background: var(--paper-2); }}
  .cov-row {{ border-top: 1px solid var(--hair-2); }}
  .cov-area {{ font-family: var(--sans); font-weight: 600; font-size: 14.5px; }}
  .cov-note {{ font-weight: 400; font-size: 12.5px; color: var(--ink-3); margin-top: 3px; }}
  .cov-srcs {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .cov-pill {{ font-family: var(--mono); font-size: 10.5px; padding: 3px 9px; border-radius: 999px; white-space: nowrap; border: 1px solid transparent; }}
  .cov-spec_backed {{ background: color-mix(in srgb, var(--teal) 18%, transparent); color: var(--teal); border-color: color-mix(in srgb, var(--teal) 40%, transparent); }}
  .cov-specced_only {{ background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--accent); border-color: color-mix(in srgb, var(--accent) 38%, transparent); }}
  .cov-implemented_only {{ background: color-mix(in srgb, var(--plum) 16%, transparent); color: var(--plum); border-color: color-mix(in srgb, var(--plum) 38%, transparent); }}
  .cov-unknown {{ background: var(--paper-2); color: var(--ink-3); border-color: var(--hair-2); }}

  .box {{ border-radius: 13px; padding: 18px 20px; margin: 24px 0; font-family: var(--sans); font-size: 15.5px; line-height: 1.55; border: 1px solid; position: relative; max-width: 70ch; }}
  .box .tag {{ font-family: var(--mono); font-size: 11px; letter-spacing: .14em; text-transform: uppercase; font-weight: 600; display: block; margin-bottom: 7px; }}
  .box p {{ margin: 0; max-width: none; font-family: var(--sans); }}
  .box.decision {{ background: var(--accent-soft); border-color: color-mix(in oklab, var(--accent) 35%, var(--hair)); }}
  .box.decision .tag {{ color: var(--accent); }}
  .box.unspec {{ background: var(--ochre-soft); border-color: color-mix(in oklab, var(--ochre) 35%, var(--hair)); }}
  .box.unspec .tag {{ color: var(--ochre); }}
  .box.hist {{ background: var(--plum-soft); border-color: color-mix(in oklab, var(--plum) 32%, var(--hair)); }}
  .box.hist .tag {{ color: var(--plum); }}

  .reveal {{ opacity: 0; transform: translateY(14px); transition: opacity .6s ease, transform .6s ease; }}
  .reveal.in {{ opacity: 1; transform: none; }}
  @media (prefers-reduced-motion: reduce) {{ .reveal {{ opacity: 1; transform: none; }} }}

  /* svg shared */
  .d-panel {{ fill: var(--paper); stroke: var(--hair-2); }}
  .d-panel-2 {{ fill: var(--paper-3); stroke: var(--hair-2); }}
  .d-node {{ fill: var(--paper); stroke: var(--hair-2); transition: fill .18s, stroke .18s; }}
  .d-node.act {{ cursor: pointer; }}
  .d-node.act:hover {{ fill: var(--accent-soft); stroke: var(--accent); }}
  .d-flow {{ fill: none; stroke: var(--hair-2); stroke-width: 1.6; }}
  .d-flow-em {{ fill: none; stroke: var(--accent); stroke-width: 2; }}
  text.t {{ font-family: var(--sans); fill: var(--ink); }}
  text.tm {{ font-family: var(--mono); fill: var(--ink-2); }}
  text.tlab {{ font-family: var(--mono); fill: var(--ink-3); letter-spacing: .12em; }}
  text.acc {{ fill: var(--accent); }}

  footer {{ border-top: 1px solid var(--hair); padding: 34px 0 90px; color: var(--ink-3); font-family: var(--sans); font-size: 13.5px; }}"""


# ──────────────────────────── diagram → SVG layout ──────────────────────────
# Each layout is a pure function (DiagramGraph) -> SVG markup with FIXED, hand-laid
# coordinates. No physics, no randomness: same graph → same bytes. Every colour is a
# CSS var so a theme change needs no re-layout (DESIGN §6). Nodes with a caption get
# data-cap (hover-to-explain); nodes with a target get data-target (click-to-jump).

_NS_ARROW_FWD = "var(--accent)"
_NS_ARROW_MUTED = "var(--hair-2)"


def _node_attrs(node: DiagramNode) -> str:
    """Common interactivity attributes for an interactive node group."""
    attrs = ['class="d-node act"']
    if node.caption:
        attrs.append(f'data-cap="{esc(node.caption)}"')
    if node.target:
        # target is a section id; the click handler scrolls to #<id>.
        attrs.append(f'data-target="#{esc(node.target)}"')
    return " ".join(attrs)


def _svg_text(x: float, y: float, cls: str, size: float, text: str, *, anchor: str = "start") -> str:
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    return f'<text class="{cls}" x="{x:g}" y="{y:g}" font-size="{size:g}"{a}>{esc(text)}</text>'


def _markers(fig_id: str) -> str:
    """Per-figure arrowhead markers (unique ids so multiple SVGs coexist)."""
    return (
        f'<defs>'
        f'<marker id="{fig_id}-af" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">'
        f'<path d="M0,0 L8,4.5 L0,9 z" fill="{_NS_ARROW_FWD}"/></marker>'
        f'<marker id="{fig_id}-am" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">'
        f'<path d="M0,0 L8,4.5 L0,9 z" fill="{_NS_ARROW_MUTED}"/></marker>'
        f'</defs>'
    )


def _layout_pipeline(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """Nodes laid out left→right as a horizontal pipeline; edges connect in sequence.

    Edges are drawn by node id where both endpoints exist; an edge with emphasis uses
    the accent flow + filled arrowhead. Labels ride above the connector.
    """
    n = len(graph.nodes)
    nw, nh, gap = 150, 64, 60
    margin_x, top = 30, 70
    width = margin_x * 2 + n * nw + max(0, n - 1) * gap
    height = top + nh + 70
    cx: dict[str, tuple[float, float]] = {}
    parts = [_markers(fig_id)]
    for i, node in enumerate(graph.nodes):
        x = margin_x + i * (nw + gap)
        y = top
        cx[node.id] = (x, y)
        parts.append(f'<g {_node_attrs(node)}>')
        parts.append(f'<rect x="{x:g}" y="{y:g}" width="{nw}" height="{nh}" rx="12" class="d-panel"/>')
        parts.append(_svg_text(x + nw / 2, y + nh / 2 + 4, "tm", 12, node.label, anchor="middle"))
        parts.append('</g>')
    parts.append(_edges_horizontal(graph.edges, cx, fig_id, nw, nh))
    return "".join(parts), width, height


def _layout_flow(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """A decision/flow: nodes stacked vertically down the centre, connected top→bottom.

    Generic enough for branching narratives; emphasis edges use the accent stroke.
    """
    n = len(graph.nodes)
    nw, nh, gap = 280, 56, 46
    top, margin_x = 24, 30
    width = 940
    cx = (width) / 2
    height = top + n * nh + max(0, n - 1) * gap + 40
    pos: dict[str, tuple[float, float]] = {}
    parts = [_markers(fig_id)]
    for i, node in enumerate(graph.nodes):
        y = top + i * (nh + gap)
        x = cx - nw / 2
        pos[node.id] = (x, y)
        rx = 26 if i == 0 or i == n - 1 else 12
        parts.append(f'<g {_node_attrs(node)}>')
        parts.append(f'<rect x="{x:g}" y="{y:g}" width="{nw}" height="{nh}" rx="{rx}" class="d-panel"/>')
        parts.append(_svg_text(cx, y + nh / 2 + 4, "t", 13, node.label, anchor="middle"))
        parts.append('</g>')
    parts.append(_edges_vertical(graph.edges, pos, fig_id, nw, nh, cx))
    return "".join(parts), width, height


def _layout_ladder(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """An ordered, rising ladder: rank-0 low-left climbing to rank-N high-right.

    Each rung shows its rank index + label; the terminal rung is accent-outlined.
    Connectors run rung→rung. Matches the north-star's Fig. 3.
    """
    n = len(graph.nodes)
    if n == 0:
        return _markers(fig_id), 940, 120
    width = 940
    x0, w, rh = 40, 96, 38
    base_y, rise = 40 + (n - 1) * 22, 22
    height = base_y + rh + 40
    span = width - x0 - w - 30
    gap = span / (n - 1) if n > 1 else 0
    pos: dict[str, tuple[float, float]] = {}
    parts = [_markers(fig_id)]
    # baseline rule
    parts.append(f'<line x1="{x0}" y1="{base_y + rh + 14:g}" x2="{width - 30}" y2="{base_y + rh + 14:g}" stroke="var(--hair)"/>')
    for i, node in enumerate(graph.nodes):
        x = x0 + i * gap
        y = base_y - i * rise
        pos[node.id] = (x, y)
        terminal = i == n - 1
        stroke = ' stroke="var(--accent)"' if terminal else ""
        parts.append(f'<g {_node_attrs(node)}>')
        parts.append(f'<rect x="{x:g}" y="{y:g}" width="{w}" height="{rh}" rx="8" class="d-node"{stroke}/>')
        parts.append(_svg_text(x + 9, y + 15, "tlab", 9, str(i)))
        cls = "tm acc" if terminal else "tm"
        parts.append(f'<text class="{cls}" x="{x + 9:g}" y="{y + 30:g}" font-size="9.5">{esc(node.label)}</text>')
        parts.append('</g>')
        if i < n - 1:
            nx = x0 + (i + 1) * gap
            parts.append(f'<path class="d-flow" d="M{x + w:g} {y + rh / 2:g} H {nx:g}" marker-end="url(#{fig_id}-am)"/>')
    return "".join(parts), width, height


def _edges_horizontal(edges: list[DiagramEdge], pos: dict[str, tuple[float, float]],
                      fig_id: str, nw: int, nh: int) -> str:
    parts: list[str] = []
    for e in edges:
        if e.src not in pos or e.dst not in pos:
            continue
        sx, sy = pos[e.src]
        dx, dy = pos[e.dst]
        x1, y1 = sx + nw, sy + nh / 2
        x2, y2 = dx, dy + nh / 2
        cls = "d-flow-em" if e.emphasis else "d-flow"
        marker = f"{fig_id}-af" if e.emphasis else f"{fig_id}-am"
        midx = (x1 + x2) / 2
        parts.append(f'<path class="{cls}" d="M{x1:g} {y1:g} C {midx:g} {y1:g}, {midx:g} {y2:g}, {x2:g} {y2:g}" marker-end="url(#{marker})"/>')
        if e.label:
            lcls = "tm acc" if e.emphasis else "tm"
            parts.append(f'<text class="{lcls}" x="{midx:g}" y="{min(y1, y2) - 8:g}" font-size="10.5" text-anchor="middle">{esc(e.label)}</text>')
    return "".join(parts)


def _edges_vertical(edges: list[DiagramEdge], pos: dict[str, tuple[float, float]],
                    fig_id: str, nw: int, nh: int, cx: float) -> str:
    parts: list[str] = []
    for e in edges:
        if e.src not in pos or e.dst not in pos:
            continue
        sx, sy = pos[e.src]
        dx, dy = pos[e.dst]
        x1, y1 = cx, sy + nh
        x2, y2 = cx, dy
        cls = "d-flow-em" if e.emphasis else "d-flow"
        marker = f"{fig_id}-af" if e.emphasis else f"{fig_id}-am"
        parts.append(f'<path class="{cls}" d="M{x1:g} {y1:g} V {y2:g}" marker-end="url(#{marker})"/>')
        if e.label:
            lcls = "tm acc" if e.emphasis else "tm"
            parts.append(f'<text class="{lcls}" x="{cx + 10:g}" y="{(y1 + y2) / 2 + 4:g}" font-size="10.5">{esc(e.label)}</text>')
    return "".join(parts)


def _layout_mapping(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """Two columns connected left→right by edges — a "this maps to that" table.

    The node set is split by edge direction: every node that is some edge's src
    sits in the left column, every node that is some edge's dst in the right;
    a node that is both (or neither) defaults left. Rows align by first
    appearance, so an edge draws a clean horizontal connector across the gap.
    Matches the north-star's Fig. 2 (filesystem → tracker mapping).
    """
    srcs = [n for n in graph.nodes if any(e.src == n.id for e in graph.edges)]
    dsts = [n for n in graph.nodes if any(e.dst == n.id for e in graph.edges)
            and not any(e.src == n.id for e in graph.edges)]
    leftovers = [n for n in graph.nodes if n not in srcs and n not in dsts]
    left, right = srcs + leftovers, dsts
    rows = max(len(left), len(right), 1)
    width = 940
    nw, nh, vgap = 300, 38, 10
    lx, rx, top = 40, width - 40 - nw, 50
    height = top + rows * (nh + vgap) + 20
    pos: dict[str, tuple[float, float]] = {}
    parts = [_markers(fig_id)]
    parts.append(_svg_text(lx, 34, "tlab", 11, "FROM"))
    parts.append(_svg_text(rx, 34, "tlab", 11, "TO"))
    for col, x in ((left, lx), (right, rx)):
        for i, node in enumerate(col):
            y = top + i * (nh + vgap)
            pos[node.id] = (x, y)
            parts.append(f'<g {_node_attrs(node)}>')
            parts.append(f'<rect x="{x:g}" y="{y:g}" width="{nw}" height="{nh}" rx="9" class="d-node"/>')
            parts.append(_svg_text(x + 16, y + nh / 2 + 4, "tm", 12, node.label))
            parts.append('</g>')
    for e in graph.edges:
        if e.src not in pos or e.dst not in pos:
            continue
        sx, sy = pos[e.src]
        dx, dy = pos[e.dst]
        cls = "d-flow-em" if e.emphasis else "d-flow"
        marker = f"{fig_id}-af" if e.emphasis else f"{fig_id}-am"
        parts.append(f'<path class="{cls}" d="M{sx + nw:g} {sy + nh / 2:g} H {dx:g}" marker-end="url(#{marker})"/>')
    return "".join(parts), width, height


def _layout_panel(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """A responsive grid of labelled boxes — a components/areas overview.

    Edges are ignored (a panel is a set, not a flow); each node is a card that
    keeps its hover caption + click-to-jump. Three columns, wrapping by count.
    """
    n = len(graph.nodes)
    if n == 0:
        return _markers(fig_id), 940, 100
    width = 940
    cols = 3 if n > 4 else max(1, n)
    cw, ch, gx, gy = (width - 40 * 2 - (cols - 1) * 20) / cols, 70, 20, 20
    margin_x, top = 40, 30
    rows = (n + cols - 1) // cols
    height = top + rows * (ch + gy)
    parts = [_markers(fig_id)]
    for i, node in enumerate(graph.nodes):
        r, c = divmod(i, cols)
        x = margin_x + c * (cw + gx)
        y = top + r * (ch + gy)
        parts.append(f'<g {_node_attrs(node)}>')
        parts.append(f'<rect x="{x:g}" y="{y:g}" width="{cw:g}" height="{ch}" rx="11" class="d-panel"/>')
        parts.append(f'<text class="t" x="{x + 16:g}" y="{y + 28:g}" font-size="13" font-weight="600">{esc(node.label)}</text>')
        if node.caption:
            # caption wraps to a second line inside the card (truncated to fit)
            cap = node.caption if len(node.caption) <= 46 else node.caption[:45] + "…"
            parts.append(f'<text class="tm" x="{x + 16:g}" y="{y + 48:g}" font-size="10.5">{esc(cap)}</text>')
        parts.append('</g>')
    return "".join(parts), width, height


# Registry of hand-laid diagram layouts. The renderer falls back to `flow` for any
# layout not present, so a new layout value never crashes a build — it degrades to a
# generic, still-correct stacked rendering.
_LAYOUTS = {
    "pipeline": _layout_pipeline,
    "flow": _layout_flow,
    "ladder": _layout_ladder,
    "mapping": _layout_mapping,
    "panel": _layout_panel,
}


def render_diagram(graph: DiagramGraph, fig_id: str) -> str:
    layout_fn = _LAYOUTS.get(graph.layout, _layout_flow)
    body, w, h = layout_fn(graph, fig_id)
    aria = esc(f"{graph.layout} diagram with {len(graph.nodes)} nodes")
    return (
        f'<svg id="{fig_id}" viewBox="0 0 {w} {h}" role="img" aria-label="{aria}">'
        f'{body}</svg>'
    )


# ─────────────────────────────── block rendering ────────────────────────────

def _cite_chips(refs: list[SourceRef]) -> str:
    """A Layer-2 citation strip. Source-TYPED chips (data-t). The chip text/title
    come straight from the model — the renderer never fabricates source numbers."""
    chips = ['<span class="cite-lab">Backed by</span>']
    for r in refs:
        t = SOURCE_T.get(r.type, "doc")
        title = r.name
        if r.anchor:
            title = f"{r.name} · {r.anchor}"
        chips.append(f'<span class="cite" data-t="{t}" title="{esc(title)}">{esc(r.name)}</span>')
    return (
        '<div class="tier tier2"><div class="tier-in"><div class="cites">'
        + "".join(chips)
        + "</div></div></div>"
    )


def _render_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    head, *body = rows
    th = "".join(f"<th>{esc(c)}</th>" for c in head)
    trs = []
    for row in body:
        tds = "".join(f"<td>{esc(c)}</td>" for c in row)
        trs.append(f"<tr>{tds}</tr>")
    return (
        '<div class="tbl"><table>'
        f"<thead><tr>{th}</tr></thead>"
        f"<tbody>{''.join(trs)}</tbody>"
        "</table></div>"
    )


def _render_callout(block: Block) -> str:
    kind = block.callout_kind
    cls = CALLOUT_CLASS.get(kind, "decision")
    tag = block.callout_tag or CALLOUT_DEFAULT_TAG.get(kind, "Note")
    body = esc(block.prose) if block.prose else ""
    return (
        f'<div class="box {cls}">'
        f'<span class="tag">{esc(tag)}</span>'
        f"<p>{body}</p>"
        "</div>"
    )


def _render_block_core(block: Block, fig_counter: list[int]) -> str:
    """Render a block's actual payload (no tier wrapper)."""
    if block.type is BlockType.PROSE:
        return f"<p>{esc(block.prose)}</p>"
    if block.type is BlockType.TABLE:
        return _render_table(block.table or [])
    if block.type is BlockType.CALLOUT:
        return _render_callout(block)
    if block.type is BlockType.DIAGRAM:
        fig_counter[0] += 1
        n = fig_counter[0]
        fig_id = f"fig{n}"
        svg = render_diagram(block.diagram, fig_id)
        return (
            '<figure class="fig"><div class="fig-shell">'
            '<div class="fig-head">'
            f'<span class="lab">Fig. {n}</span>'
            '<span class="lab" style="color:var(--ink-3)">hover a node &middot; click to jump</span>'
            "</div>"
            f"{svg}"
            f'<figcaption id="cap-{fig_id}">'
            '<span class="pin">Hover the nodes to explore.</span></figcaption>'
            "</div></figure>"
        )
    if block.type is BlockType.COVERAGE:
        return _render_coverage(block.coverage or [])
    return ""


_COVERAGE_LABEL = {
    "spec_backed": "Specified &amp; built",
    # specced_only means "no implementing code was found in the SCANNED tree" —
    # which honestly covers both genuinely-unbuilt areas and code that lives
    # outside the scan (e.g. installed templates). The row's note disambiguates.
    "specced_only": "Specified, not in scanned source",
    "implemented_only": "Built, not specified",
    "unknown": "Unknown",
}


def _render_coverage(rows: list) -> str:
    """An intent-vs-reality matrix: one row per area, a status pill, and the
    spec/code citation chips that back the classification (DESIGN §5.8)."""
    out = ['<div class="coverage">']
    out.append('<div class="cov-head"><span>Area</span><span>Coverage</span><span>Sources</span></div>')
    for ci in rows:
        status = ci.status.value if hasattr(ci.status, "value") else str(ci.status)
        chips = "".join(
            f'<span class="cite" data-t="{r.type.value}">{esc(r.name)}</span>'
            for r in (list(ci.spec_refs) + list(ci.code_refs))
        )
        note = f'<div class="cov-note">{esc(ci.note)}</div>' if ci.note else ""
        out.append(
            '<div class="cov-row">'
            f'<div class="cov-area">{esc(ci.area)}{note}</div>'
            f'<div><span class="cov-pill cov-{status}">{_COVERAGE_LABEL.get(status, esc(status))}</span></div>'
            f'<div class="cov-srcs">{chips}</div>'
            "</div>"
        )
    out.append("</div>")
    return "".join(out)


def _render_block(block: Block, fig_counter: list[int]) -> str:
    """A block, wrapped in its altitude tier.

    functional → Layer 0, always visible.
    technical  → Layer 1, inside a .tier1 wrapper (revealed at depth ≥ 1).
    provenance → handled separately as the per-section Layer-2 citation strip.
    """
    core = _render_block_core(block, fig_counter)
    if not core:
        return ""
    if block.altitude is Altitude.TECHNICAL:
        return (
            '<div class="tier tier1"><div class="tier-in">'
            '<span class="tier-lab">Technical detail</span>'
            f"{core}"
            "</div></div>"
        )
    # functional (and any provenance-altitude block's payload) renders inline at Layer 0.
    return core


def _collect_section_refs(section: Section) -> list[SourceRef]:
    """Stable, de-duplicated union of every block's resolved source_refs → the
    section's Layer-2 strip. Order preserved by first appearance (determinism)."""
    seen: set[tuple[str, str, str, str]] = set()
    ordered: list[SourceRef] = []
    for block in section.blocks:
        for r in block.source_refs:
            key = (r.type.value, r.name, r.locator, r.anchor or "")
            if key not in seen:
                seen.add(key)
                ordered.append(r)
    return ordered


def _render_section(section: Section, fig_counter: list[int]) -> str:
    parts = [f'<section id="{esc(section.id)}" class="reveal">']
    parts.append(f'<span class="sec-no">{section.number:02d}</span>')
    parts.append(f"<h2>{esc(section.title)}</h2>")
    if section.subtitle:
        parts.append(f'<p class="section-sub">{esc(section.subtitle)}</p>')
    for block in section.blocks:
        parts.append(_render_block(block, fig_counter))
    refs = _collect_section_refs(section)
    if refs:
        parts.append(_cite_chips(refs))
    parts.append("</section>")
    return "".join(parts)


# ──────────────────────────────── page shell ────────────────────────────────

def _render_toc(sections: list[Section]) -> str:
    items = "".join(
        f'<li><a href="#{esc(s.id)}">{esc(s.title)}</a></li>' for s in sections
    )
    return (
        '<nav class="toc" aria-label="Table of contents">'
        '<div class="toc-title">Contents</div>'
        f"<ol>{items}</ol>"
        "</nav>"
    )


JS = """(function () {
  "use strict";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var root = document.documentElement;

  /* theme (persisted) */
  var btn = document.getElementById("themeBtn"), lbl = document.getElementById("themeLbl");
  function setTheme(t){ root.setAttribute("data-theme", t); lbl.textContent = (t === "dark" ? "Light" : "Dark"); try { localStorage.setItem("arch-theme", t); } catch(e){} }
  try { var sv = localStorage.getItem("arch-theme"); if (sv) setTheme(sv);
    else if (window.matchMedia("(prefers-color-scheme: dark)").matches) setTheme("dark"); } catch(e){}
  btn.addEventListener("click", function(){ setTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark"); });

  /* reading depth */
  var depthBtns = Array.prototype.slice.call(document.querySelectorAll(".depth button"));
  function setDepth(d){ d = String(d); root.setAttribute("data-depth", d);
    depthBtns.forEach(function(b){ b.setAttribute("aria-pressed", b.getAttribute("data-d") === d); });
    try { localStorage.setItem("arch-depth", d); } catch(e){} }
  depthBtns.forEach(function(b){ b.addEventListener("click", function(){ setDepth(b.getAttribute("data-d")); }); });
  try { var sd = localStorage.getItem("arch-depth"); setDepth(sd !== null ? sd : "0"); } catch(e){ setDepth("0"); }

  /* reading-progress bar */
  var bar = document.getElementById("progress");
  function onScroll(){ var h = document.documentElement, max = h.scrollHeight - h.clientHeight;
    bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + "%"; }
  document.addEventListener("scroll", onScroll, { passive: true }); onScroll();

  /* scrollspy TOC */
  var links = Array.prototype.slice.call(document.querySelectorAll("nav.toc a"));
  var map = {}; links.forEach(function(a){ map[a.getAttribute("href").slice(1)] = a; });
  if (window.IntersectionObserver) {
    var spy = new IntersectionObserver(function(entries){
      entries.forEach(function(en){ if (en.isIntersecting){
        links.forEach(function(a){ a.classList.remove("active"); });
        var a = map[en.target.id]; if (a) a.classList.add("active");
      }});
    }, { rootMargin: "-15% 0px -70% 0px" });
    document.querySelectorAll("main section").forEach(function(s){ spy.observe(s); });
  }

  /* reveal-on-scroll (reduced-motion safe) */
  if (!reduce && window.IntersectionObserver) {
    var rev = new IntersectionObserver(function(entries){
      entries.forEach(function(en){ if (en.isIntersecting){ en.target.classList.add("in"); rev.unobserve(en.target); } });
    }, { rootMargin: "0px 0px -8% 0px" });
    document.querySelectorAll(".reveal").forEach(function(el){ rev.observe(el); });
  } else { document.querySelectorAll(".reveal").forEach(function(el){ el.classList.add("in"); }); }

  /* diagrams: hover-to-explain captions + click-to-jump targets */
  document.querySelectorAll("figure.fig svg").forEach(function(svg){
    var cap = svg.parentNode.querySelector("figcaption"); if (!cap) return;
    var base = cap.innerHTML;
    svg.querySelectorAll("[data-cap]").forEach(function(n){
      n.addEventListener("mouseenter", function(){ cap.textContent = n.getAttribute("data-cap"); });
      n.addEventListener("mouseleave", function(){ cap.innerHTML = base; });
    });
    svg.querySelectorAll("[data-target]").forEach(function(n){
      n.addEventListener("click", function(e){ e.stopPropagation();
        var t = document.querySelector(n.getAttribute("data-target"));
        if (t) t.scrollIntoView({ behavior: reduce ? "auto" : "smooth" }); });
    });
  });
})();"""


def render(doc: DocumentModel, theme: dict[str, str]) -> str:
    """Pure: DocumentModel + theme tokens → a complete HTML document string."""
    merged = {**DEFAULT_THEME, **theme}
    css = build_css(merged)
    toc = _render_toc(doc.sections)
    fig_counter = [0]
    sections_html = "".join(_render_section(s, fig_counter) for s in doc.sections)

    lede = (
        f'<p class="lede">{esc(doc.lede)}</p>' if doc.lede else ""
    )
    fonts_link = (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,500;12..96,600;12..96,700'
        '&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400'
        '&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">'
    )

    theme_icon = (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">'
        '<circle cx="12" cy="12" r="4"/>'
        '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'
        "</svg>"
    )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en" data-theme="light" data-depth="0">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(doc.title)}</title>\n"
        f"{fonts_link}\n"
        f"<style>\n{css}\n</style>\n"
        "</head>\n"
        "<body>\n"
        '<div id="progress" aria-hidden="true"></div>\n'
        '<div class="controls">\n'
        '  <div class="seg depth" role="group" aria-label="Reading depth">\n'
        '    <button data-d="0" aria-pressed="true">Overview</button>\n'
        '    <button data-d="1" aria-pressed="false">Technical</button>\n'
        '    <button data-d="2" aria-pressed="false">Sources</button>\n'
        "  </div>\n"
        '  <button class="toggle" id="themeBtn" aria-label="Toggle colour theme">\n'
        f"    {theme_icon}\n"
        '    <span id="themeLbl">Dark</span>\n'
        "  </button>\n"
        "</div>\n"
        '<header class="mast"><div class="wrap">\n'
        '  <div class="kicker">System Architecture</div>\n'
        f"  <h1>{esc(doc.title)}</h1>\n"
        f"  {lede}\n"
        '  <p class="depthnote">Read at three depths with the control above. '
        "<b>Overview</b> is the plain-English story. <b>Technical</b> reveals the engineering detail. "
        "<b>Sources</b> shows the cited specs and code behind each claim.</p>\n"
        "</div></header>\n"
        '<div class="wrap layout">\n'
        f"{toc}\n"
        "<main>\n"
        f"{sections_html}\n"
        "</main>\n"
        "</div>\n"
        "<footer><div class=\"wrap\">Synthesized whole-system architecture — "
        "organized by structure, not by authoring history. Reads at three depths: "
        "plain-English overview, technical drill-down, and cited sources. Where the "
        "underlying specifications leave a question open, this document says so rather "
        "than guessing.</div></footer>\n"
        f"<script>\n{JS}\n</script>\n"
        "</body>\n"
        "</html>\n"
    )


# ────────────────────────────────── CLI ─────────────────────────────────────

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministically render a DocumentModel JSON to interactive HTML."
    )
    parser.add_argument("document_model", help="Path to a DocumentModel JSON file.")
    parser.add_argument("--theme", help="Optional flat-dict JSON of CSS token overrides.")
    parser.add_argument("--out", help="Output HTML path (default: stdout).")
    args = parser.parse_args(argv)

    raw = Path(args.document_model).read_text(encoding="utf-8")
    doc = DocumentModel.model_validate_json(raw)  # validate against the frozen contract

    theme: dict[str, str] = {}
    if args.theme:
        loaded = json.loads(Path(args.theme).read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            parser.error("--theme must be a flat JSON object of token overrides.")
        theme = {str(k): str(v) for k, v in loaded.items()}

    html_out = render(doc, theme)

    if args.out:
        Path(args.out).write_text(html_out, encoding="utf-8")
    else:
        sys.stdout.write(html_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
