#!/usr/bin/env python3
"""Deterministic HTML renderer for spec-kit-atlas (renderer v2 — spec 001).

INPUT  : a `DocumentModel` JSON (the compose output; see schema.py).
OUTPUT : one self-contained, interactive HTML storybook in the editorial design
         system — the visual contract at `skill/templates/storybook.html`.

This module is PURE: stdlib only, NO LLM, NO network at render time, NO timestamps,
NO randomness. Identical input bytes → identical output bytes. The renderer never
invents prose and never injects source identifiers into the narrative body.

Renderer v2 (spec 001) replaces the old shell with the editorial design system:
  - warm light palette (light-only; no dark toggle), Fraunces / Newsreader / Spline Sans Mono
  - per-section disclosure (technical detail inside a <details> per section) — no global depth
  - inline source-typed citation chips + a doc-wide References appendix
  - eight hand-laid SVG diagram layouts, each with its own semantically-appropriate,
    reduced-motion/print-safe entrance animation (motion fitted to each layout's grammar)

Three clean stages are honoured: composition (the DocumentModel) ≠ markup (this renderer) ≠
theme (a flat dict of CSS custom-property tokens). The faithfulness engine (adapters, reconcile,
verify.py) is unaffected — verify.py validates the IR, never the HTML.

CLI:
    uv run python skill/scripts/render.py <document_model.json> [--theme <theme.json>] [--out <out.html>]
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import sys
from contextvars import ContextVar
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

REPO_URL = "https://github.com/ashbrener/spec-kit-atlas"

# ────────────────────────────── default reference theme ─────────────────────
# The editorial design-system palette + fonts. A --theme JSON is a *flat* dict of
# these keys; any subset overrides the defaults. Keys map 1:1 to CSS custom properties.
# (Light-only by design — there is no dark variant.)

DEFAULT_THEME: dict[str, str] = {
    "ink": "#16140f",
    "paper": "#f4f0e6",
    "paper-2": "#ebe5d6",
    "gold": "#a8742a",
    "gold-bright": "#cf9a3c",
    "red": "#9b3022",
    "green": "#3f5d3a",
    "blue": "#2c4a63",
    "line": "#cdc4ad",
    "line-dk": "#b3a98d",
    "shadow": "rgba(40,32,16,.16)",
    "acc-plan": "#3f6661",     # source-type accents (spec 011): muted teal (plan) + plum (research),
    "acc-research": "#6a4a63", # tuned to the warm register; spec/code/adr/narrative reuse gold/green/red/blue.
    "font-display": "'Fraunces', Georgia, serif",
    "font-body": "'Newsreader', Georgia, serif",
    "font-mono": "'Spline Sans Mono', ui-monospace, Menlo, monospace",
}

# SourceType → the citation chip's short type token (drives the typed badge colour).
SOURCE_T = {
    SourceType.SPEC: "spec",
    SourceType.CODE: "code",
    SourceType.DESIGN_DOC: "doc",
    SourceType.ADR: "adr",
}

# Source-category taxonomy (spec 011): every chip/source-page → one of six categories (+ neutral
# 'source' default), driving a consistent accent. Colour is ALWAYS paired with this label, never the
# sole signal. Chips carry no kind, so the category is derived from SourceType + the locator filename.
_CATEGORY_LABEL = {"spec": "Spec", "plan": "Plan", "adr": "ADR", "research": "Research",
                   "code": "Code", "narrative": "Narrative", "source": "Source"}


def _source_category(ref: SourceType) -> str:
    """Six-category identity for a citation chip — total (unknown → 'source')."""
    t = ref.type
    if t is SourceType.ADR:
        return "adr"
    if t is SourceType.CODE:
        return "code"
    if t is SourceType.DESIGN_DOC:
        return "narrative"
    if t is SourceType.SPEC:
        base = ref.locator.split("::", 1)[-1].split("#", 1)[0].rsplit("/", 1)[-1].lower()
        return "plan" if base == "plan.md" else "research" if base == "research.md" else "spec"
    return "source"

# CalloutKind → design-system note variant. decision=affirmative (green),
# unspecified=warning (red), evolution=neutral (plain).
CALLOUT_CLASS = {
    CalloutKind.DECISION: "flag-ok",
    CalloutKind.UNSPECIFIED: "flag",
    CalloutKind.EVOLUTION: "",
}
CALLOUT_DEFAULT_TAG = {
    CalloutKind.DECISION: "Decision",
    CalloutKind.UNSPECIFIED: "Unspecified",
    CalloutKind.EVOLUTION: "Evolution",
}

# CoverageStatus value → (pill class, human label).
COVERAGE_PILL = {
    "spec_backed": ("build", "Specified &amp; built"),
    "specced_only": ("buy", "Specified, not in scanned source"),
    "implemented_only": ("hybrid", "Built, not specified"),
    "unknown": ("hard", "Unknown"),
}

# Brand wordmark / colophon labels for the source types present.
SOURCE_LABEL = {"spec": "spec", "code": "code", "doc": "design-doc"}


def esc(s: Optional[str]) -> str:
    """HTML-escape any text from the model (incl. quotes, for attribute safety)."""
    return html.escape(s or "", quote=True)


# ────────────────────────────── brand glyph ─────────────────────────────────
# A neutral geometric mark (an asterisk) — carries no third-party identity. The
# .spin-star group rotates with scroll. Used in the masthead and the sticky nav.

GLYPH = (
    '<svg class="glyph" viewBox="0 0 40 40" role="img" aria-label="mark" xmlns="http://www.w3.org/2000/svg">'
    '<g class="spin-star"><g transform="translate(20,20)" stroke="#16140f" stroke-width="3" stroke-linecap="round">'
    '<line x1="-13" y1="0" x2="13" y2="0"/><line x1="0" y1="-13" x2="0" y2="13"/>'
    '<line x1="-9.2" y1="-9.2" x2="9.2" y2="9.2"/><line x1="-9.2" y1="9.2" x2="9.2" y2="-9.2"/>'
    "</g></g></svg>"
)


# ────────────────────────────────── CSS ─────────────────────────────────────

def _theme_vars(theme: dict[str, str]) -> str:
    return "\n".join(f"  --{k}: {v};" for k, v in theme.items())


_FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;0,9..144,900;1,9..144,500"
    "&family=Spline+Sans+Mono:wght@400;500;600"
    "&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&display=swap');\n"
)

# Static stylesheet — ported from the visual contract (skill/templates/storybook.html),
# with fonts and key surfaces referenced through CSS variables so a --theme retint applies
# without re-layout. References var(--*) only; no Python interpolation here.
_STATIC_CSS = """
  :root{ color-scheme: light; }
  html{ color-scheme: light; background-color: var(--paper) !important; scroll-behavior: smooth; }
  body{ background-color: var(--paper) !important; min-height: 100vh; }
  @media (prefers-reduced-motion: reduce){ html{ scroll-behavior: auto; } }

  *{ box-sizing: border-box; margin: 0; padding: 0; }
  body{
    color: var(--ink);
    font-family: var(--font-body);
    font-size: 18px; line-height: 1.62;
    background-image:
      radial-gradient(circle at 12% 8%, rgba(168,116,42,.05), transparent 40%),
      radial-gradient(circle at 88% 92%, rgba(44,74,99,.05), transparent 42%);
    background-attachment: fixed;
    -webkit-font-smoothing: antialiased;
  }
  .grain{ position: fixed; inset: 0; pointer-events: none; z-index: 1; opacity: .06;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.5'/%3E%3C/svg%3E"); }

  .wrap{ max-width: 1180px; margin: 0 auto; padding: 0 28px; position: relative; z-index: 2; }

  /* brand */
  .spin-star{ transform-box: fill-box; transform-origin: center; transform: rotate(var(--spin,0deg)); transition: transform .35s var(--ease); will-change: transform; }
  .brand-logo{ display: inline-flex; align-items: center; gap: 11px; margin-bottom: 22px; text-decoration: none; color: var(--ink); }
  .glyph{ display: block; height: 32px; width: 32px; }
  .brand-word{ font-family: var(--font-display); font-weight: 900; font-size: 22px; letter-spacing: -.01em; }
  nav.toc .brand-mark{ display: flex; align-items: center; gap: 8px; flex: 0 0 auto; text-decoration: none; color: var(--ink);
    opacity: 0; max-width: 0; overflow: hidden; padding-right: 0; margin-right: 0; border-right: 1px solid transparent;
    transition: opacity .3s ease, max-width .35s ease, padding-right .35s ease, margin-right .35s ease; }
  nav.toc .brand-mark.show{ opacity: 1; max-width: 260px; padding-right: 16px; margin-right: 8px; border-right-color: var(--line-dk); }
  nav.toc .brand-mark .glyph{ height: 20px; width: 20px; }
  nav.toc .brand-mark .brand-word{ font-size: 16px; }

  /* masthead */
  header.mast{ border-bottom: 3px double var(--ink); padding: 40px 0 22px; margin-bottom: 8px; }
  .kicker{ font-family: var(--font-mono); font-size: 11px; letter-spacing: .32em; text-transform: uppercase; color: var(--gold);
    display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; border-bottom: 1px solid var(--line); padding-bottom: 10px; margin-bottom: 18px; }
  h1.title{ font-family: var(--font-display); font-weight: 900; font-size: clamp(2.4rem,6vw,4.6rem); line-height: .96; letter-spacing: -.02em; }
  h1.title em{ font-style: italic; font-weight: 500; color: var(--gold); }
  .dek{ font-size: clamp(1.05rem,2vw,1.32rem); max-width: 720px; margin-top: 18px; color: #42392a; line-height: 1.5; }
  .meta-row{ display: flex; gap: 26px; flex-wrap: wrap; margin-top: 22px; font-family: var(--font-mono); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: #5b513c; }
  .meta-row b{ color: var(--ink); font-weight: 600; }

  /* sticky nav */
  nav.toc{ position: sticky; top: 0; z-index: 50; background: rgba(244,240,230,.96);
    -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--line-dk); box-shadow: 0 1px 0 rgba(255,255,255,.5) inset, 0 6px 18px -12px var(--shadow);
    padding: 10px 0; margin-bottom: 46px; }
  nav.toc .wrap{ display: flex; gap: 5px; align-items: center; }
  nav.toc .links{ display: flex; gap: 4px; align-items: center; flex: 1; overflow-x: auto; scrollbar-width: none; -ms-overflow-style: none; }
  nav.toc .links::-webkit-scrollbar{ display: none; }
  /* scroll affordance as capabilities grow (spec 011 US3): the link row already scrolls (overflow-x)
     and collapses to a hamburger on narrow screens; this fades the right edge to signal "more →". */
  nav.toc .links{ -webkit-mask-image: linear-gradient(90deg, #000 calc(100% - 22px), transparent); mask-image: linear-gradient(90deg, #000 calc(100% - 22px), transparent); }
  nav.toc a{ font-family: var(--font-mono); font-size: 10.5px; letter-spacing: .05em; text-transform: uppercase; color: #5b513c; text-decoration: none;
    padding: 6px 10px; border: 1px solid transparent; border-radius: 3px; transition: all .18s; white-space: nowrap; flex: 0 0 auto; }
  nav.toc a:hover, nav.toc a:focus-visible{ color: var(--ink); border-color: var(--line-dk); background: var(--paper-2); outline: none; }
  nav.toc a.active{ color: var(--gold); border-color: var(--gold); background: rgba(168,116,42,.08); font-weight: 600; }
  nav.toc .navbtn{ display: none; align-items: center; gap: 9px; width: 100%; background: none; border: none; cursor: pointer;
    font-family: var(--font-mono); font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--ink); padding: 4px 2px; }
  nav.toc .navbtn .lbl{ flex: 1; text-align: left; color: #5b513c; }
  nav.toc .navbtn .cur{ color: var(--ink); font-weight: 600; }
  nav.toc .navbtn .bars{ display: inline-flex; flex-direction: column; gap: 3px; width: 20px; }
  nav.toc .navbtn .bars span{ height: 2px; background: var(--ink); border-radius: 2px; transition: transform .25s, opacity .2s; }
  nav.toc.open .navbtn .bars span:nth-child(1){ transform: translateY(5px) rotate(45deg); }
  nav.toc.open .navbtn .bars span:nth-child(2){ opacity: 0; }
  nav.toc.open .navbtn .bars span:nth-child(3){ transform: translateY(-5px) rotate(-45deg); }

  /* sections + type */
  section{ margin-bottom: 64px; scroll-margin-top: 64px; }
  .sec-num{ font-family: var(--font-mono); font-size: 12px; letter-spacing: .2em; color: var(--gold); text-transform: uppercase; }
  h2{ font-family: var(--font-display); font-weight: 900; font-size: clamp(1.9rem,4vw,3rem); line-height: 1.04; letter-spacing: -.015em; margin: 6px 0 8px; }
  h3{ font-family: var(--font-display); font-weight: 600; font-size: 1.45rem; margin: 34px 0 12px; letter-spacing: -.01em; }
  h4{ font-family: var(--font-mono); font-size: 12px; letter-spacing: .16em; text-transform: uppercase; color: var(--gold); margin: 24px 0 8px; }
  p{ margin-bottom: 16px; max-width: 74ch; }
  p.lead{ font-size: 1.22rem; line-height: 1.5; color: #2e2a20; }
  p.pull{ border-left: 3px solid var(--gold); padding: 6px 0 6px 22px; margin: 30px 0; font-family: var(--font-display); font-style: italic; font-size: 1.5rem; line-height: 1.32; color: #2e2a20; max-width: none; }
  a{ color: var(--blue); text-underline-offset: 3px; }
  strong{ font-weight: 600; color: var(--ink); }
  em.term{ font-style: italic; color: var(--gold); font-weight: 500; }
  .mono{ font-family: var(--font-mono); font-size: .82em; }
  .divider{ border: none; border-top: 1px solid var(--line); margin: 48px 0; }

  /* callouts */
  .note{ background: var(--paper-2); border: 1px solid var(--line-dk); border-radius: 4px; padding: 18px 22px; margin: 24px 0; font-size: .96rem; line-height: 1.55; max-width: 74ch; }
  .note .tag{ font-family: var(--font-mono); font-size: 10px; letter-spacing: .18em; text-transform: uppercase; color: var(--gold); display: block; margin-bottom: 6px; }
  .note.flag{ border-left: 3px solid var(--red); }
  .note.flag .tag{ color: var(--red); }
  .note.flag-ok{ border-left: 3px solid var(--green); }
  .note.flag-ok .tag{ color: var(--green); }

  /* tables */
  .tbl-scroll{ overflow-x: auto; -webkit-overflow-scrolling: touch; }
  table.tbl{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: .93rem; }
  table.tbl th{ font-family: var(--font-mono); font-size: 10px; letter-spacing: .1em; text-transform: uppercase; text-align: left; padding: 10px 12px; border-bottom: 2px solid var(--ink); color: #42392a; vertical-align: bottom; }
  table.tbl td{ padding: 11px 12px; border-bottom: 1px solid var(--line); vertical-align: top; line-height: 1.42; }
  table.tbl tr:hover td{ background: rgba(168,116,42,.05); }
  .cov-note{ font-size: 12.5px; color: #7d705a; margin-top: 3px; }
  td.covsrc{ display: flex; flex-wrap: wrap; gap: 6px; }
  .pill{ display: inline-block; font-family: var(--font-mono); font-size: 9.5px; letter-spacing: .06em; text-transform: uppercase; padding: 2px 7px; border-radius: 10px; font-weight: 600; white-space: nowrap; }
  .pill.build{ background: #d8e4d2; color: #2f4628; }
  .pill.buy{ background: #f0dccb; color: #7a4316; }
  .pill.hybrid{ background: #d9e2ea; color: #274056; }
  .pill.hard{ background: #efd0c9; color: #7c2618; }

  /* per-section disclosure */
  .mod{ border: 1px solid var(--line-dk); border-radius: 5px; margin: 24px 0 12px; overflow: hidden; background: rgba(255,253,247,.5); transition: box-shadow .2s; }
  .mod[open]{ box-shadow: 0 8px 30px var(--shadow); }
  .mod summary{ cursor: pointer; list-style: none; padding: 18px 22px; display: flex; align-items: center; gap: 18px; transition: background .18s; }
  .mod summary::-webkit-details-marker{ display: none; }
  .mod summary:hover{ background: var(--paper-2); }
  .mod .mt{ font-family: var(--font-display); font-weight: 600; font-size: 1.16rem; flex: 1; letter-spacing: -.01em; }
  .mod .mx{ font-family: var(--font-mono); font-size: 20px; color: var(--gold); transition: transform .25s; }
  .mod[open] .mx{ transform: rotate(45deg); }
  .mod .body{ padding: 4px 24px 24px; border-top: 1px solid var(--line); }
  .mod .body p{ font-size: .97rem; }
  .what{ font-family: var(--font-mono); font-size: 10px; letter-spacing: .14em; text-transform: uppercase; color: #7d705a; margin: 16px 0 4px; }

  /* per-section sources line + inline citation chips */
  .srcline{ margin: 18px 0 4px; font-family: var(--font-mono); font-size: 11px; color: #7d705a; display: flex; flex-wrap: wrap; gap: 8px 10px; align-items: baseline; }
  .srcline .srclab{ letter-spacing: .16em; text-transform: uppercase; color: #9a8e74; }
  .srcline a.ref{ color: var(--blue); text-decoration: none; border-bottom: 1px solid rgba(44,74,99,.3); }
  .srcline a.ref:hover{ border-bottom-color: var(--blue); }
  .cite-t{ display: inline-block; font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; padding: 1px 5px; border-radius: 4px; color: #fff; margin-right: 5px; }
  .cite-t.spec{ background: var(--gold); }
  .cite-t.code{ background: var(--green); }
  .cite-t.adr{ background: var(--red); }
  .cite-t.narrative{ background: var(--blue); }
  .cite-t.plan{ background: var(--acc-plan); }
  .cite-t.research{ background: var(--acc-research); }
  .cite-t.source{ background: var(--line-dk); }

  /* diagram frames */
  figure{ margin: 34px 0; border: 1px solid var(--line-dk); border-radius: 6px; background: #fbf9f2; padding: 8px; box-shadow: 0 4px 20px var(--shadow); overflow: hidden; }
  figure svg{ display: block; width: 100%; height: auto; }
  figcaption{ font-family: var(--font-mono); font-size: 11px; letter-spacing: .06em; color: #6b5f48; padding: 10px 14px 6px; border-top: 1px solid var(--line); margin-top: 8px; text-transform: uppercase; }
  figcaption b{ color: var(--ink); }

  /* SVG diagram primitives — ALL visual styling (fill / stroke / font / weight) is emitted
     INLINE (literal values) on each element, so diagrams render correctly even where the
     document <style> is not cascaded into inline SVG (QuickLook, mail/preview panes, some PDF
     paths). CSS here carries only the pointer affordance; motion rules live further below. */
  .d-node.act{ cursor: pointer; }

  /* ===== per-layout diagram MOTION (fitted to each layout's grammar) ===== */
  figure{ opacity: 0; transform: translateY(20px); transition: opacity .7s ease, transform .7s var(--ease); }
  figure.in{ opacity: 1; transform: none; }

  @keyframes partIn{ from{ opacity: 0; } to{ opacity: 1; } }
  @keyframes popIn{ 0%{ opacity: 0; transform: scale(.4);} 60%{ transform: scale(1.12);} 100%{ opacity: 1; transform: scale(1);} }
  @keyframes drawIn{ to{ stroke-dashoffset: 0; } }
  @keyframes sweep{ from{ transform: rotate(-90deg); opacity: 0;} 40%{ opacity: 1;} to{ transform: rotate(0); opacity: 1;} }
  @keyframes layerIn{ from{ opacity: 0; transform: translateY(14px);} to{ opacity: 1; transform: none;} }
  @keyframes riseIn{ from{ opacity: 0; transform: translateY(10px);} to{ opacity: 1; transform: none;} }
  @keyframes traceMove{ 0%{ stroke-dashoffset: 1600; opacity: 0;} 8%{ opacity: .9;} 90%{ opacity: .9;} 100%{ stroke-dashoffset: -40; opacity: 0;} }

  /* staggered delays (shared) */
  .a0{ animation-delay: .06s; } .a1{ animation-delay: .14s; } .a2{ animation-delay: .22s; }
  .a3{ animation-delay: .30s; } .a4{ animation-delay: .38s; } .a5{ animation-delay: .46s; }
  .a6{ animation-delay: .54s; } .a7{ animation-delay: .62s; } .a8{ animation-delay: .70s; }
  .a9{ animation-delay: .78s; } .a10{ animation-delay: .86s; } .a11{ animation-delay: .94s; }

  /* pipeline — stages illuminate L→R */
  .fig-pipeline.in svg .anim{ animation: popIn .5s var(--ease) both; transform-box: fill-box; transform-origin: center; }
  /* flow — nodes drop in top→bottom; a comet traces the spine (flow is continuous) */
  .fig-flow.in svg .anim{ animation: riseIn .5s var(--ease) both; }
  .flow-trace{ fill: none; stroke: var(--gold-bright); stroke-width: 3; stroke-linecap: round; stroke-dasharray: 26 1600; stroke-dashoffset: 1600; opacity: 0; }
  .fig-flow.in .flow-trace{ animation: traceMove 3s cubic-bezier(.4,0,.2,1) .8s infinite; }
  /* ladder — rungs draw in order */
  .fig-ladder.in svg .anim{ animation: riseIn .5s var(--ease) both; }
  /* mapping — left column, then links draw, then right column */
  .fig-mapping.in svg .lm-l, .fig-mapping.in svg .lm-r{ animation: partIn .45s ease both; }
  .fig-mapping.in svg .lm-r{ animation-delay: .7s; }
  .fig-mapping.in svg .lm-k{ stroke-dasharray: 760; stroke-dashoffset: 760; animation: drawIn .5s ease .45s both; }
  /* panel — cards stagger-fade */
  .fig-panel.in svg .anim{ animation: partIn .45s ease both; }
  /* hub — core pops, spokes draw outward, nodes fade, ring sweeps */
  .fig-hub.in svg .hub-core{ animation: popIn .5s var(--ease) .05s both; transform-box: fill-box; transform-origin: center; }
  .fig-hub.in svg .hub-spoke{ stroke-dasharray: 240; stroke-dashoffset: 240; animation: drawIn .5s ease .32s both; }
  .fig-hub.in svg .hub-node{ animation: partIn .45s ease .55s both; }
  .fig-hub.in svg .hub-ring{ transform-box: fill-box; transform-origin: center; animation: sweep .7s var(--ease) .85s both; }
  /* stack — layers build bottom-up (bottom layer carries .a0) */
  .fig-stack.in svg .stack-layer{ animation: layerIn .55s var(--ease) both; }
  /* timeline — line draws L→R, nodes light in order (scroll-scrubbed via --p) */
  .fig-timeline svg .tl-line{ stroke-dasharray: 900; stroke-dashoffset: calc(900 - 900 * var(--p,0)); }
  .fig-timeline svg .tl-node{ opacity: 0; transform: scale(.4); transform-box: fill-box; transform-origin: center; transition: opacity .25s, transform .25s; }
  .fig-timeline svg .tl-node.lit{ opacity: 1; transform: scale(1); }
  .fig-timeline.in:not(.scrubbed) svg .tl-line{ stroke-dashoffset: 0; transition: stroke-dashoffset 1s ease; }
  .fig-timeline.in:not(.scrubbed) svg .tl-node{ opacity: 1; transform: scale(1); }

  /* footer */
  footer{ border-top: 3px double var(--ink); margin-top: 30px; padding: 30px 0 70px; font-size: .86rem; color: #5b513c; }
  footer h3{ margin-top: 6px; }
  footer .reflist{ columns: 2; column-gap: 40px; font-size: .8rem; line-height: 1.55; margin-top: 16px; }
  footer .reflist p{ margin-bottom: 8px; max-width: none; break-inside: avoid; }
  .reftype{ font-family: var(--font-mono); font-size: 9px; text-transform: uppercase; letter-spacing: .08em; color: #fff; padding: 1px 5px; border-radius: 4px; margin-right: 6px; }
  .reftype.spec{ background: var(--gold); } .reftype.code{ background: var(--green); } .reftype.adr{ background: var(--red); }
  .reftype.narrative{ background: var(--blue); } .reftype.plan{ background: var(--acc-plan); } .reftype.research{ background: var(--acc-research); } .reftype.source{ background: var(--line-dk); }
  .colophon{ width: 100%; border-collapse: collapse; margin-top: 22px; font-family: var(--font-mono); font-size: 11px; background: var(--paper-2); border: 1px solid var(--line-dk); border-radius: 5px; overflow: hidden; }
  .colophon th, .colophon td{ text-align: left; padding: 9px 16px; border-bottom: 1px solid var(--line); vertical-align: top; line-height: 1.5; }
  .colophon tbody tr:last-child th, .colophon tbody tr:last-child td{ border-bottom: none; }
  .colophon tbody th{ width: 120px; white-space: nowrap; letter-spacing: .12em; text-transform: uppercase; color: var(--gold); font-weight: 600; background: rgba(168,116,42,.06); border-right: 1px solid var(--line); }
  .colophon td{ color: #3a3324; }
  .vtag{ display: inline-block; background: var(--ink); color: var(--paper); padding: 2px 9px; border-radius: 10px; font-size: 10px; letter-spacing: .06em; font-weight: 600; }
  .genline{ margin-top: 26px; padding-top: 16px; border-top: 1px solid var(--line); font-family: var(--font-mono); font-size: 10px; line-height: 1.7; letter-spacing: .04em; color: #7d705a; max-width: none; text-transform: uppercase; }
  .genline .gm{ color: var(--green); margin-right: 6px; }
  .genline a{ color: var(--blue); text-decoration: none; border-bottom: 1px solid rgba(44,74,99,.4); }
  .genline a:hover{ border-bottom-color: var(--blue); }

  ul.clean{ list-style: none; margin: 12px 0; }
  ul.clean li{ padding: 5px 0 5px 22px; position: relative; font-size: .97rem; line-height: 1.45; }
  ul.clean li::before{ content: "\\2192"; position: absolute; left: 0; color: var(--gold); font-family: var(--font-mono); }

  ol.steps{ margin: 14px 0 14px 4px; counter-reset: s; list-style: none; }
  ol.steps li{ counter-increment: s; padding: 8px 0 8px 40px; position: relative; border-bottom: 1px dotted var(--line); font-size: .96rem; }
  ol.steps li::before{ content: counter(s, decimal-leading-zero); position: absolute; left: 0; top: 8px; font-family: var(--font-mono); font-size: 11px; color: var(--gold); font-weight: 600; }

  .anchor{ display: block; position: relative; top: -64px; visibility: hidden; }

  /* responsive */
  @media (max-width: 900px){ body{ font-size: 17px; } .wrap{ padding: 0 22px; } }
  @media (max-width: 680px){
    body{ font-size: 16px; line-height: 1.58; }
    .wrap{ padding: 0 18px; }
    header.mast{ padding: 28px 0 18px; }
    .kicker{ font-size: 9.5px; letter-spacing: .2em; }
    .dek{ font-size: 1.06rem; }
    .meta-row{ gap: 14px 20px; font-size: 10px; }
    section{ margin-bottom: 48px; scroll-margin-top: 60px; }
    h2{ font-size: 1.7rem; } h3{ font-size: 1.25rem; }
    p, p.lead{ max-width: none; } p.lead{ font-size: 1.1rem; }
    p.pull{ font-size: 1.22rem; padding-left: 16px; }
    .note{ padding: 15px 16px; }
    .mod summary{ padding: 14px 16px; gap: 12px; }
    .mod .mt{ font-size: 1.02rem; }
    .mod .body{ padding: 4px 16px 18px; }
    nav.toc{ padding: 0; margin-bottom: 34px; }
    nav.toc .navbtn{ display: flex; padding: 13px 0; flex: 1; }
    nav.toc .links{ position: absolute; left: 0; right: 0; top: 100%; flex-direction: column; align-items: stretch; gap: 0;
      background: var(--paper); border-bottom: 1px solid var(--line-dk); box-shadow: 0 14px 24px -10px var(--shadow);
      max-height: 0; overflow: hidden; transition: max-height .32s ease; padding: 0 18px; }
    nav.toc.open .links{ max-height: 80vh; overflow-y: auto; padding: 6px 18px 12px; }
    nav.toc .links a{ font-size: 12px; padding: 11px 6px; border: none; border-bottom: 1px solid var(--line); border-radius: 0; white-space: normal; }
    nav.toc .links a:last-child{ border-bottom: none; }
    table.tbl{ min-width: 520px; }
    .colophon{ font-size: 10px; }
    footer .reflist{ columns: 1; }
  }
  @media (max-width: 400px){ h1.title{ font-size: 2.1rem; } nav.toc .navbtn .lbl{ font-size: 10px; } }

  /* reduced-motion + print + no-JS: settle every diagram to its final static state */
  @media (prefers-reduced-motion: reduce){
    *{ animation: none !important; transition: none !important; scroll-behavior: auto !important; }
    figure{ opacity: 1 !important; transform: none !important; }
    figure svg *{ opacity: 1 !important; transform: none !important; }
    .tl-line, .hub-spoke, .lm-k{ stroke-dashoffset: 0 !important; }
    .flow-trace{ display: none !important; }
    .spin-star{ transform: none !important; }
  }
  @media print{
    figure{ opacity: 1 !important; transform: none !important; break-inside: avoid; }
    figure svg *{ opacity: 1 !important; transform: none !important; }
    .tl-line, .hub-spoke, .lm-k{ stroke-dashoffset: 0 !important; }
    .flow-trace{ display: none !important; }
  }
  @media (scripting: none){
    figure{ opacity: 1 !important; transform: none !important; }
    figure svg *{ opacity: 1 !important; transform: none !important; }
    .tl-line, .hub-spoke, .lm-k{ stroke-dashoffset: 0 !important; }
  }
"""


# Melded SITE layer (spec 006): per-tier disclosures, build-status badges + fading, human-titled
# source tables, nested nav. Appended to the static CSS; uses the same design tokens.
_MELD_CSS = """
  /* build-status badges */
  .bstatus{ display:inline-block; font-family:var(--font-mono); font-size:9.5px; letter-spacing:.08em;
    text-transform:uppercase; font-weight:600; padding:2px 7px; border-radius:10px; vertical-align:middle;
    margin-left:10px; }
  h2 .bstatus{ margin-left:14px; }
  .bs-built{ background:#dce8d6; color:#37502f; }
  .bs-partial{ background:#efe3c4; color:#6e5413; }
  .bs-planned{ background:#e7ded0; color:#7a5a2e; }
  /* build status reads pre-attentively (spec 011): planned faded + muted heading + dashed left rule;
     partial intermediate (solid rule + warm heading); built full weight. Colour/fade never the sole
     signal — the .bstatus badge label is always present. Print/forced-colors safe. */
  .planned{ opacity:.62; }
  section.planned{ border-left:3px dashed var(--line-dk); padding-left:22px; }
  section.planned > h2{ opacity:1; color:var(--line-dk); }       /* muted heading via colour, not just opacity */
  section.partial{ border-left:3px solid var(--line); padding-left:22px; }
  section.partial > h2{ color:var(--gold); }                     /* subtle warm shift — between built and planned */
  details.tier-mod.planned{ opacity:1; }
  details.tier-mod.planned > .body{ opacity:.6; border-left:2px dashed var(--line-dk); padding-left:14px; }
  @media print{ .planned, details.tier-mod.planned > .body{ opacity:1 !important; } }
  /* per-tier disclosure label */
  details.tier-mod > summary .mt{ font-family:var(--font-display); }
  /* human-titled source table */
  .srctbl-wrap{ margin:22px 0 4px; }
  .srctbl{ width:100%; }
  .srctbl th{ font-family:var(--font-mono); font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:#7d705a; }
  .srctbl td{ font-size:.92rem; }
  .srctbl .srcgo{ font-family:var(--font-mono); font-size:12px; color:var(--gold); text-decoration:none; white-space:nowrap; }
  /* nested nav */
  nav.toc .toc-tier{ display:block; font-family:var(--font-mono); font-size:11px; color:#7d705a;
    padding:2px 0 2px 16px; text-decoration:none; }
  nav.toc .toc-tier:hover{ color:var(--gold); }
"""


def build_css(theme: dict[str, str]) -> str:
    root = ":root{\n" + _theme_vars(theme) + "\n  --ease: cubic-bezier(.22,.61,.36,1);\n}\n"
    return _FONT_IMPORT + root + _STATIC_CSS + _MELD_CSS


# ────────────────────────── diagram → SVG layout ────────────────────────────
# Each layout is a pure function (DiagramGraph) -> (svg-body, width, height) with FIXED,
# hand-laid coordinates. No physics, no randomness: same graph → same bytes. Every colour
# is a CSS var so a theme change needs no re-layout. Nodes with a caption get data-cap
# (hover-to-explain); nodes with a target get data-target (click-to-jump). Each layout also
# tags its elements with the motion-hook classes its prescribed animation keys off.

# Diagram palette — LITERAL hex/font values, emitted INLINE on every SVG element (mirrors the
# visual contract skill/templates/storybook.html). Diagram internals use this fixed warm palette
# and are not --theme-retinted; the rest of the page still themes via CSS variables.
_DINK = "#16140f"
_DMUT = "#3a3324"
_DFAINT = "#7d705a"
_DGOLD = "#a8742a"
_DGOLDB = "#cf9a3c"
_DPAPER = "#f4f0e6"
_DPANEL = "#fbf9f2"
_DLINE = "#cdc4ad"
_DLINEDK = "#b3a98d"
_DBLUE = "#2c4a63"
_DRED = "#9b3022"
_DGREEN = "#3f5d3a"
_FMONO = "'Spline Sans Mono', ui-monospace, Menlo, monospace"
_FDISP = "'Fraunces', Georgia, serif"

# cls → text fill (emitted inline, not via CSS class).
_CLS_FILL = {"t": _DINK, "tm": _DMUT, "tlab": _DFAINT, "tm acc": _DGOLD, "acc": _DGOLD}
_CLS_SPACE = {"tlab": ".12em"}


def _node_group_open(node: DiagramNode, extra: str = "") -> str:
    """Open an interactive node <g> carrying the motion-hook + hover/jump data attributes.
    Visual fill/stroke/font live INLINE on the child shapes/text, not on this group."""
    cls = "d-node act" + ((" " + extra) if extra else "")
    attrs = [f'class="{cls}"']
    if node.caption:
        attrs.append(f'data-cap="{esc(node.caption)}"')
    if node.target:
        attrs.append(f'data-target="#{esc(node.target)}"')
    return f"<g {' '.join(attrs)}>"


def _svg_text(x: float, y: float, cls: str, size: float, text: str, *,
              anchor: str = "start", weight: Optional[int] = None,
              font: str = _FMONO, fill: Optional[str] = None) -> str:
    """A diagram text label — font-family + fill emitted INLINE (literal) for portability."""
    f = fill or _CLS_FILL.get(cls, _DMUT)
    sp = _CLS_SPACE.get(cls)
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    w = f' font-weight="{weight}"' if weight else ""
    s = f' letter-spacing="{sp}"' if sp else ""
    return (f'<text x="{x:g}" y="{y:g}" font-family="{font}" font-size="{size:g}" '
            f'fill="{f}"{w}{s}{a}>{esc(text)}</text>')


def _rect(x: float, y: float, w: float, h: float, rx: int, *,
          fill: str = _DPANEL, stroke: str = _DLINEDK) -> str:
    return (f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}"/>')


def _markers(fig_id: str) -> str:
    return (
        f"<defs>"
        f'<marker id="{fig_id}-af" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">'
        f'<path d="M0,0 L8,4.5 L0,9 z" fill="{_DGOLD}"/></marker>'
        f'<marker id="{fig_id}-am" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">'
        f'<path d="M0,0 L8,4.5 L0,9 z" fill="{_DLINEDK}"/></marker>'
        f"</defs>"
    )


def _edge_path(d: str, fig_id: str, emphasis: bool, *, cls: str = "") -> str:
    stroke = _DGOLD if emphasis else _DLINEDK
    width = 2 if emphasis else 1.6
    marker = f"{fig_id}-af" if emphasis else f"{fig_id}-am"
    c = f' class="{cls}"' if cls else ""
    return (f'<path{c} d="{d}" fill="none" stroke="{stroke}" stroke-width="{width:g}" '
            f'marker-end="url(#{marker})"/>')


def _ai(i: int) -> str:
    """Stagger-delay class for index i (clamped to the defined a0..a11 set)."""
    return f"a{min(i, 11)}"


def _layout_pipeline(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """Nodes left→right as a horizontal pipeline; stages illuminate in sequence."""
    n = len(graph.nodes)
    width, margin_x, top, nh, gap = 1000, 40, 70, 64, 28
    nw = (width - 2 * margin_x - max(0, n - 1) * gap) / max(1, n)
    height = top + nh + 70
    pos: dict[str, tuple[float, float]] = {}
    parts = [_markers(fig_id)]
    for i, node in enumerate(graph.nodes):
        x = margin_x + i * (nw + gap)
        y = top
        pos[node.id] = (x, y)
        parts.append(_node_group_open(node, f"anim {_ai(i)}"))
        parts.append(_rect(x, y, nw, nh, 12))
        parts.append(_svg_text(x + nw / 2, y + nh / 2 + 4, "tm", 12, node.label, anchor="middle"))
        parts.append("</g>")
    parts.append(_edges_horizontal(graph.edges, pos, fig_id, nw, nh))
    return "".join(parts), width, height


def _layout_flow(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """Nodes stacked down the centre, connected top→bottom; a comet traces the spine."""
    n = len(graph.nodes)
    nw, nh, gap = 280, 56, 46
    top = 24
    width = 1000
    cx = width / 2
    height = top + n * nh + max(0, n - 1) * gap + 40
    pos: dict[str, tuple[float, float]] = {}
    parts = [_markers(fig_id)]
    for i, node in enumerate(graph.nodes):
        y = top + i * (nh + gap)
        x = cx - nw / 2
        pos[node.id] = (x, y)
        rx = 26 if i == 0 or i == n - 1 else 12
        parts.append(_node_group_open(node, f"anim {_ai(i)}"))
        parts.append(_rect(x, y, nw, nh, rx))
        parts.append(_svg_text(cx, y + nh / 2 + 4, "t", 13, node.label, anchor="middle"))
        parts.append("</g>")
    parts.append(_edges_vertical(graph.edges, pos, fig_id, nw, nh, cx))
    if n >= 2:
        y0 = top + nh
        y1 = top + (n - 1) * (nh + gap)
        parts.append(f'<path class="flow-trace" d="M{cx:g} {y0:g} V {y1:g}" fill="none"/>')
    return "".join(parts), width, height


def _layout_ladder(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """An ordered, rising ladder; rungs draw in order, terminal rung accent-outlined."""
    n = len(graph.nodes)
    if n == 0:
        return _markers(fig_id), 940, 120
    width = 1000
    x0, w, rh = 40, 96, 38
    base_y, rise = 40 + (n - 1) * 22, 22
    height = base_y + rh + 40
    span = width - x0 - w - 30
    gap = span / (n - 1) if n > 1 else 0
    parts = [_markers(fig_id)]
    parts.append(f'<line x1="{x0}" y1="{base_y + rh + 14:g}" x2="{width - 30}" y2="{base_y + rh + 14:g}" stroke="{_DLINE}"/>')
    for i, node in enumerate(graph.nodes):
        x = x0 + i * gap
        y = base_y - i * rise
        terminal = i == n - 1
        parts.append(_node_group_open(node, f"anim {_ai(i)}"))
        parts.append(_rect(x, y, w, rh, 8, stroke=_DGOLD if terminal else _DLINEDK))
        parts.append(_svg_text(x + 9, y + 15, "tlab", 9, str(i)))
        parts.append(_svg_text(x + 9, y + 30, "tm acc" if terminal else "tm", 9.5, node.label))
        parts.append("</g>")
        if i < n - 1:
            nx = x0 + (i + 1) * gap
            parts.append(_edge_path(f"M{x + w:g} {y + rh / 2:g} H {nx:g}", fig_id, False))
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
        midx = (x1 + x2) / 2
        d = f"M{x1:g} {y1:g} C {midx:g} {y1:g}, {midx:g} {y2:g}, {x2:g} {y2:g}"
        parts.append(_edge_path(d, fig_id, e.emphasis))
        if e.label:
            parts.append(_svg_text(midx, min(y1, y2) - 8, "tm acc" if e.emphasis else "tm", 10.5, e.label, anchor="middle"))
    return "".join(parts)


def _edges_vertical(edges: list[DiagramEdge], pos: dict[str, tuple[float, float]],
                    fig_id: str, nw: int, nh: int, cx: float) -> str:
    parts: list[str] = []
    for e in edges:
        if e.src not in pos or e.dst not in pos:
            continue
        sx, sy = pos[e.src]
        dx, dy = pos[e.dst]
        y1 = sy + nh
        y2 = dy
        parts.append(_edge_path(f"M{cx:g} {y1:g} V {y2:g}", fig_id, e.emphasis))
        if e.label:
            parts.append(_svg_text(cx + 10, (y1 + y2) / 2 + 4, "tm acc" if e.emphasis else "tm", 10.5, e.label))
    return "".join(parts)


def _layout_mapping(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """Two columns connected left→right; left appears, links draw, right appears."""
    srcs = [n for n in graph.nodes if any(e.src == n.id for e in graph.edges)]
    dsts = [n for n in graph.nodes if any(e.dst == n.id for e in graph.edges)
            and not any(e.src == n.id for e in graph.edges)]
    leftovers = [n for n in graph.nodes if n not in srcs and n not in dsts]
    left, right = srcs + leftovers, dsts
    rows = max(len(left), len(right), 1)
    width = 1000
    nw, nh, vgap = 300, 38, 10
    lx, rx, top = 40, width - 40 - nw, 50
    height = top + rows * (nh + vgap) + 20
    pos: dict[str, tuple[float, float]] = {}
    parts = [_markers(fig_id)]
    parts.append(_svg_text(lx, 34, "tlab", 11, "FROM"))
    parts.append(_svg_text(rx, 34, "tlab", 11, "TO"))
    for col, x, klass in ((left, lx, "lm-l"), (right, rx, "lm-r")):
        for i, node in enumerate(col):
            y = top + i * (nh + vgap)
            pos[node.id] = (x, y)
            extra = f"{klass} {_ai(i)}" if klass == "lm-l" else klass
            parts.append(_node_group_open(node, extra))
            parts.append(_rect(x, y, nw, nh, 9))
            parts.append(_svg_text(x + 16, y + nh / 2 + 4, "tm", 12, node.label))
            parts.append("</g>")
    for e in graph.edges:
        if e.src not in pos or e.dst not in pos:
            continue
        sx, sy = pos[e.src]
        dx, dy = pos[e.dst]
        parts.append(_edge_path(f"M{sx + nw:g} {sy + nh / 2:g} H {dx:g}", fig_id, e.emphasis, cls="lm-k"))
    return "".join(parts), width, height


def _layout_panel(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """A responsive grid of labelled cards; cards stagger-fade in (a set, not a flow)."""
    n = len(graph.nodes)
    if n == 0:
        return _markers(fig_id), 940, 100
    width = 1000
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
        parts.append(_node_group_open(node, f"anim {_ai(i)}"))
        parts.append(_rect(x, y, cw, ch, 11))
        parts.append(_svg_text(x + 16, y + 28, "t", 12.5, node.label, weight=500))
        if node.caption:
            cap = node.caption if len(node.caption) <= 46 else node.caption[:45] + "…"
            parts.append(_svg_text(x + 16, y + 48, "tm", 10.5, cap))
        parts.append("</g>")
    return "".join(parts), width, height


def _layout_hub(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """A central core with radiating nodes: core pops, spokes draw out, nodes fade, ring sweeps.

    Convention: the FIRST node is the core; the rest radiate around it.
    """
    nodes = graph.nodes
    if not nodes:
        return _markers(fig_id), 1000, 300
    core, outer = nodes[0], nodes[1:]
    width, height = 1000, 420
    cx, cy, ring_r, core_r, spoke_r = 500, 210, 104, 78, 172
    nw, nh = 160, 44
    parts = [
        f'<defs><radialGradient id="{fig_id}-hub" cx="0.5" cy="0.5" r="0.5">'
        f'<stop offset="0" stop-color="{_DGOLDB}"/><stop offset="1" stop-color="{_DGOLD}"/>'
        f"</radialGradient></defs>"
    ]
    m = max(1, len(outer))
    placed: list[tuple[DiagramNode, float, float]] = []
    for i, node in enumerate(outer):
        ang = -math.pi / 2 + (2 * math.pi * i / m)
        x = round(cx + spoke_r * math.cos(ang), 2)
        y = round(cy + spoke_r * math.sin(ang), 2)
        placed.append((node, x, y))
    # spokes first (under the nodes)
    for _node, x, y in placed:
        parts.append(f'<line class="hub-spoke" x1="{cx}" y1="{cy}" x2="{x:g}" y2="{y:g}" stroke="{_DLINEDK}" stroke-width="1.5"/>')
    # radial satellites
    for node, x, y in placed:
        parts.append(_node_group_open(node, "hub-node"))
        parts.append(_rect(x - nw / 2, y - nh / 2, nw, nh, 6))
        parts.append(_svg_text(x, y + 5, "tm", 12, node.label, anchor="middle", fill=_DINK))
        parts.append("</g>")
    # ring + gradient core
    parts.append(f'<circle class="hub-ring" cx="{cx}" cy="{cy}" r="{ring_r}" fill="none" stroke="{_DBLUE}" stroke-width="2.5" stroke-dasharray="7 6"/>')
    parts.append(_node_group_open(core, "hub-core"))
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{core_r}" fill="url(#{fig_id}-hub)"/>')
    parts.append(_svg_text(cx, cy + 6, "t", 18, core.label, anchor="middle", font=_FDISP, weight=600, fill="#fffaf0"))
    parts.append("</g>")
    return "".join(parts), width, height


def _layout_stack(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """Layered architecture; layers build bottom-up (first node = top layer in reading order)."""
    nodes = graph.nodes
    n = len(nodes)
    if n == 0:
        return _markers(fig_id), 760, 120
    width = 1000
    lh, gap, top = 46, 12, 30
    height = top + n * (lh + gap)
    tints = ["#d9e2ea", "#dce8d6", "#f0dccb"]
    parts = [_markers(fig_id)]
    for i, node in enumerate(nodes):
        y = top + i * (lh + gap)
        delay = _ai(n - 1 - i)  # bottom layer animates first
        fill = tints[i % len(tints)]
        parts.append(_node_group_open(node, f"stack-layer {delay}"))
        parts.append(f'<rect x="80" y="{y:g}" width="840" height="{lh}" rx="8" fill="{fill}" stroke="{_DLINEDK}"/>')
        parts.append(_svg_text(width / 2, y + lh / 2 + 4, "tm", 12.5, node.label, anchor="middle"))
        parts.append("</g>")
    return "".join(parts), width, height


def _layout_timeline(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """An evolution timeline; line draws L→R and nodes light in chronological order (scrubbed)."""
    nodes = graph.nodes
    n = len(nodes)
    if n == 0:
        return _markers(fig_id), 1000, 160
    width, height = 1000, 200
    x0, x1, y = 80, 920, 110
    gap = (x1 - x0) / (n - 1) if n > 1 else 0
    parts = [
        f'<defs><linearGradient id="{fig_id}-tl" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{_DRED}"/><stop offset="0.6" stop-color="{_DGOLD}"/>'
        f'<stop offset="1" stop-color="{_DGREEN}"/></linearGradient></defs>'
    ]
    parts.append(f'<line class="tl-line" x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="url(#{fig_id}-tl)" stroke-width="5"/>')
    for i, node in enumerate(nodes):
        x = round(x0 + i * gap, 2)
        data_at = round(0.1 + 0.7 * (i / (n - 1)), 3) if n > 1 else 0.4
        attrs = [f'class="tl-node" data-at="{data_at:g}"']
        if node.caption:
            attrs.append(f'data-cap="{esc(node.caption)}"')
        if node.target:
            attrs.append(f'data-target="#{esc(node.target)}"')
        parts.append(f"<g {' '.join(attrs)}>")
        parts.append(f'<circle cx="{x:g}" cy="{y}" r="8" fill="{_DGOLD}"/>')
        parts.append(_svg_text(x, y - 18, "t", 12, node.label, anchor="middle", weight=500))
        if node.caption:
            cap = node.caption if len(node.caption) <= 28 else node.caption[:27] + "…"
            parts.append(_svg_text(x, y + 30, "tlab", 11, cap, anchor="middle"))
        parts.append("</g>")
    return "".join(parts), width, height


def _layout_sequence(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """A cross-tier request path (spec 006): participants as lifeline columns; ordered messages
    draw top→bottom in sequence (e.g. client → API → database)."""
    nodes = graph.nodes
    n = len(nodes)
    if n == 0:
        return _markers(fig_id), 1000, 120
    ids = {nd.id for nd in nodes}
    msgs = [e for e in graph.edges if e.src in ids and e.dst in ids and e.src != e.dst]
    width, margin_x, head_y, head_h, step = 1000, 60, 20, 42, 52
    colw = (width - 2 * margin_x) / max(1, n)
    colx = {nd.id: margin_x + i * colw + colw / 2 for i, nd in enumerate(nodes)}
    bottom = head_y + head_h + (len(msgs) + 1) * step
    height = bottom + 36
    parts = [_markers(fig_id)]
    for i, nd in enumerate(nodes):
        cx = colx[nd.id]
        parts.append(_node_group_open(nd, f"anim {_ai(i)}"))
        parts.append(_rect(cx - colw / 2 + 12, head_y, colw - 24, head_h, 10))
        parts.append(_svg_text(cx, head_y + head_h / 2 + 4, "tm", 12, nd.label, anchor="middle"))
        parts.append("</g>")
        parts.append(f'<line x1="{cx:g}" y1="{head_y + head_h:g}" x2="{cx:g}" y2="{bottom:g}" '
                     f'stroke="{_DLINE}" stroke-dasharray="4 5"/>')
    for j, e in enumerate(msgs):
        y = head_y + head_h + (j + 1) * step
        x1, x2 = colx[e.src], colx[e.dst]
        parts.append(f'<g class="anim {_ai(j)}">')
        parts.append(_svg_text(margin_x - 18, y + 3, "tlab", 9, str(j + 1)))
        parts.append(_edge_path(f"M{x1:g} {y:g} H {x2:g}", fig_id, e.emphasis))
        if e.label:
            parts.append(_svg_text((x1 + x2) / 2, y - 8, "tlab", 9, e.label, anchor="middle"))
        parts.append("</g>")
    return "".join(parts), width, height


def _layout_erd(graph: DiagramGraph, fig_id: str) -> tuple[str, int, int]:
    """A data model (spec 006): entities as boxes in a grid; relationships as labeled connectors.
    Entities fade in staggered; relations draw after."""
    nodes = graph.nodes
    n = len(nodes)
    if n == 0:
        return _markers(fig_id), 1000, 120
    width = 1000
    cols = min(n, 3)
    rows = math.ceil(n / cols)
    bw, bh, gx, gy, top = 230, 72, 70, 54, 30
    margin_x = (width - (cols * bw + (cols - 1) * gx)) / 2
    height = top + rows * bh + max(0, rows - 1) * gy + 36
    centre: dict[str, tuple[float, float]] = {}
    parts = [_markers(fig_id)]
    for i, nd in enumerate(nodes):
        r, c = divmod(i, cols)
        x = margin_x + c * (bw + gx)
        y = top + r * (bh + gy)
        centre[nd.id] = (x + bw / 2, y + bh / 2)
        parts.append(_node_group_open(nd, f"anim {_ai(i)}"))
        parts.append(_rect(x, y, bw, bh, 8))
        parts.append(_svg_text(x + bw / 2, y + 24, "tm", 12, nd.label, anchor="middle"))
        parts.append(f'<line x1="{x:g}" y1="{y + 34:g}" x2="{x + bw:g}" y2="{y + 34:g}" stroke="{_DLINE}"/>')
        if nd.caption:
            parts.append(_svg_text(x + bw / 2, y + 54, "tlab", 9, nd.caption[:30], anchor="middle"))
        parts.append("</g>")
    for j, e in enumerate(graph.edges):
        if e.src not in centre or e.dst not in centre:
            continue
        sx, sy = centre[e.src]
        dx, dy = centre[e.dst]
        parts.append(f'<g class="anim {_ai(j)}">')
        parts.append(_edge_path(f"M{sx:g} {sy:g} L {dx:g} {dy:g}", fig_id, e.emphasis))
        if e.label:
            parts.append(_svg_text((sx + dx) / 2, (sy + dy) / 2 - 6, "tlab", 9, e.label, anchor="middle"))
        parts.append("</g>")
    return "".join(parts), width, height


# Registry of hand-laid diagram layouts. Unknown layouts fall back to `flow`.
_LAYOUTS = {
    "pipeline": _layout_pipeline,
    "flow": _layout_flow,
    "ladder": _layout_ladder,
    "mapping": _layout_mapping,
    "panel": _layout_panel,
    "hub": _layout_hub,
    "stack": _layout_stack,
    "timeline": _layout_timeline,
    "sequence": _layout_sequence,
    "erd": _layout_erd,
}


def render_diagram(graph: DiagramGraph, fig_id: str) -> str:
    layout_fn = _LAYOUTS.get(graph.layout, _layout_flow)
    body, w, h = layout_fn(graph, fig_id)
    if graph.title:
        th = 50  # room for the Fraunces title; the body is shifted down beneath it
        title = (f'<text x="40" y="34" font-family="{_FDISP}" font-weight="600" '
                 f'font-size="19" fill="{_DINK}">{esc(graph.title)}</text>')
        body = title + f'<g transform="translate(0,{th})">{body}</g>'
        h += th
    aria = esc(graph.title or f"{graph.layout} diagram with {len(graph.nodes)} nodes")
    return f'<svg id="{fig_id}" viewBox="0 0 {w} {h}" role="img" aria-label="{aria}">{body}</svg>'


# ─────────────────────────────── block rendering ────────────────────────────

def _render_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    head, *body = rows
    th = "".join(f"<th>{esc(c)}</th>" for c in head)
    trs = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in body)
    return f'<div class="tbl-scroll"><table class="tbl"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'


def _ref_key(ref: SourceRef) -> tuple[str, str, str, str, str]:
    """Stable identity of a citation (including origin) — shared by appendix dedup + anchor."""
    return (ref.type.value, ref.origin or "", ref.name, ref.locator, ref.anchor or "")


def _ref_anchor(ref: SourceRef) -> str:
    """Deterministic, collision-safe HTML id for this citation's References-appendix entry."""
    h = hashlib.sha1("\x00".join(_ref_key(ref)).encode("utf-8")).hexdigest()[:10]
    return f"ref-{h}"


# Optional cross-repo resolver, injected per render() call by the portal (spec 002, Phase E):
# a SourceRef -> href|None callable. Held in a context var so chip rendering needs no signature
# threading and stays reentrancy-safe.
_RESOLVE: ContextVar = ContextVar("atlas_resolve", default=None)

# Optional human-title map injected by the melded portal (spec 006): locator -> SourceTitle
# ({title, artifact_kind, repo}). When present, per-section sources render as a human-titled TABLE
# instead of bare filename chips. Absent (e.g. the single-repo storybook), sources fall back to the
# chip line unchanged.
_TITLES: ContextVar = ContextVar("atlas_titles", default=None)


def _resolve_ref_href(ref: SourceRef) -> str:
    """Where a citation chip points. A portal may inject a resolver (Phase E) to drill a chip
    ACROSS pages (docs -> spec -> code); absent or unmatched, it falls back to the in-page
    References-appendix anchor for this exact source (Phase B). Deterministic either way."""
    resolve = _RESOLVE.get()
    if resolve is not None:
        href = resolve(ref)
        if href:
            return href
    return f"#{_ref_anchor(ref)}"


def _cite_chip(ref: SourceRef) -> str:
    title = ref.name + (f" · {ref.anchor}" if ref.anchor else "")
    href = _resolve_ref_href(ref) or "#refs"
    cat = _source_category(ref)
    return f'<a class="ref" href="{href}" title="{esc(title)}"><span class="cite-t {cat}">{cat}</span>{esc(ref.name)}</a>'


def _render_callout(block: Block) -> str:
    kind = block.callout_kind
    variant = CALLOUT_CLASS.get(kind, "")
    tag = block.callout_tag or CALLOUT_DEFAULT_TAG.get(kind, "Note")
    body = esc(block.prose) if block.prose else ""
    classes = "note" + ((" " + variant) if variant else "")
    return f'<div class="{classes}"><span class="tag">{esc(tag)}</span>{body}</div>'


def _render_coverage(rows: list) -> str:
    """Intent-vs-reality matrix as a design-system table: area, status pill, source chips."""
    out = ['<div class="tbl-scroll"><table class="tbl"><thead><tr><th>Area</th><th>Coverage</th><th>Sources</th></tr></thead><tbody>']
    for ci in rows:
        status = ci.status.value if hasattr(ci.status, "value") else str(ci.status)
        pill, label = COVERAGE_PILL.get(status, ("hard", esc(status)))
        chips = "".join(_cite_chip(r) for r in (list(ci.spec_refs) + list(ci.code_refs)))
        note = f'<div class="cov-note">{esc(ci.note)}</div>' if ci.note else ""
        out.append(
            f"<tr><td>{esc(ci.area)}{note}</td>"
            f'<td><span class="pill {pill}">{label}</span></td>'
            f'<td class="covsrc">{chips}</td></tr>'
        )
    out.append("</tbody></table></div>")
    return "".join(out)


def _render_block_core(block: Block, fig_counter: list[int]) -> str:
    if block.type is BlockType.PROSE:
        if block.prose_style == "lead":
            return f'<p class="lead">{esc(block.prose)}</p>'
        if block.prose_style == "pull":
            return f'<p class="pull">{esc(block.prose)}</p>'
        return f"<p>{esc(block.prose)}</p>"
    if block.type is BlockType.TABLE:
        return _render_table(block.table or [])
    if block.type is BlockType.CALLOUT:
        return _render_callout(block)
    if block.type is BlockType.DIAGRAM:
        fig_counter[0] += 1
        n = fig_counter[0]
        fig_id = f"fig{n}"
        layout = block.diagram.layout if block.diagram else "flow"
        svg = render_diagram(block.diagram, fig_id)
        return (
            f'<figure class="fig fig-{esc(layout)}">'
            f"{svg}"
            f'<figcaption id="cap-{fig_id}"><b>Fig. {n}</b> — hover a node to explain · click to jump.</figcaption>'
            "</figure>"
        )
    if block.type is BlockType.COVERAGE:
        return _render_coverage(block.coverage or [])
    return ""


def _block_refs(block: Block):
    """Every source ref a block surfaces: its own refs PLUS any carried by its diagram
    nodes or its coverage rows.

    Diagram nodes (schema §6) and coverage-row spec_refs/code_refs (§5.8) carry their own
    grounding source_refs; those must surface in the per-section sources line and the
    References appendix, not be silently dropped.
    """
    yield from block.source_refs
    if block.type is BlockType.DIAGRAM and block.diagram:
        for node in block.diagram.nodes:
            yield from node.source_refs
    if block.type is BlockType.COVERAGE and block.coverage:
        for ci in block.coverage:
            yield from ci.spec_refs
            yield from ci.code_refs


def _collect_section_refs(section: Section) -> list[SourceRef]:
    """De-duplicated union of every block's resolved source_refs (first-appearance order)."""
    seen: set[tuple[str, str, str, str, str]] = set()
    ordered: list[SourceRef] = []
    for block in section.blocks:
        for r in _block_refs(block):
            key = _ref_key(r)
            if key not in seen:
                seen.add(key)
                ordered.append(r)
    return ordered


def _source_line(refs: list[SourceRef]) -> str:
    chips = ['<span class="srclab">Sources</span>'] + [_cite_chip(r) for r in refs]
    return '<div class="srcline">' + "".join(chips) + "</div>"


def _source_table(refs: list[SourceRef]) -> str:
    """Human-titled sources TABLE (melded portal, spec 006). Falls back to the chip line when no
    title map is injected (the single-repo storybook), keeping that output unchanged."""
    titles = _TITLES.get()
    if not titles:
        return _source_line(refs)
    rows = ['<table class="tbl srctbl"><thead><tr><th>Source</th><th>Artifact</th><th>Repo</th><th></th></tr></thead><tbody>']
    for r in refs:
        st = titles.get(r.locator)
        title = st.title if st else r.name
        kind = (st.artifact_kind if st else r.type.value)
        repo = (st.repo if st else (r.origin or "—"))
        href = _resolve_ref_href(r) or "#refs"
        cat = _source_category(r)
        rows.append(
            f"<tr><td>{esc(title)}</td>"
            f'<td><span class="cite-t {cat}">{esc(kind)}</span></td>'
            f"<td>{esc(repo)}</td>"
            f'<td><a class="srcgo" href="{href}">view &rarr;</a></td></tr>'
        )
    rows.append("</tbody></table>")
    return '<div class="srctbl-wrap"><span class="srclab">Sources</span><div class="tbl-scroll">' + "".join(rows) + "</div></div>"


_TIER_LABELS = {"backend": "Backend", "frontend": "Frontend", "docs": "Docs"}


def _tier_label(tier: Optional[str]) -> str:
    if not tier:
        return "Technical detail"
    return _TIER_LABELS.get(tier.lower(), tier[:1].upper() + tier[1:])


_STATUS_LABEL = {"built": "Built", "partial": "Partial", "planned": "Planned"}


def _status_badge(status: Optional[str]) -> str:
    if not status:
        return ""
    label = _STATUS_LABEL.get(status, status)
    return f'<span class="bstatus bs-{esc(status)}">{esc(label)}</span>'


def _render_section(section: Section, fig_counter: list[int]) -> str:
    sclass = ({"planned": ' class="planned"', "partial": ' class="partial"'}
              .get(section.build_status or "", ""))  # built omits the class → byte-identical legacy output
    parts = [f'<section id="{esc(section.id)}"{sclass}>', '<span class="anchor"></span>']
    strap = f" — {esc(section.strap)}" if section.strap else ""
    parts.append(f'<span class="sec-num">{section.number:02d}{strap}</span>')
    parts.append(f"<h2>{esc(section.title)}{_status_badge(section.build_status)}</h2>")
    if section.subtitle:
        parts.append(f'<p class="lead">{esc(section.subtitle)}</p>')
    # functional (inline) vs technical (grouped by tier into per-tier disclosures)
    tier_groups: list[tuple[Optional[str], list[Block]]] = []
    tier_index: dict[Optional[str], int] = {}
    for block in section.blocks:
        if block.altitude is Altitude.TECHNICAL:
            key = block.tier
            if key not in tier_index:
                tier_index[key] = len(tier_groups)
                tier_groups.append((key, []))
            tier_groups[tier_index[key]][1].append(block)
        else:
            parts.append(_render_block_core(block, fig_counter))
    for i, (tier, blocks) in enumerate(tier_groups):
        # a tier's grade: the strongest 'planned' signal among its blocks, else None
        statuses = {b.build_status for b in blocks if b.build_status}
        grade = ("planned" if "planned" in statuses else
                 "partial" if "partial" in statuses else
                 "built" if "built" in statuses else None)
        faded = " planned" if grade == "planned" else ""
        slug = re.sub(r"[^a-z0-9]+", "-", (tier or "tech").lower()).strip("-")
        # legacy single-repo output (tier=None, no grade) stays byte-identical: class is exactly "mod".
        mod_class = "mod" + (" tier-mod" if tier else "") + faded
        parts.append(f'<details class="{mod_class}" id="{esc(section.id)}-{esc(slug)}">')
        parts.append(f'<summary><span class="mt">{esc(_tier_label(tier))}</span>'
                     f'{_status_badge(grade)}<span class="mx">+</span></summary>')
        parts.append('<div class="body">')
        for block in blocks:
            parts.append(_render_block_core(block, fig_counter))
        parts.append("</div></details>")
    refs = _collect_section_refs(section)
    if refs:
        parts.append(_source_table(refs))
    parts.append("</section>")
    return "".join(parts)


# ──────────────────────────────── page shell ────────────────────────────────

def _title_html(title: str, accent: Optional[str]) -> str:
    if accent and accent in title:
        i = title.index(accent)
        return esc(title[:i]) + f"<em>{esc(accent)}</em>" + esc(title[i + len(accent):])
    return esc(title)


def _all_refs(doc: DocumentModel) -> list[SourceRef]:
    seen: set[tuple[str, str, str, str, str]] = set()
    ordered: list[SourceRef] = []
    for s in doc.sections:
        for b in s.blocks:
            for r in _block_refs(b):
                key = _ref_key(r)
                if key not in seen:
                    seen.add(key)
                    ordered.append(r)
    return ordered


def _section_tiers(section: Section) -> list[Optional[str]]:
    """The distinct technical tiers in a section, first-appearance order (for the nested nav)."""
    seen: list[Optional[str]] = []
    for b in section.blocks:
        if b.altitude is Altitude.TECHNICAL and b.tier not in seen:
            seen.append(b.tier)
    return seen


def _render_nav(sections: list[Section], project: str, catalog_href: Optional[str] = None) -> str:
    # nested: each capability links to its section + its tier disclosures (spec 006)
    chunks: list[str] = []
    for s in sections:
        chunks.append(f'<a href="#{esc(s.id)}">{esc(s.title)}</a>')
        for tier in _section_tiers(s):
            if tier is None:
                continue   # single-repo storybook keeps a flat nav (no generic 'Technical detail' sub-link)
            slug = re.sub(r"[^a-z0-9]+", "-", tier.lower()).strip("-")
            chunks.append(f'<a class="toc-tier" href="#{esc(s.id)}-{esc(slug)}">{esc(_tier_label(tier))}</a>')
    if catalog_href:
        chunks.append(f'<a class="toc-catalog" href="{esc(catalog_href)}">Source index &rarr;</a>')
    links = "".join(chunks)
    cur = esc(sections[0].title) if sections else "Contents"
    return (
        '<nav class="toc" id="toc"><div class="wrap">'
        f'<a href="#" class="brand-mark" aria-label="{esc(project)}">{GLYPH}<span class="brand-word">{esc(project)}</span></a>'
        '<button class="navbtn" id="navbtn" aria-expanded="false" aria-controls="toclinks">'
        '<span class="bars"><span></span><span></span><span></span></span>'
        f'<span class="lbl">Contents · <span class="cur" id="navcur">{cur}</span></span></button>'
        f'<div class="links" id="toclinks">{links}</div>'
        "</div></nav>"
    )


def _render_footer(doc: DocumentModel, project: str) -> str:
    refs = _all_refs(doc)
    refitems = "".join(
        f'<p id="{_ref_anchor(r)}"><span class="reftype {_source_category(r)}">{_source_category(r)}</span>'
        f'{esc(r.name)}{(" · " + esc(r.anchor)) if r.anchor else ""}</p>'
        for r in refs
    )
    types = sorted({SOURCE_T.get(r.type, "doc") for r in refs})
    sources = " · ".join(SOURCE_LABEL.get(t, t) for t in types) if types else "—"
    colophon = (
        '<table class="colophon"><tbody>'
        f"<tr><th>Document</th><td>Architecture Storybook — {esc(project)}</td></tr>"
        '<tr><th>Build</th><td><span class="vtag">deterministic</span></td></tr>'
        f"<tr><th>Sources</th><td>{sources}</td></tr>"
        "<tr><th>Gate</th><td>fail-closed · 6 checks</td></tr>"
        "</tbody></table>"
    )
    return (
        '<div class="wrap"><footer id="refs"><span class="anchor"></span>'
        '<span class="sec-num">Appendix</span><h3>References &amp; build</h3>'
        '<p style="font-size:.86rem;max-width:74ch">Every source consulted, resolved to its '
        "locator — the resolved form of the model's source references, the same data the "
        "fail-closed gate checks.</p>"
        f'<div class="reflist">{refitems}</div>'
        f"{colophon}"
        '<div class="genline"><span class="gm">●</span> Generated by '
        f'<a href="{REPO_URL}" target="_blank" rel="noopener noreferrer">spec-kit-atlas</a> — '
        "a faithful atlas of many sources into one architecture narrative. Organised by "
        "architecture, not authoring history. Every claim is traceable to its source.</div>"
        "</footer></div>"
    )


JS = r"""(function(){
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var nav=document.getElementById('toc'), btn=document.getElementById('navbtn'),
      links=document.getElementById('toclinks'), curEl=document.getElementById('navcur');
  var anchors = links ? Array.prototype.slice.call(links.querySelectorAll('a')) : [];

  function setOpen(open){ if(!nav)return; nav.classList.toggle('open',open); if(btn) btn.setAttribute('aria-expanded',open?'true':'false'); }
  if(btn) btn.addEventListener('click', function(){ setOpen(!nav.classList.contains('open')); });
  anchors.forEach(function(a){ a.addEventListener('click', function(){ if(curEl) curEl.textContent=a.textContent; setOpen(false); }); });
  document.addEventListener('click', function(e){ if(nav && nav.classList.contains('open') && !nav.contains(e.target)) setOpen(false); });
  document.addEventListener('keydown', function(e){ if(e.key==='Escape') setOpen(false); });

  /* scrollspy */
  var targets = anchors.map(function(a){ return document.getElementById(a.getAttribute('href').slice(1)); }).filter(Boolean);
  function setActive(a){ if(!a||a.classList.contains('active'))return; anchors.forEach(function(x){x.classList.remove('active');}); a.classList.add('active'); if(curEl) curEl.textContent=a.textContent;
    if(links && links.scrollWidth>links.clientWidth){ var lr=links.getBoundingClientRect(),ar=a.getBoundingClientRect(); if(ar.left<lr.left||ar.right>lr.right){ links.scrollLeft += (ar.left-lr.left)-(lr.width-ar.width)/2; } } }
  function recompute(){ var line=100,best=null,bd=Infinity; targets.forEach(function(t){ var top=t.getBoundingClientRect().top,d=line-top; if(d>=0&&d<bd){bd=d;best=t.id;} }); if(!best&&targets[0])best=targets[0].id; var a=anchors.find(function(x){return x.getAttribute('href')==='#'+best;}); setActive(a); }
  if(targets.length){ var tick=false; window.addEventListener('scroll',function(){ if(!tick){tick=true;requestAnimationFrame(function(){recompute();tick=false;});} },{passive:true}); window.addEventListener('resize',recompute,{passive:true}); recompute(); }

  /* open a targeted disclosure on hash */
  function openHash(){ if(location.hash){ var t; try{t=document.querySelector(location.hash);}catch(e){return;} if(t&&t.tagName&&t.tagName.toLowerCase()==='details') t.setAttribute('open',''); } }
  window.addEventListener('hashchange', openHash); openHash();

  /* e/c expand-collapse all disclosures */
  document.addEventListener('keydown', function(e){ if(e.target&&(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA'))return;
    if(e.key==='e') document.querySelectorAll('details.mod').forEach(function(d){d.setAttribute('open','');});
    if(e.key==='c') document.querySelectorAll('details.mod').forEach(function(d){d.removeAttribute('open');}); });

  /* diagrams: hover-to-explain + click-to-jump */
  document.querySelectorAll('figure svg').forEach(function(svg){
    var cap = svg.parentNode.querySelector('figcaption'); var base = cap ? cap.innerHTML : '';
    svg.querySelectorAll('[data-cap]').forEach(function(n){
      n.addEventListener('mouseenter', function(){ if(cap) cap.textContent=n.getAttribute('data-cap'); });
      n.addEventListener('mouseleave', function(){ if(cap) cap.innerHTML=base; });
    });
    svg.querySelectorAll('[data-target]').forEach(function(n){
      n.addEventListener('click', function(e){ e.stopPropagation(); var t; try{t=document.querySelector(n.getAttribute('data-target'));}catch(err){return;} if(t) t.scrollIntoView({behavior:reduce?'auto':'smooth'}); });
    });
  });

  /* figure reveal + timeline scrub + brand motion */
  var figs = Array.prototype.slice.call(document.querySelectorAll('figure'));
  if(reduce || !('IntersectionObserver' in window)){
    figs.forEach(function(f){ f.classList.add('in'); });
    var nm0=document.querySelector('.brand-mark'); if(nm0) nm0.classList.add('show');
  } else {
    var io=new IntersectionObserver(function(es){ es.forEach(function(en){ if(en.isIntersecting){ en.target.classList.add('in'); io.unobserve(en.target); } }); }, {rootMargin:'0px 0px -10% 0px',threshold:0.15});
    figs.forEach(function(f){ io.observe(f); });
    requestAnimationFrame(function(){ figs.forEach(function(f){ if(f.getBoundingClientRect().top<window.innerHeight*0.9) f.classList.add('in'); }); });

    var scrubbed = Array.prototype.slice.call(document.querySelectorAll('.fig-timeline'));
    scrubbed.forEach(function(f){ f.classList.add('scrubbed'); });
    function scrub(){ var vh=window.innerHeight; scrubbed.forEach(function(f){ var r=f.getBoundingClientRect(); var p=(vh*0.85 - r.top)/(vh*0.35); p=Math.max(0,Math.min(1,p)); f.style.setProperty('--p',p.toFixed(3)); f.querySelectorAll('[data-at]').forEach(function(el){ el.classList.toggle('lit', p>=parseFloat(el.getAttribute('data-at'))); }); }); }
    if(scrubbed.length){ var st=false; window.addEventListener('scroll',function(){ if(!st){st=true;requestAnimationFrame(function(){scrub();st=false;});} },{passive:true}); window.addEventListener('resize',scrub,{passive:true}); scrub(); }

    var stars=Array.prototype.slice.call(document.querySelectorAll('.spin-star'));
    if(stars.length){ var lastY=window.pageYOffset||0,ang=0,sp=false; function spin(){ var y=window.pageYOffset||0; ang+=(y-lastY)*0.18; lastY=y; var v=ang.toFixed(1)+'deg'; stars.forEach(function(s){ s.style.setProperty('--spin',v); }); sp=false; } window.addEventListener('scroll',function(){ if(!sp){sp=true;requestAnimationFrame(spin);} },{passive:true}); }

    var mast=document.querySelector('.brand-logo'), navMark=document.querySelector('.brand-mark');
    if(mast && navMark){ var io2=new IntersectionObserver(function(es){ es.forEach(function(en){ navMark.classList.toggle('show', !en.isIntersecting); }); }, {threshold:0}); io2.observe(mast); }
  }
})();"""


def render(doc: DocumentModel, theme: dict[str, str], resolve=None, titles=None, catalog_href=None) -> str:
    """Pure: DocumentModel + theme tokens → a complete HTML document string.

    `resolve` (optional, portal Phase E): a SourceRef -> href|None callable to drill a citation
    chip ACROSS pages; absent or unmatched, chips resolve to the in-page References appendix.
    `titles` (optional, melded portal spec 006): a locator -> SourceTitle map; when present, per-section
    sources render as a human-titled table.
    `catalog_href` (optional, spec 006): href of the hierarchical source index, linked from the nav.
    Deterministic for fixed inputs."""
    token = _RESOLVE.set(resolve)
    ttoken = _TITLES.set(titles)
    try:
        return _render_doc(doc, theme, catalog_href=catalog_href)
    finally:
        _RESOLVE.reset(token)
        _TITLES.reset(ttoken)


def _render_doc(doc: DocumentModel, theme: dict[str, str], catalog_href=None) -> str:
    merged = {**DEFAULT_THEME, **theme}
    css = build_css(merged)
    project = doc.project_name or doc.title
    fig_counter = [0]
    sections_html = '<hr class="divider">'.join(_render_section(s, fig_counter) for s in doc.sections)

    kicker = doc.kicker if doc.kicker else ["Architecture Storybook"]
    kicker_html = "".join(f"<span>{esc(k)}</span>" for k in kicker[:2])
    dek = f'<p class="dek">{esc(doc.lede)}</p>' if doc.lede else ""
    meta_html = ""
    if doc.meta:
        meta_html = '<div class="meta-row">' + "".join(
            f"<span><b>{esc(m.label)}</b> {esc(m.value)}</span>" for m in doc.meta
        ) + "</div>"

    masthead = (
        '<div class="wrap"><header class="mast">'
        f'<a href="#" class="brand-logo" aria-label="{esc(project)}">{GLYPH}<span class="brand-word">{esc(project)}</span></a>'
        f'<div class="kicker">{kicker_html}</div>'
        f'<h1 class="title">{_title_html(doc.title, doc.title_accent)}</h1>'
        f"{dek}{meta_html}"
        "</header></div>"
    )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light only">\n'
        '<meta name="theme-color" content="#f4f0e6">\n'
        f"<title>{esc(doc.title)}</title>\n"
        f"<style>{css}</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="grain"></div>\n'
        f"{masthead}\n"
        f"{_render_nav(doc.sections, project, catalog_href)}\n"
        '<div class="wrap">\n'
        f"{sections_html}\n"
        "</div>\n"
        f"{_render_footer(doc, project)}\n"
        f"<script>{JS}</script>\n"
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
