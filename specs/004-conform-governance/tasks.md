# Tasks: Conform to arch-governance contracts (the reader)

**Feature**: `004-conform-governance` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Tests are included (synthesis is test-first; the drift guard is itself a test). Neutral examples only
(`CORE`/`API`/`WEB`) — no real consumer names anywhere.

## Phase 1: Setup

- [X] T001 Add `pyyaml` to `pyproject.toml` dependencies (governed configs/manifest are YAML).
- [X] T002 [P] Vendor pinned contract copies into `skill/scripts/vendor/`: `vocabulary.json` (@0.2.0) and `domain.schema.json`, copied verbatim from the published contract; add a one-line `vendor/README.md` noting the pinned source + tag.
- [X] T003 [P] Create a neutral governed fixture tree under `skill/tests/fixtures/governed/` — an authority repo with `.spec-arch-domain.yml` (members `CORE`/`API`/`WEB`) + per-repo `.spec-arch-governance.yml`, a bare `ADR-001` decision, a plan citing it, and code implementing a spec.

## Phase 2: Foundational (blocks US2 + US3)

- [X] T004 Create `skill/scripts/gov_config.py`: read a repo's `.spec-arch-governance.yml` (→ its `namespace`, `adr_dir`, `specs_dir`) and an authority repo's `.spec-arch-domain.yml` (→ validated members/roles/namespaces/locators). Pure, deterministic, `pyyaml`; returns typed pydantic models; tolerant of absent files (returns None).
- [X] T005 [P] Validate the domain manifest against the vendored `skill/scripts/vendor/domain.schema.json` inside `gov_config.py`; invalid → return a structured error (caller falls back), never raise through.
- [X] T006 [P] Tests `skill/tests/test_gov_config.py`: reads namespace from a per-repo config; loads + validates a domain manifest; rejects a malformed manifest; returns None when files absent.

## Phase 3: User Story 1 — typed citation graph (Priority: P1) 🎯 MVP

**Goal**: relations match the contract and the `cites` edge exists. **Independent test**: governed
fixture's plan→decision renders as a typed `cites` edge; code→spec as `implements`.

- [X] T007 [US1] Reconcile `LinkRel` in `skill/scripts/schema.py`: add `CITES = "cites"`; rename `DERIVES_FROM` value to `"derived_from"`; remove `SPECIFIED_BY`. Final set = derived_from/cites/implements/supersedes/references.
- [X] T008 [US1] Update `skill/scripts/discover_links.py` `_typed_edge`: code↔spec→`implements`; spec↔spec→`derived_from`; any↔adr→`cites`; docs↔spec→`references`; else→`references`. Remove the `specified_by` branch.
- [X] T009 [US1] In `discover_links.py`, discover `cites` edges from shared ADR identifiers (a spec/plan fragment and an adr fragment sharing a qualified ADR id) at the `identifier` tier.
- [X] T010 [P] [US1] Update `skill/scripts/synthesize_atlas.py` atlas rendering + any rel-display to the new relation names (no `specified_by`).
- [X] T011 [P] [US1] Update `skill/tests/test_discover_links.py` + `skill/tests/test_portal_phase_e.py`: relation names → contract spelling; add a `cites`-edge case; drop `specified_by` assertions.
- [X] T012 [US1] Add `skill/tests/test_contract_conformance.py`: assert `LinkRel` values == `vendor/vocabulary.json` `relations` keys, and roles/kinds/evidence enums match too (the drift guard).

## Phase 4: User Story 2 — declared topology as source of truth (Priority: P2)

**Goal**: a `.spec-arch-domain.yml` drives structural topology; workspace.json = overlay + fallback.
**Independent test**: with the manifest, members/roles/namespaces come from it; without it, the
reader's record is used and the build still succeeds.

- [X] T013 [US2] In `skill/scripts/synthesize_atlas.py`, when `.spec-arch-domain.yml` is present (via `gov_config`), build the member topology (members/roles/namespaces/locators) from it as the source of truth; tag these facts `declared` (LinkEvidenceKind).
- [X] T014 [US2] Apply precedence: manifest wins on overlapping structural fields; `synthesis.workspace.json` supplies presentation (title/description/theme/order) always and full topology fallback when no manifest; the manifest contributes no presentation.
- [X] T015 [P] [US2] Tests in `skill/tests/test_gov_config.py` / a new `test_topology_precedence.py`: manifest-present → topology from manifest + presentation from workspace; manifest-absent → workspace fallback; overlapping field → manifest wins.

## Phase 5: User Story 3 — bare ADR-NNN qualified by namespace (Priority: P3)

**Goal**: bare `ADR-NNN` read under the owning repo's namespace, no renames; bare stays repo-local.
**Independent test**: governed fixture's bare `ADR-001` attributes to its namespace; a bare id does
not cross-match another repo.

- [X] T016 [US3] In `skill/scripts/discover_links.py`, recognise bare `ADR-NNN` (`^ADR-\d{3,}$`) and qualify it with the owning repo's namespace (from `gov_config`) → `<namespace>-ADR-NNN` before indexing; keep recognising the qualified form.
- [X] T017 [US3] Ensure a bare id is repo-local — never matched across a repo boundary; only the qualified form participates in cross-repo identifier edges.
- [X] T018 [P] [US3] Tests in `skill/tests/test_discover_links.py`: bare id qualified to its namespace; two repos each with `ADR-001` do NOT produce a spurious cross-repo edge; qualified cross-repo id does.

## Phase 6: Polish & cross-cutting

- [X] T019 [P] Wire `test_contract_conformance.py` into CI (`.github/workflows/ci.yml`) so drift fails the build.
- [X] T020 [P] Update docs: `skills/speckit-atlas/SKILL.md` + `README.md` note governed-repo reading (declared topology, typed citations, bare-ADR, evidence tiers) — as an enhancement, ungoverned unchanged. Neutral examples only.
- [X] T021 Run `uv run pytest skill/tests -q` (all green) and confirm the ungoverned baseline output is unchanged (SC-006); confirm no real consumer names in source/docs/tests (SC: FR-009).

## Dependencies & order

- Setup (T001–T003) → Foundational (T004–T006) → US1 (T007–T012) → US2 (T013–T015) → US3 (T016–T018) → Polish (T019–T021).
- **US1 is the MVP** (the correctness blocker — typed relations + `cites`); it depends only on Setup, not on US2/US3.
- US2 and US3 both depend on Foundational (`gov_config`); they are independent of each other.
- `[P]` tasks within a phase touch different files and can run in parallel.

## MVP scope

**User Story 1 alone** delivers the headline value: a governed project's citation graph becomes
visible and correctly typed. US2 (declared topology) and US3 (bare-ADR) are incremental enhancements.
