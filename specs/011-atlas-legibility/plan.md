# Implementation Plan: Atlas Legibility

**Branch**: `011-atlas-legibility` | **Date**: 2026-06-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-atlas-legibility/spec.md`

## Summary

Presentation-only legibility pass on the renderer-v2 editorial design system. The plumbing already exists (`Section.build_status` built/partial/planned; source-typed citation chips; source pages carrying `kind`), so this is mostly CSS + small render seams:

1. **US1 build-status emphasis** — strengthen the `planned` treatment and *add* a `partial` treatment so built/partial/planned separate pre-attentively (muted heading + faded body + left rule), keeping the explicit badge.
2. **US2 source-type taxonomy** — widen the 4-type chip palette (`spec/code/doc/adr`) to the 6-category vocabulary (spec · plan · ADR · research · code · narrative + neutral default), add the matching accents, and give the drilled source-page header a tinted band + explicit type label + left rule.
3. **US3 nav scaling** — CSS-only: the sticky TOC wraps/scrolls and stays usable as links grow.

Colour is always paired with a text label (FR-006/008); single self-contained deterministic file preserved; the visual contract template (`storybook.html`) kept in sync.

## Technical Context

**Language/Version**: Python ≥3.11 · **Deps**: pydantic + stdlib · **Testing**: pytest (`uv run pytest skill/tests -q`) · **Output**: one deterministic self-contained HTML file (light-only, CDN fonts + system fallback) · **Constraints**: WCAG AA, colour-never-sole-signal, print/reduced-motion safe, no second visual system, faithfulness engine untouched.

## Constitution Check

| Principle | Status | How |
|---|---|---|
| I. Faithfulness (NON-NEGOTIABLE) | ✅ | Presentation only; verify gates/clustering/IR untouched (FR-011). Fade signals status, never hides content (FR-002). |
| II. Organized by architecture | ✅ | No spec numbers in prose; chips/labels unchanged in meaning. |
| III. Current-state only | ✅ | No historical content added. |
| IV. Fail-closed on gaps | ✅ | Unknown status → conservative legible default; uncategorised source → neutral accent + generic label (never blank). |
| V. Stateless; generated | ✅ | Pure function of the model + theme; deterministic. |
| VI. General reader | ✅ | Directly improves legibility for a non-specialist. |
| Arch: one design system | ✅ | Accents tuned within the existing palette; light-only; no per-page theme (FR-007). |
| Arch: reasoning vs determinism | ✅ | Deterministic render; no LLM. |
| Quality gates | ✅ | `verify*` untouched; `pytest` green before push; the north-star readability bar upheld. |

**Result: PASS.** No Complexity Tracking needed.

## Project Structure

```text
specs/011-atlas-legibility/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/legibility_contract.md
└── tasks.md   (/speckit-tasks)

skill/scripts/
├── render.py          # status CSS+classes (planned/partial); chip 6-category accents; nav CSS; theme accent tokens
└── render_sources.py  # source-page header: category band + type label + left rule
skill/templates/
└── storybook.html     # visual contract kept in sync (same CSS)
skill/tests/
├── test_render_meld.py / test_render.py     # status classes (planned+partial), chip categories+labels, determinism, no-colour-only
└── test_render_sources.py                   # source-page band + label per category + neutral default
```

**Structure Decision**: Single-library render layer; changes localised to `render.py` + `render_sources.py` (+ the template mirror). No schema change required — categories derive deterministically from existing `SourceType` + locator (chips) and `kind` (pages); status already on `Section`/`Block`.

## Phase 0 — Research

See [research.md](./research.md). No open clarifications (taxonomy + accent approach resolved best-practice; hues/fade are implementation tuning).

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — the category derivation (6 + neutral), the status emphasis levels, the accent token set, invariants.
- [contracts/legibility_contract.md](./contracts/legibility_contract.md) — render guarantees (classes, labels, accents, determinism, colour-never-sole-signal).
- [quickstart.md](./quickstart.md) — verify + the acceptance checks + eyeball vs the north-star.
- Agent context: point `CLAUDE.md` SPECKIT markers at this plan.

## Complexity Tracking

No violations — section intentionally empty.
