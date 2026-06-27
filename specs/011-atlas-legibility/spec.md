# Feature Specification: Atlas Legibility — Build-Status Emphasis + Source-Type Color Taxonomy

**Feature Branch**: `011-atlas-legibility`

**Created**: 2026-06-27

**Status**: Draft

**Input**: User description: "Make build STATUS and source TYPE legible at a glance — accent and de-emphasis as information, not decoration — entirely within the one editorial design system. Planned sections pre-attentively faded; a consistent accent + label per source type on chips and drilled source pages; nav that scales. Render/presentation only; faithfulness untouched."

## Context

The rendered Atlas portal is faithful and polished, but driving it in a browser (post-render dogfood) surfaced three legibility gaps. They are presentation-only — the faithfulness engine (verify gates, clustering, the IR rules) is untouched. This feature improves how the existing single editorial design system *communicates*, without adding a second visual system, dark mode, or per-page re-skins.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tell built from planned at a glance (Priority: P1)

A reader scrolling the portal can immediately see which capabilities are **built** vs **planned** vs **partial** without reading a status badge — planned work is pre-attentively de-emphasised so the eye separates "what exists" from "what's intended."

**Why this priority**: The portal's core promise is an honest built-vs-planned picture; today only a small badge carries that signal, so a fast scan misreads aspirational work as shipped.

**Independent Test**: Render a document with built, partial, and planned sections; confirm planned sections are visibly de-emphasised (reduced emphasis on heading + body + a left-margin treatment) relative to built, partial sits between, and the difference is apparent without reading the badge — while the planned content remains fully readable and still drills to its source.

**Acceptance Scenarios**:

1. **Given** a planned section, **When** the page renders, **Then** it carries a distinct de-emphasised treatment (muted heading + faded body + a left-margin rule) clearly different from a built section, in addition to (never instead of) its status label.
2. **Given** a partial section, **Then** its emphasis sits visibly between built and planned.
3. **Given** a planned section, **Then** all its prose, callouts, tables, and citations remain present, legible, and drill to source (fade signals status, it never hides or removes content).
4. **Given** any section, **Then** its status is still conveyed by an explicit text label, not by colour/fade alone.

---

### User Story 2 - Know a source's type at a glance (Priority: P1)

A reader looking at a citation chip, or drilling into a bundled source page, can immediately tell whether they're looking at a **spec**, **plan**, **ADR**, **research**, **code**, or **narrative** — by a consistent accent colour *and* an explicit type label — while the portal still reads as one cohesive document.

**Why this priority**: Today everything is one beige register; a reader cannot distinguish a governing ADR from a spec from free-form narrative when they drill in, which undercuts trust and navigation.

**Independent Test**: Render chips and source pages for each of the six categories; confirm each carries a consistent, category-specific accent (a thin left rule + small label tint + chip accent) **and** an explicit type label ("ADR", "Spec", …); confirm an uncategorised source falls back to a neutral accent; confirm the whole page still reads as one design system (no per-page re-skin).

**Acceptance Scenarios**:

1. **Given** a citation chip, **When** it renders, **Then** its accent reflects its source category and the category is also stated in text.
2. **Given** a drilled source page, **Then** its header shows a tinted band + an explicit type label + a thin left rule matching the source's category.
3. **Given** sources of all six categories on the same portal, **Then** each is distinguishable by accent + label, yet the portal remains visually one document (shared type system, layout, and palette).
4. **Given** a source with no recognised category, **Then** it renders with a neutral default accent and a generic label (never a broken/missing accent).

---

### User Story 3 - Navigation that scales (Priority: P3)

A reader of a portal with many capabilities (and per-tier sub-links) can still navigate without the table-of-contents becoming crowded or unusable.

**Why this priority**: Minor today (fine at ~8 capabilities) but degrades as capability count and sub-links grow; lowest priority and must not compromise the single-file deterministic output.

**Independent Test**: Render a portal with a large number of capabilities (and sub-links) and confirm the navigation remains usable (grouped or rail layout) and the output is still a single self-contained deterministic file.

**Acceptance Scenarios**:

1. **Given** a portal with many capabilities, **When** it renders, **Then** the navigation stays readable and usable (no overflow/crowding that hides links).
2. **Given** the same inputs, **Then** the output remains a single self-contained file rendered deterministically.

---

### Edge Cases

- A section whose status is unknown/unset → treated as the most conservative legible default (not silently shown as built).
- A source whose category cannot be derived → neutral default accent + generic label (US2 #4).
- Print and reduced-motion contexts → the status/type signals remain legible (fade/accents resolve to print-safe, motion-free equivalents).
- Colour-blind / low-vision readers → every status and type is also carried by text + shape/weight, so no information is lost if colour is imperceptible.
- A very long single capability vs many short ones → navigation and status/type treatments hold at both extremes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST render build status (built / partial / planned) with a pre-attentive visual difference — planned de-emphasised (muted heading + faded body + a left-margin treatment), partial intermediate, built full weight.
- **FR-002**: Build-status de-emphasis MUST NOT remove, hide, or truncate content; planned content stays fully present, legible, and able to drill to its source.
- **FR-003**: Build status MUST always be conveyed by an explicit text label in addition to the visual treatment (colour/fade is never the sole signal).
- **FR-004**: The system MUST assign a consistent accent per source category for the six categories (spec, plan, ADR, research, code, narrative), derived deterministically from each source's kind/type, with a neutral default for any uncategorised source.
- **FR-005**: The source-type accent MUST be applied to the citation chips and to the drilled source-page header (a tinted band + an explicit type label + a thin left rule).
- **FR-006**: Every source-type accent MUST be accompanied by an explicit text label of the category (colour is never the sole signal).
- **FR-007**: The whole portal MUST remain one cohesive editorial design system — a single shared palette/type system/layout; no second visual system, no per-page themes, no dark mode.
- **FR-008**: Text MUST meet WCAG AA contrast; status and type information MUST remain perceivable without colour (text label + weight/shape), satisfying colour-blind/low-vision readers.
- **FR-009**: The rendered output MUST remain a single self-contained HTML file produced deterministically (identical inputs → identical bytes), and remain print- and reduced-motion-safe.
- **FR-010**: Navigation MUST remain usable as the number of capabilities and per-tier sub-links grows, without breaking the single-file deterministic output.
- **FR-011**: This feature MUST NOT change the faithfulness engine (verify gates, clustering, IR rules); it is presentation-only, and any data-model additions are additive.
- **FR-012**: The visual-contract template MUST stay in sync with the renderer so the documented design system matches what is emitted.

### Key Entities *(include if feature involves data)*

- **Source category**: one of spec · plan · ADR · research · code · narrative (+ a neutral default) — the unit the colour taxonomy keys on; derived from a source's kind/type.
- **Build status**: built · partial · planned — the per-section emphasis level.
- **Citation chip**: the inline reference to a source; carries the source category (accent + label).
- **Source page**: a drilled, bundled source view; its header carries the category band + label + rule.
- **Capability section**: a unit of the narrative; carries a build status that drives its emphasis.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a quick scan (no badge reading), a viewer can correctly classify a section as built vs planned — built and planned sections are visually distinguishable at a glance, with partial discernibly between them.
- **SC-002**: 100% of citation chips and drilled source pages display both an accent and an explicit type label for their category; 0 rely on colour alone.
- **SC-003**: All six source categories are mutually distinguishable by accent + label; an uncategorised source always renders a neutral accent + generic label (never blank/broken).
- **SC-004**: The portal renders as a single self-contained file, byte-identical across repeat renders of the same input.
- **SC-005**: All body text meets WCAG AA contrast; with colour removed (e.g. grayscale/print), every status and type remains identifiable from text + weight/shape.
- **SC-006**: Navigation remains usable (no hidden/overflowing links) at ≥20 capabilities with per-tier sub-links.
- **SC-007**: The faithfulness gates and clustering are unchanged and all existing reader tests continue to pass.

## Assumptions

- Builds on the renderer-v2 editorial design system (spec 001): light-only, warm paper palette, the existing type system; accents are tuned within that palette, not a new theme.
- The six-category taxonomy and the "neutral default for uncategorised" are settled (best-practice); exact hues and fade strength are a visual-quality tuning done in implementation against the design system and the north-star example, not abstract questions.
- Build status per section is already computed (built/partial/planned, spec 006); this feature consumes it for emphasis.
- Source category is derived from the existing fragment kind / SourceType; any field needed to surface it on a chip/section is additive.
- Out of scope: clustering / capability grain (specs 009/010), the governance authoring note, catalog publish, dark mode, and any second visual system.
