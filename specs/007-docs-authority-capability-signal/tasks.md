# Tasks: Docs-authority capability signal

**Feature**: `007-docs-authority-capability-signal` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Test-first. Neutral examples only (`CORE`/`API`/`WEB`) — no real consumer/company/namespace names
(FR-013, SC-008).

## Phase 1: Setup

- [ ] T001 [P] Create `skill/tests/fixtures/docs_authority/` — a docs-authority workspace: a source
  repo `core` with `.spec-arch-domain.yml` + `.spec-arch-governance.yml` (specs_dir + adr_dir), a
  `specs/` holding ≥2 spec-kit features, an ADR dir holding a **cited** ADR and an **uncited** ADR,
  and ≥2 free-form narrative dirs (e.g. `01_overview/`, `05_research/`); build repos `api`/`web` whose
  specs `derive_from` the source specs and cite the cited ADR. Neutral names only.

## Phase 2: Foundational — path-prefix exclude (blocks US1)

- [ ] T002 In `skill/scripts/schema.py` add `IngestionSource.exclude: list[str] = []` (path-prefixes
  or bare names the ingestion of this source skips).
- [ ] T003 In `skill/scripts/adapter_doc.py` + `skill/scripts/adapter_code.py`: extend `_is_skipped`
  to honor a path-PREFIX exclude — an entry containing `/` matches when the file's relpath equals it
  or starts with `entry + "/"`; a bare name keeps the part match; hidden dot-dirs always skipped. Pass
  the relpath through `build_corpus` so prefixes resolve.
- [ ] T004 In `skill/scripts/synthesize_atlas.py` `_adapt_one`: forward an `IngestionSource.exclude`
  to the adapter via `--exclude` (comma-joined; values may contain `/`).
- [ ] T005 [P] Tests `skill/tests/test_adapter_doc.py`: a path-prefix exclude (`docs/adr`) skips
  exactly that subtree while keeping a similarly-named leaf elsewhere; a bare-name exclude still works;
  hidden dirs still always skipped.

## Phase 3: User Story 1 — cross-tier capabilities form (Priority: P1) 🎯 MVP

**Goal**: source specs read as distinct features; build specs cluster with the source spec they derive
from; no double-ingest. **Independent test**: on the docs-authority fixture, a build spec and its
source spec share a cluster; source specs are distinct (not one bucket); no file ingested twice.

- [ ] T006 [US1] In `skill/scripts/scaffold.py` `derive_manifest`: for a `source` member, emit merged
  sources — `speckit(specs_dir)` + `doc(adr_dir, adr_dir=".")` + `doc(repo, exclude=[specs_dir,
  adr_dir])` — omitting a pass when its dir is undeclared. Build/standalone members unchanged.
- [ ] T007 [P] [US1] Tests `skill/tests/test_scaffold.py`: a source member derives three passes
  (speckit specs + doc adrs + doc narrative-with-exclude); the narrative pass carries
  `exclude=[specs_dir, adr_dir]`; a build/standalone member's sources are unchanged.
- [ ] T008 [US1] Tests `skill/tests/test_docs_authority.py`: building the docs-authority fixture
  corpus + clusters → the source's specs are distinct features (count == declared, not collapsed); a
  build spec and the source spec it derives from are in the SAME cluster; no fragment appears twice
  (a spec is never also a design-doc fragment) (SC-001/002/003).

## Phase 4: User Story 2 — classify clusters (Priority: P2)

**Goal**: capability / decision / background labels so signal-less content can't pose as a capability.
**Independent test**: each cluster is classified; a cited ADR rides in its capability; an uncited ADR
is a decision; narrative is background.

- [ ] T009 [US2] In `skill/scripts/cluster.py` add `CapabilityCluster.kind: Literal["capability",
  "decision","background"]`; classify each cluster from membership (≥1 spec/code → capability; else
  only ADR → decision; else → background); order capabilities first, then decisions, then background.
- [ ] T010 [P] [US2] Tests `skill/tests/test_cluster.py`: a cluster with a spec → capability; a
  cited-ADR rides inside the citing spec's capability (not its own decision); an uncited ADR → a
  decision cluster; a narrative-only cluster → background; classification deterministic (SC-004/005).

## Phase 5: User Story 3 — fold-in contract + nothing else regresses (Priority: P3)

**Goal**: the agent folds decisions/background in correctly; build/standalone + ungoverned unchanged;
deterministic. **Independent test**: build/standalone ingestion unchanged; ungoverned output
unchanged; clusters reproducible.

- [ ] T011 [US3] Update `commands/atlas.md`: the fold-in contract — capabilities are the sections; a
  **cited** decision renders inline in its capability; **uncited** decisions → a Decisions appendix;
  **background** → a short Overview/Background section; never promote a lone decision or signal-less
  narrative to a capability; strict deterministic background (no auto-attach). Note the brief now
  carries each cluster's `kind`.
- [ ] T012 [P] [US3] Tests: a build/standalone member's derived sources are byte-identical to before
  (no regression); an ungoverned/non-docs-authority workspace's stage-0 output is unchanged;
  `build_clusters` is reproducible on the docs-authority fixture (SC-006/007).

## Phase 6: Polish & cross-cutting

- [ ] T013 [P] Update `README.md` + `CHANGELOG.md`: docs-authority capability signal (structure-aware
  source ingestion, classification, fold-in). Neutral examples.
- [ ] T014 Run `uv run pytest skill/tests -q` (all green); confirm no real consumer/company/namespace
  names in source/docs/tests/fixtures (SC-008); confirm the single-repo storybook + ungoverned
  baselines are unchanged.

## Dependencies & order

- Setup (T001) → Foundational exclude (T002–T005) → US1 source ingestion (T006–T008) → US2
  classification (T009–T010) → US3 contract + guards (T011–T012) → Polish (T013–T014).
- **US1 is the MVP** (cross-tier capabilities forming). US2 (classification) and US3 (fold-in +
  guards) layer on; US2 depends only on clustering, US3 only on the contract + existing behavior.
- `[P]` tasks touch different files (tests/fixtures) and can run in parallel.

## MVP scope

**User Story 1 alone** delivers the headline: on a docs-authority workspace, build specs and the
source specs they derive from actually meld into shared capabilities (the dogfood-#2 fix). US2 + US3
keep the story clean (classification) and safe (no regressions).
