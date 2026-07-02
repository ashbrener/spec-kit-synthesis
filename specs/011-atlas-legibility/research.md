# Phase 0 Research: Atlas Legibility

## Current state (what already exists)

- `Section.build_status` and `Block.build_status` carry `built|partial|planned` (spec 006). `render._render_section` adds `class="planned"` only for planned; CSS today: `.planned{opacity:.62}`, `section.planned>h2{opacity:.8}`, and a dashed left rule on a planned tier's `.body`. **No `partial` treatment exists**, and the planned signal is weak (opacity only).
- Citation chips (`_cite_chip`) render `<span class="cite-t {t}">` where `t ∈ {spec, code, doc, adr}` from `SOURCE_T[SourceType]` — only **4** categories, colour + text token already paired.
- Source pages (`render_sources._page_html`) already have the fragment `kind` and a kicker `Source · <kind>` + an `h1` filename — but no category accent/band.
- The References appendix uses `.reftype.{spec,code,doc}`.

## Decision 1 — strengthen planned + add partial (US1)

**Decision:** emit a status class on every section (`planned`/`partial`; built = no class), and strengthen the CSS so the three separate pre-attentively: planned = reduced opacity **+ desaturated/muted heading colour + a faint dashed left rule down the section**; partial = an intermediate, lighter treatment (subtle solid left rule + slightly muted heading); built = full weight. Block-level planned fading stays.

**Rationale:** the dogfood showed opacity-only is too subtle. Adding a left-margin rule + heading mute gives a second and third channel (position + colour + weight), so the distinction survives a fast scan and grayscale/print (FR-008). The badge label is retained — colour/fade is never the sole signal (FR-003).

**Alternatives:** badge-only (status quo — the defect); background tints (rejected — fights the prose, breaks the one-register ethos).

## Decision 2 — 6-category source taxonomy (US2)

**Decision:** a deterministic `category(ref|kind) → {spec, plan, adr, research, code, narrative, source(default)}`:
- **source pages** derive from the fragment `kind` (reliable): spec/tasks/data-model/contract→`spec`, plan→`plan`, research→`research`, adr→`adr`, code/code-symbol→`code`, design-doc→`narrative`, else→`source`.
- **chips** derive from `SourceType` + the locator filename (chips carry no kind): ADR→`adr`, CODE→`code`, DESIGN_DOC→`narrative`, SPEC→ (`plan` if locator ends `plan.md`, `research` if `research.md`, else `spec`), else→`source`.

Both map to the same CSS vocabulary, so chips and the page they drill to agree. Accents are added to chips (replacing the 4-token class), the source-page header (band + label + left rule), and the appendix reftype.

**Rationale:** matches the requested six categories without a schema change (additive, derived). The dual derivation (kind for pages, type+locator for chips) is deterministic and converges. A neutral default guarantees no blank/broken accent (FR-004, SC-003).

**Alternatives:** add a `category` field to `SourceRef`/fragment (more plumbing; deferred — derivation suffices); colour by the 4 `SourceType`s only (rejected — drops plan/research the user asked for).

## Decision 3 — accent palette

**Decision:** extend `DEFAULT_THEME` with low-saturation accents reusing the existing family where natural and adding two muted hues for the new categories, all tuned to sit in the warm paper register:
- spec → gold, code → green, adr → red, narrative → blue (existing), plan → muted teal, research → muted plum, default → `line-dk` neutral.
Applied as a thin left rule + small label tint + chip background — never a full content background.

**Rationale:** reuses the established tokens so the portal stays one cohesive system (FR-007); two new muted hues are enough to disambiguate the six. Exact hex values are tuned in implementation against the north-star (visual-quality call, not an abstract fork).

## Decision 4 — nav scaling (US3)

**Decision:** CSS-only — the sticky `nav.toc` link row wraps / scrolls within a bounded height and stays usable as links grow; no structural/JS change that would threaten the single-file deterministic output.

**Rationale:** lowest priority; a contained, deterministic CSS treatment satisfies "usable at ≥20 capabilities" (SC-006) without a second nav system.

## Determinism / accessibility

All derivations are pure functions of the model (no clock/rng); identical inputs → identical bytes (SC-004). Every status and category is carried by an explicit text label + weight/position, so information survives grayscale/print/colour-blindness (FR-008, SC-005). `@media print` and reduced-motion keep the signals legible (existing guards extended).
