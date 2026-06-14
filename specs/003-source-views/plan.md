# Implementation Plan: Source views (drill-to-source)

**Spec**: `spec.md` (003-source-views) · **Constitution**: faithfulness (I), generated-never-authored (V)

## Summary

A new deterministic renderer turns the `FragmentCorpus` into one beautified HTML page per
source file (`sources/<file>.html`), and the existing chip `resolve` seam is pointed at those
pages so citations drill to the exact section. Reasoning, IR contracts, and `verify.py` are
untouched — this is purely an additive read surface (DESIGN §1.7 Layer-2).

## Technical context

- **Source of truth = the corpus.** Each `Fragment` carries `.text` (the section's raw
  markdown) and `.id` (locator `file#section`). Reconstruct a file by grouping its fragments
  (by the locator's pre-`#` path), in first-appearance order.
- **Rendering = client-side, CDN.** Python stays pydantic-only: each source page embeds the
  reconstructed markdown and renders it in-browser with **markdown-it** + **Mermaid** (CDN),
  styled to the design system. Consistent with the accepted CDN-fonts decision; no new Python
  dependency, no server-side markdown engine.
- **Anchors.** Each section heading gets `id="<section-anchor>"` derived from the locator's
  `#part`, so `file#section` deep-links resolve.

## Components

1. **`skill/scripts/render_sources.py`** (new, pure/deterministic, stdlib only):
   - `render_source_pages(corpus, *, origin_prefix="") -> dict[str, str]` → `{ "sources/<safe>.html": html }`.
   - `build_source_resolver(corpus, *, base="") -> Callable[[SourceRef], str|None]` → maps a
     ref's locator to `sources/<safe(file)>.html#<section-anchor>` when that file/section was
     emitted, else `None`.
   - Reuse `render.build_css` + `GLYPH` for the shell; embed markdown in a `data-*`/`<script type="text/markdown">`
     block; include the CDN markdown-it + Mermaid bootstrap. Inline-literal styling so it reads in any viewer.
2. **`skill/scripts/render.py`** — no API change needed: it already exposes `render(doc, theme, resolve=...)`
   via the `_RESOLVE` ContextVar. Source-view wiring rides that seam.
3. **`skill/scripts/synthesize.py`** (single-repo finish): after verify passes, build source pages
   from the corpus, write them under `<out_dir>/sources/`, and call `render(doc, theme, resolve=source_resolver)`.
4. **`skill/scripts/synthesize_atlas.py`** (portal finish): per member, build `sources/<origin>/…`
   from that member's corpus; **compose** resolvers — the existing cross-repo `resolve` first,
   falling back to the per-member source resolver.

## Faithfulness & invariants

- Read surface only; `verify.py`/`verify_links.py` unchanged. Source pages are regenerated each
  run, never hand-edited (V). They strengthen I: the cited source is now readable, not just named.
- Deterministic: pure functions of the corpus; no clock/rng (DESIGN §6). Markdown is escaped
  before embedding; the CDN renderer is the only dynamic part and degrades to readable raw text
  if scripting is off.

## Phases

1. `render_sources.py` + unit tests (pages emitted per file, anchors present, resolver maps
   locators, determinism, no content lost).
2. Wire `synthesize.py`; regenerate the e2e fixture storybook; eyeball drill-down.
3. Wire `synthesize_atlas.py` (portal) + compose resolvers; dogfood on a real multi-repo
   workspace (a docs portal — its ADRs + specs become reachable).
4. Docs: SKILL.md + README note the source-view layer; `examples/` refreshed.

## Out of scope

Server-side markdown, source editing, governance conformance (parked), changes to the engine.
