# Tasks: Atlas Legibility

**Feature**: `011-atlas-legibility` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Approach**: TDD, presentation-only. Changes in `render.py` (+ `render_sources.py`) and the `storybook.html` visual contract. Tests assert structure (classes/labels), determinism, and no-colour-only; visual hues are eyeballed.

## Phase 1: Setup
- [x] T001 Confirm baseline green (`uv run pytest skill/tests -q`); re-read `render._render_section`, `_cite_chip`, `DEFAULT_THEME`, the status/chip CSS, and `render_sources._page_html` to confirm seams.

## Phase 2: Foundational — category derivation + accent tokens
- [x] T002 In `skill/scripts/render.py`, add `_source_category(ref)` (SourceType+locator → spec|plan|adr|research|code|narrative|source) and a `kind`→category helper for source pages; add `_CATEGORY_LABEL` map. Pure/total.
- [x] T003 In `skill/scripts/render.py`, extend `DEFAULT_THEME` with additive accent tokens (`acc-spec/plan/adr/research/code/narrative/default`) reusing gold/green/red/blue + two muted hues (teal/plum) + neutral.

## Phase 3: US1 — build-status emphasis (P1) 🎯 MVP
### Tests
- [x] T004 [P] [US1] In `skill/tests/test_render_meld.py`, `test_partial_section_gets_partial_class`: a `partial` section emits a `partial` class + its badge; a `built` section emits neither.
- [x] T005 [P] [US1] `test_planned_section_strengthened_and_content_intact`: a `planned` section emits the `planned` class + badge, and all its blocks/chips are still present in the HTML (fade is CSS-only).
### Implementation
- [x] T006 [US1] In `render._render_section`, emit `planned`/`partial` class by `build_status` (built omits); in the status CSS, strengthen planned (opacity + muted heading + faint dashed left rule down the section) and add an intermediate `partial` treatment. Keep `@media print` legible. Run T004–T005 green.

## Phase 4: US2 — source-type taxonomy (P1)
### Tests
- [x] T007 [P] [US2] In `skill/tests/test_render.py`, `test_chip_emits_six_category_classes_and_labels`: chips for spec/plan/adr/research/code/narrative emit `cat-<category>` + visible label; an unknown source → `cat-source` + generic label.
- [x] T008 [P] [US2] In `skill/tests/test_render_sources.py`, `test_source_page_header_band_and_label`: a source page header emits a `cat-<category>` band + an explicit type label + left rule, derived from the fragment kind; uncategorised → `cat-source`.
### Implementation
- [x] T009 [US2] In `render._cite_chip` (+ appendix `reftype`), switch the type token to `cat-<category>` from `_source_category`, keeping the visible label; add `.cite-t.cat-*` / `.reftype.cat-*` accent CSS. Run T007 green.
- [x] T010 [US2] In `render_sources._page_html`, add the category band (`cat-<category>` + type label + thin left rule) using the fragment `kind`; add the CSS. Run T008 green.

## Phase 5: US3 — nav scaling (P3)
- [x] T011 [US3] In `render.py` nav CSS, make the sticky `nav.toc` link row wrap/scroll within a bounded height so it stays usable as links grow (CSS-only, single-file preserved). Add a light assertion if practical.

## Phase 6: Parity, polish, verify
- [x] T012 [P] (N/A — documented) `skill/templates/storybook.html` is the older renderer-v2 *standalone* sample and carries NONE of the meld-layer classes (`cite-t`/`planned`/`bstatus`/`srctype`) and no test references it; `render.py` is the source of truth for these. Forcing the classes in would fabricate structure, so parity is not applicable for this feature (noted in the PR).
- [x] T013 [P] Determinism + no-colour-only guards: a test that the meld render is byte-identical across two runs with the new features, and that every status/category emits a text label (not colour alone).
- [x] T014 Confirm light-only intact (no `data-theme`/dark tokens reintroduced) and `@media print`/reduced-motion keep content legible.
- [x] T015 Full gate: `uv run pytest skill/tests -q` green; scrub-grep the diff; `verify.py`/`verify_links.py` untouched. Regenerate a sample + eyeball vs the north-star (visual-quality).

## Dependencies & order
Setup (T001) → Foundational (T002–T003) → US1 (T004–T006, MVP) → US2 (T007–T010) → US3 (T011) → Parity/verify (T012–T015). `[P]` = independent test files. Impl tasks in `render.py` (T006, T009, T011) are sequential (same file).

## Implementation strategy
**MVP = US1** (build-status emphasis) — the highest-impact legibility fix. US2 (taxonomy) is the other P1; US3 is minor. Parity + determinism guards close it out.
