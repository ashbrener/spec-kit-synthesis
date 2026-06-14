# Feature Specification: Renderer v2 — Editorial Design System

**Feature Branch**: `001-renderer-v2`

**Created**: 2026-06-03

**Status**: Draft

**Input**: User direction: "We can't modify our html template to be like this one. We need
to modify our model to fit into the framework of the design system. This being the default
one, barring the bespoke branding." Plus: "SVG diagrams are important … all animations need
to be appropriate for the diagram, not 1 size fits all." Design context: `DESIGN.md` §6/§11,
the scrubbed visual contract at `skill/templates/storybook.html`, and the plan at
`specs/001-renderer-v2/plan.md`.

## Overview

The generated storybook is faithful but visually flat ("clean, not great"). This feature
adopts a proven editorial design system — warm paper palette, Fraunces / Newsreader / Spline
Sans Mono, inset-shadow cards, per-section disclosure, scroll-revealed SVG — as the **single
default output of the deterministic renderer**.

The governing principle is an inversion of the usual approach: the design system is the **fixed
contract**, and the `DocumentModel` is extended to **populate its slots**. We do not reshape the
template toward our model; we reshape the model to fit the template. The faithful, fully scrubbed
reference (no third-party branding, no client content) lives at `skill/templates/storybook.html`
and is the visual source of truth.

This is a **render + presentation** change only. The faithfulness engine — adapters, reconcile,
and the fail-closed `verify.py` gate — is unchanged: `verify.py` validates the IR (model/corpus)
and never reads HTML, so the renderer may be rewritten freely. Provenance, coverage, evolution,
and the "no source numbers in the narrative" invariant are all preserved; citations simply move
to a more elegant home (inline reference anchors + a References appendix).

## Clarifications

### Session 2026-06-03

- **Delivery technology** — The output remains a **deterministic, pure-function, single
  self-contained HTML file**. It is NOT a React SPA. Rationale: the artifact is a compiled
  *document*, not an app; single-file portability, byte-determinism (diffable, gate-auditable),
  and a one-toolchain (`uv`) skill are first-class properties an SPA would damage. (DESIGN §11.)
- **Disclosure model** — **Per-section disclosure.** Technical detail opens inline per section;
  functional prose is always visible; sources move to a References appendix + per-section
  citation line. The **global Overview/Technical/Sources depth toggle is removed** — it implied
  three mutually-exclusive views when the depths are cumulative.
- **Colour theme** — **Light only.** The design system intentionally pins one warm light
  palette. The dark-mode variant and theme toggle are removed. Theme tokens remain a retint
  layer.
- **Fonts** — Delivered via CDN `@import` (smallest file; system-serif fallback offline). Output
  stays one small HTML file.
- **Diagram motion** — Animation is a property of each diagram's **meaning**, keyed off the
  diagram `layout`. There is no global animation knob. Motion must reveal the diagram's logic
  (sequence / direction / radiation / stacking / flow).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — An executive reads the whole system at a glance (Priority: P1)

A non-engineer opens the storybook and reads top to bottom: a masthead with the project name,
a one-line deck, and section-by-section plain-English narrative with diagrams. They never need
to toggle a control to understand the system; technical depth is tucked into per-section
disclosures they can ignore.

**Acceptance**:
1. The masthead renders project name (brand wordmark), kicker, title (with optional accent),
   deck, and a metadata row — all from the model.
2. Functional-altitude prose, callouts, tables, and diagrams render inline and read coherently
   on their own (Layer 0 stands alone).
3. No spec numbers, FR codes, or filenames appear anywhere in the narrative body.

### User Story 2 — An engineer drills into detail in place (Priority: P1)

A developer reading a section expands its "Technical detail" disclosure to see engineering
specifics, and follows per-section citation chips to the References appendix to see exactly which
sources back the section. They can deep-link to a section or open a specific disclosure via URL
hash.

**Acceptance**:
1. Technical-altitude blocks render inside a per-section disclosure (`<details>`), collapsed by
   default; keyboard `e`/`c` expand/collapse all; a hash targeting a disclosure opens it.
2. Every section shows a quiet sources line of source-typed citation chips; a doc-wide References
   appendix lists every resolved source, grouped by type.
3. Scrollspy highlights the current section in the sticky table of contents.

### User Story 3 — Diagrams convey their logic through motion (Priority: P2)

A reader watches each diagram reveal in a way that matches what it depicts — a pipeline fills
left-to-right, a hub radiates from its core, a stack builds bottom-up, a timeline lights in
chronological order — making the structure easier to grasp.

**Acceptance**:
1. Each of the eight layouts (pipeline, flow, ladder, mapping, panel, hub, stack, timeline) has
   a distinct, semantically-appropriate entrance animation.
2. Every animation settles to a correct static final state (print/PDF/screenshot safe) and is
   fully disabled under `prefers-reduced-motion`.
3. Scroll-scrubbed motion (timeline) tracks reading progress and never scroll-jacks.

### User Story 4 — The output is portable and reproducible (Priority: P1)

An operator commits the generated `architecture.html` into a target repo as documentation. It
opens with `file://` or any static host, with no build step or dependencies, and re-running the
generator on unchanged inputs yields a byte-identical file.

**Acceptance**:
1. Output is a single self-contained HTML file (CSS + JS inlined; fonts via CDN).
2. `render(model)` is byte-deterministic — no clock, no randomness; the colophon carries no
   timestamp.

### Edge Cases

- A model with no `meta`/`kicker`/`strap`/`title_accent` still renders cleanly (graceful
  fallbacks; `project_name` falls back to `title`).
- An unknown diagram `layout` falls back to `flow` (existing rule) without crashing.
- A section with only functional blocks shows no empty disclosure.
- Reduced-motion and print produce a fully-drawn, static document.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** The renderer MUST emit the design-system structure of `skill/templates/storybook.html`
  (masthead, sticky TOC, sections with dividers, References appendix, colophon), populated from
  the `DocumentModel`.
- **FR-002** The renderer MUST be a pure function producing one self-contained HTML file, with no
  network calls at render time (fonts referenced via CDN are loaded by the browser, not the
  renderer) and byte-identical output for identical input.
- **FR-003** The narrative body MUST contain no source identifiers; citations appear only as
  source-typed chips and in the References appendix.
- **FR-004** Reading depth MUST be per-section (inline functional + collapsible technical). The
  global depth control and dark-mode toggle MUST be removed.
- **FR-005** The `DocumentModel` MUST carry: `project_name`, `title_accent`, `kicker`, `meta`
  (masthead); `Section.strap` (section eyebrow); `Block.prose_style` (`lead`/`pull`). All new
  fields are optional with graceful fallbacks.
- **FR-006** Diagrams MUST support eight layouts, each restyled to the design system and each with
  its own semantically-appropriate, reduced-motion/print-safe animation.
- **FR-007** Callout kinds MUST map to design-system note variants (decision→affirmative,
  unspecified→warning, evolution→neutral); coverage MUST render as a status-pilled table.
- **FR-008** The footer MUST credit `spec-kit-synthesis` with a hyperlink to its repository
  (fixed chrome), and present a model-derived colophon (project, sources, gate) with no timestamp.
- **FR-009** The verify gate, adapters, and reconcile phase MUST be unaffected by this change.

### Key Entities

- **DocumentModel** (extended) — adds `project_name`, `title_accent`, `kicker: list[str]`,
  `meta: list[MetaPair]`; retains `title`, `lede` (rendered as the deck), `sections`.
- **MetaPair** (new) — `{ label, value }` for the masthead metadata row.
- **Section** (extended) — adds `strap` (sec-num eyebrow); `subtitle` renders as the lead line.
- **Block** (extended) — adds `prose_style ∈ {lead, pull}` (PROSE only).
- **DiagramGraph** (extended) — `layout` Literal grows to eight values (adds `hub`, `stack`,
  `timeline`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** A storybook generated by renderer v2 is visually consistent with
  `skill/templates/storybook.html` (eyeball parity on masthead, type, callouts, cards, diagrams).
- **SC-002** `uv run pytest skill/tests -q` is green on Python 3.11 and 3.12, with `test_render.py`
  and `test_render_coverage.py` rewritten to assert the new structure.
- **SC-003** Re-rendering identical input yields byte-identical output (determinism test passes).
- **SC-004** A regenerated real storybook (e.g. project-arc or speckit-linear inputs) still passes
  a cross-model faithfulness review at 0/0/0 (engine unchanged).
- **SC-005** All eight diagram layouts render distinctly and animate appropriately; reduced-motion
  and print produce a complete static document.

## Assumptions

- The visual contract is `skill/templates/storybook.html`; `render.py`'s CSS mirrors it and the
  two are kept in sync by hand.
- Self-hosted/inline fonts, dark mode, push-button reconcile, and the Phase-4 OSS engine are out
  of scope for this feature.
- This is the repository's first `specs/` folder; authoring it also seeds the eventual product
  dogfood (synthesising spec-kit-synthesis's own storybook from its specs + design + code).
