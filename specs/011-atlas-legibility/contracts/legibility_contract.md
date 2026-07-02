# Contract: Atlas legibility render guarantees

Presentation-only additions to the renderer-v2 contract. Output stays a single deterministic self-contained HTML file.

## Build status (US1)
- A `planned` section emits a `planned` class; a `partial` section emits a `partial` class; a `built` section emits neither. All three additionally emit the existing `.bstatus` text badge.
- The CSS distinguishes the three pre-attentively (planned: opacity + muted heading + faint dashed left rule; partial: intermediate; built: full weight).
- Fade is CSS only: a planned section's blocks, chips, tables, and callouts are all still present and resolvable (no content removed/hidden/truncated).
- `@media print` and reduced-motion render the content legibly (no permanent dimming that hides text).

## Source-type taxonomy (US2)
- Every citation chip emits `cat-<category>` for `category ∈ {spec, plan, adr, research, code, narrative, source}` plus its visible label/name text.
- Every drilled source-page header emits a category band with `cat-<category>`, an explicit type label, and a thin left rule.
- Category is derived deterministically — from `kind` (pages) or `SourceType`+locator (chips) — and is **total**: an unrecognised source yields `cat-source` + a generic label, never a blank/missing accent.
- Chips and the source page they link to resolve to the same category.

## Cross-cutting
- **Colour never the sole signal:** every status and every category is also conveyed by text (badge/label) and weight/position — information survives grayscale, print, and colour-blindness; body text meets WCAG AA.
- **One design system:** a single shared palette/type system; no `data-theme`, no dark-mode tokens, no per-page stylesheet.
- **Determinism:** identical model + theme → byte-identical HTML.
- **Template parity:** `skill/templates/storybook.html` carries the same status/category CSS as `render.py` emits.

## Negative guarantees (must NOT happen)
- No content removed or hidden by a fade.
- No category/status conveyed by colour alone.
- No second visual system / dark mode / per-page theme introduced.
- No change to `verify.py` / `verify_links.py` / clustering / IR rules.
