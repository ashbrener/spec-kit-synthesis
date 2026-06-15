# Tasks: Governed auto-scaffold + one-command atlas (the reader)

**Feature**: `005-governed-autoscaffold` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Tests are included (synthesis is test-first). Neutral examples only (`CORE`/`API`/`WEB`) — no real
consumer/company/namespace names anywhere (FR-016, SC-007).

## Phase 1: Setup

- [X] T001 Extend the governed fixture tree `skill/tests/fixtures/governed/` so it exercises discovery
  + merged ingestion: in each **build** repo's `.spec-arch-governance.yml` add a `sources:` entry with
  `role: source` pointing at the `CORE` source repo, and ensure every repo declares `specs_dir` and
  `adr_dir`; the `CORE` source repo keeps its `.spec-arch-domain.yml` (members `CORE`/`API`/`WEB`), a
  bare `ADR-001`, and a build-repo spec/plan that derives from / cites it. Neutral names only.

## Phase 2: Foundational (blocks US1, US2, US3)

- [X] T002 In `skill/scripts/schema.py` add `IngestionSource` (`adapter: Literal["speckit","code","doc"]`,
  `path: str`, `adr_dir: Optional[str]=None`, `include: Optional[str]=None`, `extra="forbid"`) and add
  `sources: Optional[list[IngestionSource]] = None` to `WorkspaceMember`, with a validator that an
  empty list normalizes to `None` (legacy single-adapter path stays the default).
- [X] T003 In `skill/scripts/gov_config.py` add `RepoSource` (`id: Optional[str]`, `locator: str`,
  `role: Optional[str]`) and `sources: list[RepoSource] = []` to `RepoConfig` (keep `extra="ignore"`),
  so a build repo's `sources:` pointer is parsed instead of dropped.
- [X] T004 [P] Tests `skill/tests/test_gov_config.py`: `RepoConfig.sources` parses a `sources:` list
  (id/locator/role); absent `sources` → `[]`; unrelated keys still ignored.
- [X] T005 In `skill/scripts/synthesize_atlas.py` generalize `build_member_corpus`: when
  `member.sources` is set, adapt each `IngestionSource` (its `adapter` over its `path`, passing
  `--adr-dir`/`--include` where applicable) and **merge** all fragments into one origin-stamped
  `FragmentCorpus`; when `sources` is `None`, keep the existing single-adapter path unchanged.
- [X] T006 [P] Tests `skill/tests/test_merged_ingestion.py`: a member with two `sources` (a speckit
  specs dir + a doc adr dir) yields one origin-stamped corpus containing both kinds; the legacy
  single-adapter member is byte-identical to before; merged fragment ids do not collide.

## Phase 3: User Story 1 — one command on a governed workspace (Priority: P1) 🎯 MVP

**Goal**: no hand-authored manifest; topology matches the domain manifest; works launched from any
member. **Independent test**: in the governed fixture, build with no manifest from CORE and from a
build repo → a portal whose members/roles/namespaces equal the domain manifest, identical either way.

- [X] T007 [US1] Create `skill/scripts/scaffold.py` with `discover_authority(start, max_hops)`:
  return `start` if it owns `.spec-arch-domain.yml`; else follow its `.spec-arch-governance.yml`
  `sources[role==source]` locator to the source repo, recursing with a visited-set cycle guard and the
  hop bound; return `None` when exhausted. Pure, read-only.
- [X] T008 [P] [US1] Tests `skill/tests/test_scaffold.py` (discovery): authority found directly; found
  from a build repo via `sources`; cycle guard terminates; ungoverned start → `None`.
- [X] T009 [US1] In `skill/scripts/scaffold.py` add `derive_manifest(authority)`: read the validated
  domain manifest; for each `DomainMember` emit one `WorkspaceMember` (origin=name; badge role mapped
  source→`docs`/build→`spec`/standalone→`spec`; namespace declared) whose `sources` are assembled from
  that repo's `RepoConfig` per the role mapping (`specs_dir`→speckit; `adr_dir`→doc with `adr_dir`;
  source role adds a free-form-docs doc source). Paths relative to the authority dir. Build-repo code
  excluded by default.
- [X] T010 [P] [US1] Tests `skill/tests/test_scaffold.py` (derivation): derived member set equals the
  domain members exactly (no more/fewer); each member's namespace/locator come from the manifest; a
  source member's `sources` include specs + ADRs, a build member's include specs only.
- [X] T011 [US1] In `skill/scripts/synthesize_atlas.py` `main`: make `manifest` optional
  (`nargs="?"`); add `--from <dir>` (default cwd) and `--authority <dir>`. When an authority is
  discovered, set `base = authority`, read the domain manifest from the authority (decoupled from any
  manifest-file location), `derive_manifest`, and run the unchanged pipeline over the derived manifest.
- [X] T012 [US1] Tests `skill/tests/test_atlas_scaffold.py`: a no-manifest build on the governed
  fixture produces a site; `topology.json` shows members graded `declared`; launching from CORE vs a
  build repo yields the same derived member set (SC-001/002/003).

## Phase 4: User Story 2 — faithful, transparent derivation (Priority: P2)

**Goal**: derive only what governance declares, ingest from the declared locations, and account for it
all in a reviewable report. **Independent test**: run derivation on the fixture and inspect the
report; assert per-member declared facts + the `specs_dir`/`adr_dir` read, with skipped members listed
and nothing inferred.

- [X] T013 [US2] In `skill/scripts/scaffold.py` add `ScaffoldReport`/`ScaffoldMember` and have
  `derive_manifest` return `(WorkspaceManifest, ScaffoldReport)`; in `synthesize_atlas.main` print the
  report **before** reasoning (per member: declared role/namespace/locator + specs_dir/adr_dir read;
  skipped members) (FR-011).
- [X] T014 [US2] In `derive_manifest`, skip a declared member whose repo is absent on disk (record it
  in `report.skipped`, mark the member `optional`), and ensure **no invention**: derive only members,
  paths, and ingestion locations the governance files declare (FR-009); a member whose config omits
  `specs_dir`/`adr_dir` contributes only what is declared.
- [X] T015 [US2] Ensure the ingestion wiring is faithful: the `adr_dir` doc source forces ADR
  classification (via `adapter_doc --adr-dir`) even when the directory is not filename-detectable, and
  specs are ingested structure-aware via the speckit source (FR-006) — verified end-to-end that ADR
  fragments appear in the source member's corpus.
- [X] T016 [P] [US2] Tests `skill/tests/test_scaffold.py` (faithfulness/report): report lists declared
  facts + per-repo locations + skipped members; a malformed domain manifest → error reported and
  fallback (no derivation); a missing optional repo is skipped and the build still succeeds
  (SC-004/006).

## Phase 5: User Story 3 — operator overlay + ungoverned fallback (Priority: P3)

**Goal**: a hand-authored manifest overlays presentation and may add/override members; an ungoverned
workspace is unchanged. **Independent test**: (a) governed + partial manifest → structure declared,
presentation from the operator; (b) ungoverned + no manifest → clear "manifest required"; ungoverned +
manifest → today's behavior.

- [X] T017 [US3] In `skill/scripts/scaffold.py` add `overlay_manifest(derived, operator)`: operator
  presentation (title/description/theme) always wins; operator-only members are added; an operator
  member matching a derived origin overrides it (including enabling build-repo code) (FR-010).
- [X] T018 [US3] In `skill/scripts/synthesize_atlas.py` `main`: when both a manifest and an authority
  are present, overlay; when no authority and no manifest, exit with a clear "ungoverned — manifest
  required" message inventing nothing (FR-003); when no authority but a manifest is given, run today's
  path unchanged with `base = manifest.parent` (FR-015).
- [X] T019 [P] [US3] Tests `skill/tests/test_atlas_scaffold.py` (overlay/fallback): governed + partial
  manifest → presentation from operator, topology `declared`; an operator-added member appears; an
  operator override enables code on a build repo; ungoverned + no manifest → clear error; ungoverned +
  manifest → output unchanged vs a pre-feature run (SC-005).

## Phase 6: Polish & cross-cutting

- [X] T020 [P] Update `skills/speckit-atlas/SKILL.md`: document the one-command governed path (invoke
  with no manifest → discover → derive → report → unchanged pipeline), the `--from`/`--authority`
  flags, operator overlay, and the ungoverned requirement. Neutral examples only.
- [X] T021 [P] Update `README.md`: a short "governed workspaces: one command, no manifest" note
  (neutral CORE/API/WEB), framed as an enhancement; ungoverned usage unchanged.
- [X] T022 Run `uv run pytest skill/tests -q` (all green); confirm the ungoverned baseline output is
  unchanged (SC-005); confirm no real consumer/company/namespace names in source/docs/tests/fixtures
  (SC-007, FR-016). The drift guard (`test_contract_conformance.py`) and CI from 004 already run these.

## Dependencies & order

- Setup (T001) → Foundational (T002–T006) → US1 (T007–T012) → US2 (T013–T016) → US3 (T017–T019) →
  Polish (T020–T022).
- **US1 is the MVP** (the one-command headline); it depends on Foundational, not on US2/US3.
- US2 and US3 depend on US1's `scaffold.py` + `main` wiring; they are independent of each other.
- `[P]` tasks within a phase touch different files (mostly test files) and can run in parallel.

## MVP scope

**User Story 1 alone** delivers the headline value: on a governed workspace the operator runs one
command with no manifest and gets a correct, declared-topology portal — launchable from any member.
US2 (transparency + no-invention guarantees) and US3 (overlay + ungoverned fallback) harden it.
