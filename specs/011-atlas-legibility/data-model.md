# Phase 1 Data Model: Atlas Legibility

Presentation-only; no schema change. The "model" is the deterministic derivations + the render contract.

## Source category (6 + neutral)

`category` vocabulary: `spec` · `plan` · `adr` · `research` · `code` · `narrative` · `source` (neutral default).

- **From fragment `kind`** (source pages): `spec|tasks|data-model|contract → spec`; `plan → plan`; `research → research`; `adr → adr`; `code|code-symbol → code`; `design-doc → narrative`; else → `source`.
- **From `SourceRef`** (chips; no kind available): by `SourceType` then locator filename — `ADR → adr`; `CODE → code`; `DESIGN_DOC → narrative`; `SPEC → plan` if locator basename is `plan.md`, `research` if `research.md`, else `spec`; else → `source`.

Both functions are pure and total (always return a category). A render helper `_source_category(...)` centralises each.

## Build-status emphasis levels

`Section.build_status ∈ {built, partial, planned, None}` → emphasis:
- `built` (or `None`→treated as built-weight but conservatively, see edge case) → full weight, no status class.
- `partial` → intermediate: subtle solid left rule + slightly muted heading.
- `planned` → de-emphasised: reduced opacity + desaturated/muted heading + faint dashed left rule down the section; block-level planned fading retained.
- Always accompanied by the existing `.bstatus` text badge.

## Accent tokens (added to `DEFAULT_THEME`, additive)

`acc-spec, acc-plan, acc-adr, acc-research, acc-code, acc-narrative, acc-default` — low-saturation hues in the warm register (spec=gold, code=green, adr=red, narrative=blue reused; plan=muted teal, research=muted plum, default=neutral). Applied as: chip background, source-page header band + label tint, a thin left rule. Never a full content background.

## Render contract (classes/markup emitted)

- Section: `class="… planned"` or `class="… partial"` (built omits); badge unchanged.
- Chip: `<span class="cite-t cat-<category>">…</span>` + the visible category/name text (colour + label paired).
- Source-page header: a category band element with `cat-<category>` + an explicit type label ("ADR", "Spec", "Plan", "Research", "Code", "Narrative", "Source") + a thin left rule.
- Nav: bounded, wrapping/scrolling sticky TOC.

## Invariants (asserted in tests)

1. **Three statuses separate** — a planned section carries the planned class and a partial section the partial class; built carries neither; all three still emit the text badge.
2. **Content preserved under fade** — planned section still contains all its blocks/chips (fade is CSS only; no content removed).
3. **Six categories + default** — each category yields its `cat-<x>` class on chips and the source-page band; an uncategorised source yields `cat-source` + a generic label.
4. **Colour never sole signal** — every status and category also emits its text label.
5. **Determinism** — identical model+theme → byte-identical HTML.
6. **One design system** — no `data-theme`, no second stylesheet, light-only (no dark-mode tokens reintroduced).
7. **Template parity** — `storybook.html` contains the same status/category CSS classes as `render.py` emits.
