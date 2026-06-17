# Tasks: Read the governed citation slots as typed edges

**Feature**: `008-read-citation-slots` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Test-first. Neutral examples only (`CORE`/`API`/`WEB`) — no real consumer/company/namespace names
(FR-012, SC-007).

## Phase 1: Setup

- [~] T001 [P] (deferred — synthetic in-test corpora with real front-matter cover this) Create `skill/tests/fixtures/slots/` — a source repo `core` with `.spec-arch-domain.yml`
  (members core/api) + `.spec-arch-governance.yml` (specs_dir, adr_dir, namespace CORE), a source
  feature `001-auth` whose `spec.md` body does NOT contain the string "001-auth", and an ADR
  `ADR-001`; a build repo `api` (sources→core) whose `specs/007-auth/spec.md` front-matter declares
  `derived_from: [core:001-auth]` and whose `plan.md` front-matter declares `cites: [CORE-ADR-001]`.
  Neutral names only.

## Phase 2: Foundational (vendor + config; blocks US1)

- [X] T002 Re-pin `skill/scripts/vendor/vocabulary.json` from 0.2.0 to **0.3.0**, copied verbatim from
  the published contract (includes the `citation_slots` block). Update `skill/scripts/vendor/README.md`
  to note the new pinned tag.
- [X] T003 Update `skill/tests/test_contract_conformance.py`: assert vendored `version == "0.3.0"`,
  and assert the `citation_slots` shape (slots → files/locations; the `derived_from`/`cites` grammars;
  the configurable-keys defaults `source_specs→derived_from`, `adrs→cites`).
- [X] T004 In `skill/scripts/gov_config.py` add `RepoConfig.citation_keys: dict[str,str] = {}` (a
  repo's optional override of the slot key names); keep `extra="ignore"`.
- [X] T005 [P] Tests `skill/tests/test_gov_config.py`: `citation_keys` parses from a repo config;
  absent → `{}`.

## Phase 3: User Story 1 — declared derivation melds the capability (Priority: P1) 🎯 MVP

**Goal**: a build spec's `derived_from: [src:feat]` slot melds it with the source feature even when the
slug is absent from the source's prose. **Independent test**: on the slots fixture, a `derived_from`
edge (build→source feature) exists and the two cluster together; the source body lacks the slug.

- [X] T006 [US1] In `skill/scripts/discover_links.py` add `discover_slot_edges(manifest, corpora,
  namespaces, citation_keys) -> (edges, unresolved)`: parse the `derived_from` slot from each feature's
  `spec.md` front-matter (configured key or default), resolve `<src-member-id>:<feat>` (cross-repo) or
  bare `<feat>` (intra-repo) to a deterministic feature representative (min fragment id), and emit a
  `derived_from` `LinkEdge` graded `declared` (evidence = the raw slot value). Unresolved values →
  no edge, collected in `unresolved`. Include a front-matter parser (pyyaml) + a locator→feature map.
- [X] T007 [US1] In `skill/scripts/discover_links.py` `build_link_graph`: accept `citation_keys`; merge
  `discover_slot_edges` **first**; keep the locator-precise `_key`; add a feature-pair suppression that
  skips a lower-tier edge whose `(src-feature, dst-feature, rel)` is already covered by a declared slot
  edge.
- [X] T008 [US1] In `skill/scripts/synthesize_atlas.py`: gather per-member `citation_keys` (via
  `gov_config`, alongside the existing `namespaces`) and pass to `build_link_graph`.
- [X] T009 [P] [US1] Tests `skill/tests/test_slot_edges.py` (derived_from): a cross-repo
  `derived_from` slot whose target slug is absent from the source prose still yields a `declared`
  `derived_from` edge build→source feature, and the two land in the same cluster (`cluster.build_clusters`);
  a bare value resolves intra-repo (SC-001).

## Phase 4: User Story 2 — declared citations attach decisions (Priority: P2)

**Goal**: a plan's `cites: [<NS>-ADR-NNN]` slot emits a `cites` edge to the decision. **Independent
test**: the fixture plan's cites slot yields a `cites` edge to the source ADR.

- [X] T010 [US2] Extend `discover_slot_edges` to parse the `cites` slot from `plan.md` front-matter
  (configured key or default), resolving a qualified `<NS>-ADR-NNN` (cross-repo) or bare `ADR-NNN`
  (qualified under the citing repo's namespace, reusing spec-004 qualification) to the ADR fragment,
  emitting a `declared` `cites` edge.
- [X] T011 [P] [US2] Tests `skill/tests/test_slot_edges.py` (cites): a cross-repo `cites` slot yields a
  `cites` edge to the source decision; a bare value resolves under the citing namespace (SC-002).

## Phase 5: User Story 3 — conformance, trust, no regression (Priority: P3)

**Goal**: pinned contract, declared-tier dedup, no fabrication, no-slot parity. **Independent test**:
unresolved slot → no edge (noted); slot vs identifier for one pair → one declared edge; no-slot graph
unchanged.

- [X] T012 [P] [US3] Tests `skill/tests/test_slot_edges.py` (trust/regression): an unresolvable slot
  target mints no edge and appears in `unresolved`; a slot edge + an incidental identifier edge for the
  same feature pair collapse to one edge at the `declared` tier; a workspace with no slots produces a
  link graph byte-identical to the pre-feature discovery (SC-002/003/005); `discover_slot_edges` is
  reproducible (SC-006).

## Phase 6: Polish & cross-cutting

- [X] T013 [P] Update `README.md` + `CHANGELOG.md`: synthesis reads the governed citation slots
  (derived_from/cites) as declared-tier typed edges; conforms to vocabulary.json@0.3.0. Neutral examples.
- [X] T014 Run `uv run pytest skill/tests -q` (all green); confirm the single-repo storybook + a
  no-slot workspace are unchanged; confirm no real consumer/company/namespace names (SC-007). The drift
  guard now pins 0.3.0.

## Dependencies & order

- Setup (T001) → Foundational vendor+config (T002–T005) → US1 derived_from (T006–T009) → US2 cites
  (T010–T011) → US3 trust/regression (T012) → Polish (T013–T014).
- **US1 is the MVP** (derived_from melding — the dogfood-#2 unblock). US2 (cites) extends the same
  function; US3 hardens trust + non-regression.
- `[P]` tasks touch different files (tests/fixtures) and can run in parallel.

## MVP scope

**User Story 1 alone** closes the loop: a governed build spec that *declares* its derivation finally
melds with the source feature in the reader — the edge gov produces and synthesis was blind to.
