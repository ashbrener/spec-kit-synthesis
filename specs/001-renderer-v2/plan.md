# Implementation Plan: Renderer v2 — Editorial Design System

**Branch**: `001-renderer-v2` · **Spec**: `specs/001-renderer-v2/spec.md` · **Date**: 2026-06-03

## Summary

Adopt the editorial design system (`skill/templates/storybook.html`) as the single default output
of the deterministic renderer. The design system is the fixed contract; the `DocumentModel` is
extended to populate its slots. Render + presentation only — the faithfulness engine (adapters,
reconcile, `verify.py`) is untouched. Light-only, per-section disclosure, CDN fonts, vanilla
single-file HTML (no SPA), and diagrams that are semantic + animated per-layout.

## Technical Context

- **Language/deps**: Python ≥3.11, `pydantic` only; `uv` toolchain. Output is one self-contained
  HTML file (CSS+JS inlined, fonts via CDN `@import`).
- **Determinism**: stdlib only, no clock/rng; colophon carries no timestamp; identical input →
  identical bytes (tested).
- **Confirmed safe**: `verify.py` validates the IR, never HTML — the renderer can be rewritten
  freely. Only `test_render.py` and `test_render_coverage.py` assert old HTML and need rewriting.
  New schema fields are optional, so other tests/fixtures are unaffected.

## Constitution Check (SKILL.md invariants / DESIGN §11.2)

- **I. Faithfulness is architectural — PASS.** No claim/citation logic changes; `verify.py`
  unchanged. Citations move from Layer-2 chips to inline chips + References appendix, still
  source-typed and gate-resolved.
- **II. Organised by architecture, no source numbers in narrative — PASS.** Body stays
  number-free; sources live in chips and the appendix only.
- **III. Current state only — PASS.** Evolution still rendered as a single neutral callout.
- **IV. Fail-closed on gaps — PASS.** `unspecified` callouts render as the warning note variant;
  gate behaviour unchanged.
- **V. Stateless / pure function — PASS.** Renderer remains a pure, deterministic function;
  no persistent state introduced.
- **VII. Composition ≠ markup ≠ theme — PASS, strengthened.** Theme stays a flat token retint
  layer over a fixed design-system markup.

## Project Structure

### This feature
```
specs/001-renderer-v2/
  spec.md
  plan.md   (this file)
```

### Source changes
```
skill/scripts/schema.py        # Bucket 1 — schema deltas (optional fields)
skill/scripts/render.py        # Bucket 2 + 3 — renderer rewrite + per-layout diagram motion
skill/templates/storybook.html # visual contract (already present; render.py CSS mirrors it)
skill/tests/test_render.py     # rewrite — assert new structure
skill/tests/test_render_coverage.py  # rewrite — coverage pills
skill/tests/fixtures/document_model.json  # extend — new fields + hub/stack/timeline
skills/speckit-storybook/SKILL.md  # docs — layouts (5→8), compose fields, disclosure model
DESIGN.md                      # §11.3 resolved decision; §11.4 phase note
```

## Bucket 1 — Schema deltas (`skill/scripts/schema.py`)

- `DiagramGraph.layout`: extend Literal 5→8 (`+hub, +stack, +timeline`); default `pipeline`.
- New `MetaPair(BaseModel)`: `label`, `value` (extra=forbid).
- `DocumentModel`: `project_name: Optional[str]=None` (fallback `title`), `title_accent:
  Optional[str]=None`, `kicker: Optional[list[str]]=None`, `meta: list[MetaPair]=[]`; keep `lede`
  (rendered as deck).
- `Section`: `strap: Optional[str]=None`; `subtitle` → rendered as `p.lead`.
- `Block`: `prose_style: Optional[Literal["lead","pull"]]=None` + validator (PROSE only).
- `Altitude` unchanged: functional→inline, technical→per-section disclosure, provenance→appendix.

## Bucket 2 — Renderer rewrite (`skill/scripts/render.py`)

Reuse `esc()`, `_collect_section_refs()`, the diagram layout fns (restyled), the pure/
deterministic contract.

- Replace `DEFAULT_THEME` with the framework palette + font tokens; **delete `DARK_THEME`** and
  all `data-theme`/`data-depth` machinery; keep the flat `--theme` override.
- `build_css(theme)`: port the CSS from `skill/templates/storybook.html` (`:root` from theme
  dict) + per-layout motion CSS + reduced-motion/print guards.
- `render()`: emit `.grain`, `header.mast` (brand glyph + `project_name`, kicker, title with
  optional `<em>` accent, deck from `lede`, meta-row), sticky `nav.toc`, sections with
  `hr.divider`, `footer#refs` (References appendix + colophon + fixed repo-linked credit). Port
  framework JS (scrollspy, hamburger, accordion `e`/`c`+hash, figure reveal + timeline scrub,
  brand spin) merged with existing hover-caption + click-to-jump handlers.
- `_render_section()`: `sec-num` = `NN — strap`; `h2`; `subtitle`→`p.lead`; functional blocks
  inline; technical blocks collected into one trailing `<details class="mod">`; per-section
  citation line of `.ref` chips → `#refs`.
- Block mapping: prose (+`lead`/`pull` styles); callout→note variant (decision/unspecified/
  evolution); table→`.tbl`; coverage→`.tbl` with status pills; diagram→`<figure class="fig
  fig-<layout>">`.

## Bucket 3 — Diagram restyle + per-layout motion (`render.py`)

Restyle the 5 existing layouts + add `hub`/`stack`/`timeline`; each emits motion-hook classes;
`render_diagram` wraps with `fig-<layout>`.

| Layout | Motion |
|---|---|
| pipeline | stages illuminate L→R |
| flow | comet/trace travels path; branch peels after (loops) |
| ladder | rungs draw top→bottom in order |
| mapping | column-by-column: left → links → right |
| panel | cards stagger-fade |
| hub *(new)* | core pops, spokes draw out, nodes fade, ring sweeps |
| stack *(new)* | layers build bottom-up |
| timeline *(new)* | line draws L→R, nodes light in order, scroll-scrubbed |

Guardrails (acceptance): motion encodes meaning; reveal-once then rest (loop only for flow);
settles to correct static final state; reduced-motion → all off; scrub only where motion ==
reading progress, never scroll-jack; fast (~0.4–0.7s), staggered, eased.

## Tests & fixtures

- Rewrite `test_render.py`: assert masthead/title/deck/meta-row, `nav.toc` links, `sec-num`
  strap, note callout variants, `<details class="mod">`, `fig-<layout>` (incl. new three), `#refs`
  appendix + colophon + repo link, determinism, escaping, `--theme` override on new tokens, no
  leaked locators, light-only (no `data-theme`/`themeBtn`/`data-depth`).
- Rewrite `test_render_coverage.py`: coverage → `.tbl` status pills.
- Extend `document_model.json`: `project_name`, `title_accent`, `kicker`, `meta`, a section
  `strap`, a `prose_style="pull"` block, and one each of `hub`/`stack`/`timeline`.
- Gate: `uv run pytest skill/tests -q`.

## Docs

- `schema.py` docstrings for new fields.
- `SKILL.md`: 5→8 layouts; compose guidance for new fields; per-section disclosure + light-only.
- `DESIGN.md` §11.3: insert resolved decision (editorial design system as default; vanilla
  single-file; light-only; per-section disclosure; semantic per-layout motion; CDN fonts);
  §11.4 note renderer-v2 as the Phase-3 polish item.

## Verification

1. `uv run pytest skill/tests -q` green (3.11/3.12).
2. Regenerate a real storybook (project-arc / speckit-linear inputs) and eyeball against the
   contract template.
3. Determinism: render twice → identical bytes.
4. Optional: Codex cross-model faithfulness pass → confirm 0/0/0 holds.

## Complexity Tracking

No constitution violations. The renderer rewrite is large but mechanical; risk is concentrated in
diagram motion (mitigated by the six guardrails + per-layout tests) and CSS/template sync
(mitigated by keeping `storybook.html` as the single visual contract).

## Execution order

1. schema deltas → 2. fixture → 3. render.py (CSS, shell, sections, blocks, diagrams+motion, JS)
→ 4. rewrite the two render tests → 5. tests green → 6. docs → 7. regenerate + eyeball (+ Codex).
