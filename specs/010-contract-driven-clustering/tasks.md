# Tasks: Contract-Driven Capability Clustering

**Feature**: `010-contract-driven-clustering` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Approach**: TDD — failing test first, minimal code, suite green before push. Three localised changes: R1 evidence-tier gating (`cluster.py`), FR-004 hub flag (`schema.py`+`cluster.py`), R3 ingestion hygiene (`adapter_doc.py`).

## Phase 1: Setup
- [x] T001 Confirm baseline green (`uv run pytest skill/tests -q`); re-read `skill/scripts/cluster.py` strong-edge build loop, `LinkEvidenceKind`, and `adapter_doc._is_skipped` to confirm the seams.

## Phase 2: User Story 1 — inference doesn't cluster (R1) (P1) 🎯 MVP
### Tests
- [x] T002 [P] [US1] `test_identifier_build_to_build_confers_no_membership` in `skill/tests/test_cluster.py`: two build features joined only by an `identifier` `derived_from` edge are not co-members of any capability.
- [x] T003 [P] [US1] `test_identifier_source_to_build_still_confers` in `test_cluster.py`: on a workspace with no declared edges, a source↔build `identifier` edge groups the pair (un-governed workspace still clusters).
- [x] T004 [P] [US1] `test_membership_invariant_to_inferred_noise` in `test_cluster.py`: building with vs without all build↔build identifier + prose edges yields byte-identical membership.
### Implementation
- [x] T005 [US1] In `skill/scripts/cluster.py`, gate the strong-edge build: an edge confers membership iff `evidence_kind==declared`, OR (`evidence_kind==identifier` AND exactly one endpoint origin ∈ `source_origins`). Exclude `prose` and build↔build/source↔source identifier. Same-feature grouping unchanged. Run T002–T004 green.

## Phase 3: User Story 2 — hubs faithful + flagged (FR-004) (P1)
### Tests
- [x] T006 [P] [US2] `test_hub_rendered_faithfully_and_flagged` in `test_cluster.py`: a source feature declared `derived_from` by N≥2 features renders as the declared capability (members = its declared dependents) with `hub_dependents == N`; not split/re-anchored.
- [x] T007 [P] [US2] `test_non_hub_has_zero_hub_dependents` in `test_cluster.py`: a leaf/planned/orphan capability has `hub_dependents == 0`.
### Implementation
- [x] T008 [US2] In `skill/scripts/schema.py`, add additive `CapabilityCluster.hub_dependents: int = 0`.
- [x] T009 [US2] In `skill/scripts/cluster.py`, compute `hub_dependents` for each capability = count of distinct features that declare `derived_from` its anchor (declared edges only); set it on emit. No demotion/split. Run T006–T007 green.

## Phase 4: User Story 3 — ingest only source-of-truth (R3) (P2)
### Tests
- [x] T010 [P] [US3] `test_meta_and_archive_excluded` in `skill/tests/test_adapter_doc.py`: a tree with an `archive`/`99_Archive` dir, an `_Audits` dir, and `CLAUDE.md`/`RESUME.md`/`BACKEND_HANDOFF.md`/`WORKTREES.md` yields no fragments from those; real docs/specs/ADRs in the same tree are still ingested.
### Implementation
- [x] T011 [US3] In `skill/scripts/adapter_doc.py`, extend `_is_skipped` with deterministic defaults: dir name contains `archive`/`audit`; basename ∈ {claude.md, agents.md, gemini.md, resume.md, worktrees.md} or contains `handoff` (case-insensitive). Run T010 green.

## Phase 5: Polish & cross-cutting
- [x] T012 [P] Run `skill/tests/test_atlas_meld.py`, `test_render_meld.py`, `test_docs_authority.py` — confirm meld/render tolerate the gated membership + additive field with no change; fix only if a regression surfaces.
- [x] T013 Update docstrings: `cluster.py` (evidence-tier gate + hub flag), `adapter_doc.py` (meta/archive skip). No spec numbers/FR codes leak into rendered narrative (constitution II).
- [x] T014 Full gate: `uv run pytest skill/tests -q` green; scrub-grep the diff; confirm `verify.py`/`verify_links.py` untouched.
- [x] T015 Optional (read-only) re-confirm on the live workspace via the planning assessment script: catch-alls gone, noise clusters down, residual breadth flagged `hub_dependents>=2`.

## Dependencies & order
Setup (T001) → US1 (T002–T005, MVP) → US2 (T006–T009) → US3 (T010–T011) → Polish (T012–T015). `[P]` = independent test files. Impl tasks touching `cluster.py` (T005, T009) are sequential.

## Implementation strategy
**MVP = US1** (evidence-tier gating) — removes the catch-all contamination, the dominant defect. US2 (flag) + US3 (hygiene) complete the faithful picture.
