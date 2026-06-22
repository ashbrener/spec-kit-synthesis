# Tasks: Source-Anchored Capability Clustering

**Feature**: `009-source-anchored-clustering` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Approach**: TDD — every behavior change lands as a failing test first, then the minimal code to pass, suite green before push. The change is concentrated in `skill/scripts/cluster.py`; downstream phases are regression verification that multi-membership is tolerated.

**Tests**: REQUESTED (project is dogfooding TDD; US3 is explicitly about determinism/evidence guarantees).

## Phase 1: Setup

- [x] T001 Confirm baseline green: `uv run pytest skill/tests -q` (record current pass count) and re-read `skill/scripts/cluster.py` + `skill/tests/test_cluster.py` to inventory existing behaviors that must be preserved (classification, ordering, unclustered, evidence).

## Phase 2: Foundational (blocking prerequisites)

These build the unit/edge scaffolding the membership rules need. No behavior change to outputs yet.

- [x] T002 In `skill/scripts/cluster.py`, add a deterministic **feature-unit** builder: map every fragment to a unit key `(origin, feature_key)` (feature-less fragments → singleton unit `(origin, "#"+id)`), retaining fragment ids, origin role (source vs build via `source_origins`), and a derived `shape` (`spec`/`code`/`adr`/`other`) from fragment kinds/types. Pure, sorted.
- [x] T003 In `skill/scripts/cluster.py`, add a **unit-level typed strong-edge** index built from `LinkGraph`: for each `derived_from`/`cites`/`implements` edge, resolve both endpoint locators to their units and record `(rel, src_unit, dst_unit, evidence_note)`; exclude `references` (weak). Sorted/deterministic; reuse `_short` for notes.

## Phase 3: User Story 1 — Bridging artifacts don't collapse capabilities (Priority: P1) 🎯 MVP

**Goal**: source features anchor separate capabilities; a build artifact relating to several attaches to each (multi-membership) without merging the anchors.

**Independent test**: two unconnected source features + a build feature related to both ⟹ two capabilities, build feature in both.

### Tests (write first, watch fail)

- [x] T004 [P] [US1] In `skill/tests/test_cluster.py`, add `test_bridging_build_artifact_does_not_merge_sources`: S1, S2 (source) unconnected; B `derived_from` both ⟹ exactly two `capability` clusters anchored S1, S2; B's fragments members of both; assert no cluster mixes two source anchors (SC-002).
- [x] T005 [P] [US1] Add `test_source_anchored_one_capability_per_feature`: N source features ⟹ N capability clusters (each `seed` == its feature_key); a `references`-only link between two anchors does NOT merge them (weak-relation guard, FR-003).
- [x] T006 [P] [US1] Add `test_melded_chain_source_spec_code`: `K implements B`, `B derived_from S` ⟹ K and B both members of cap(S) via R1→R2 (the source→spec→code chain still coheres).

### Implementation

- [x] T007 [US1] In `skill/scripts/cluster.py`, implement the **anchored typed fixpoint** in `build_clusters`: anchors = source-role units with a feature_key, each seeding one capability; grow membership by R1 (`derived_from`→add deriving spec), R2 (`implements`→add code), R3 (`cites`→add ADR), never adding an anchor to another capability, treating ADR/code units as sinks (no outward expansion). Record an evidence note per non-anchor placement. Replace the connected-component union over strong edges for source-anchored clusters.
- [x] T008 [US1] Ensure multi-membership emission: a unit may appear in several capabilities' `members`; keep members grouped by origin/tier (source-first) and sorted; keep deterministic cluster ordering (kind rank → source-seeded before orphans → id). Run T004–T006 to green.

## Phase 4: User Story 2 — Decisions & background attach where they belong (Priority: P2)

**Goal**: cited ADRs join their capability; uncited ADRs / untied narrative stay honest standalones.

**Independent test**: spec in S1 cites ADR-A, ADR-B cited by nothing ⟹ ADR-A ∈ cap(S1) (not singleton); ADR-B standalone `decision`.

### Tests (write first, watch fail)

- [x] T009 [P] [US2] Add `test_cited_adr_joins_capability_not_singleton`: a member spec of cap(S1) cites ADR-A ⟹ ADR-A is a member of cap(S1), and there is no standalone `decision` cluster for ADR-A.
- [x] T010 [P] [US2] Add `test_shared_adr_does_not_bridge_capabilities`: B1∈S1 and B2∈S2 both cite ADR-X ⟹ ADR-X ∈ both capabilities, but B2 ∉ cap(S1) and B1 ∉ cap(S2) (ADR is a sink; SC-003, invariant 3).
- [x] T011 [P] [US2] Add `test_uncited_adr_and_untied_narrative_stay_honest`: an ADR cited by nobody ⟹ own `decision` cluster; a feature-less, edge-less narrative fragment ⟹ `background`/unclustered, never force-attached (FR-005).

### Implementation

- [x] T012 [US2] In `skill/scripts/cluster.py`, finalize the **orphan/standalone pass**: any unit not placed in a source capability is emitted as orphan `capability` (untied build feature), `decision` (uncited ADR), or `background`/`unclustered`; orphan union over strong edges **excludes ADR-as-bridge** so the remainder cannot re-collapse. Preserve `_classify` (spec 007). Run T009–T011 to green.

## Phase 5: User Story 3 — Reviewable, deterministic, honest (Priority: P3)

**Goal**: every placement is evidence-backed; output is byte-identical across runs; nothing fabricated.

### Tests (write first, watch fail)

- [x] T013 [P] [US3] Add `test_clusterset_is_byte_identical_across_runs`: build twice on identical inputs ⟹ `model_dump_json()` equal (FR-008).
- [x] T014 [P] [US3] Add `test_every_nonanchor_membership_has_evidence`: for each cluster, every member not part of the anchor feature has a matching evidence note naming the relation (FR-007, SC-005).
- [x] T015 [P] [US3] Add `test_no_membership_without_basis`: a fragment with no feature_key and no strong edge never appears in a capability (fail-closed, FR-010, invariant 8).

### Implementation

- [x] T016 [US3] Tighten evidence notes + determinism in `skill/scripts/cluster.py` (sorted worklist, sorted emit, deterministic evidence ordering) so T013–T015 pass; remove any dead union-find paths no longer used (or keep `_UF` only for the orphan union, documented).

## Phase 6: Downstream tolerance & polish (cross-cutting)

- [x] T017 [P] Run `skill/tests/test_atlas_meld.py` and `skill/tests/test_render_meld.py`; if a hidden disjointness assumption surfaces (a fragment in >1 cluster), fix the consumer in `skill/scripts/synthesize_atlas.py` / render so source content stays bundled once and is cited from each capability (FR-011). Add a regression test if a fix was needed.
- [x] T018 [P] Verify `skill/scripts/build_status.py` and `skill/scripts/source_index.py` compute correctly over overlapping membership (no double-counted coverage; index renders shared members sanely). Add/adjust tests if needed.
- [x] T019 (SKIPPED — not needed; no consumer required it) If (and only if) a consumer needs it, add the additive `CapabilityCluster.shared: bool = False` flag in `skill/scripts/schema.py` and set it in `cluster.py`; otherwise skip (keep schema untouched). Update `skill/tests/test_schema*.py` only if the field is added.
- [x] T020 Update docstrings in `skill/scripts/cluster.py` (module header + `build_clusters`) to describe the source-anchored multi-membership model; ensure no spec numbers/FR codes leak into any rendered narrative (constitution II).
- [x] T021 Full gate: `uv run pytest skill/tests -q` green on 3.11/3.12 path; scrub-grep the diff for forbidden tokens; confirm `verify.py`/`verify_links.py` untouched.

## Dependencies & order

- Setup (T001) → Foundational (T002–T003) → US1 (T004–T008) → US2 (T009–T012) → US3 (T013–T016) → Polish (T017–T021).
- US1 is the MVP (the over-merge fix). US2 and US3 build on the same fixpoint; their tests are independent and can be written in parallel within their phase.
- `[P]` tasks are test files / independent reads — the implementation tasks (T007, T008, T012, T016) all touch `cluster.py` and are sequential.

## Parallel execution examples

- Within US1: T004, T005, T006 (all new tests in `test_cluster.py`, independent assertions) can be drafted together, then T007/T008 implement.
- Polish: T017 and T018 touch different consumers and can run in parallel.

## Implementation strategy

**MVP = Phase 1–3 (US1):** delivers the over-merge fix (the actual render-quality blocker). Ship-able and independently testable on its own. US2 (singleton fix) and US3 (guarantees) complete the feature; Polish confirms the meld/render tolerate multi-membership end-to-end.
