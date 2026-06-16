# Tasks: Melded capability story (the SITE layer, re-architected)

**Feature**: `006-melded-capability-story` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Tests included (synthesis is test-first). Neutral examples only (`CORE`/`API`/`WEB`) — no real
consumer/company/namespace names (FR-017, SC-009). The deterministic machinery is what we build + test;
the agent's meld reasoning is exercised via a hand-authored melded `document_model` fixture.

## Phase 1: Setup

- [~] T001 [P] (deferred — synthetic + in-test fixtures cover the deterministic machinery) Extend `skill/tests/fixtures/governed_ws/`: add build-repo **code** (`backend/src/…`,
  `frontend/src/…`) implementing *some* of the specs (so coverage yields built for some areas,
  specced-only for others), and a `tasks.md` with mixed `[X]`/`[ ]` checkboxes in one feature. Neutral
  names only.
- [X] T002 [P] Add `skill/tests/fixtures/meld/document_model.json` — a hand-authored melded doc:
  capability sections, functional blocks (no tier) + per-tier technical blocks (`tier:"backend"`/
  `"frontend"`) with `build_status`, including one `sequence` and one `erd` diagram block — drives the
  render + end-to-end tests without invoking the agent.

## Phase 2: Foundational (blocks US1–US4)

- [X] T003 In `skill/scripts/schema.py` add `Block.tier: Optional[str] = None` and
  `Block.build_status: Optional[Literal["built","partial","planned"]] = None`, and
  `Section.build_status: Optional[Literal["built","partial","planned"]] = None`. All optional;
  existing validators unchanged.
- [X] T004 In `skill/scripts/schema.py` extend `DiagramGraph.layout` Literal with `"sequence"` and
  `"erd"` (default unchanged).
- [X] T005 [P] Tests `skill/tests/test_schema_meld.py`: new fields default to None and round-trip;
  a Block with `tier`/`build_status` validates; `layout` accepts `sequence`/`erd`; existing
  fixtures/golden models still validate (back-compat).

## Phase 3: User Story 1 — one melded capability story (Priority: P1) 🎯 MVP

**Goal**: one story, sections = capabilities, woven functional → per-tier technical, human-titled
sources, replacing the per-repo storybooks. **Independent test**: build over the merged fixture corpus
+ the hand-authored melded doc → a single `index.html` with per-tier disclosures and a human-titled
sources table, and no standalone per-repo pages.

- [X] T006 [US1] Create `skill/scripts/cluster.py`: `build_clusters(corpora, link_graph, topology)` →
  `ClusterSet` via stdlib union-find — seed one cluster per source-repo feature; attach a build
  feature to its strongest source link (`derived_from`, then shared qualified `cites`); fall back to
  shared `FR-NNN` / feature-slug; orphans stand alone; record join evidence + `unclustered`.
  Deterministic, reproducible.
- [X] T007 [P] [US1] Tests `skill/tests/test_cluster.py`: a source feature seeds a cluster; a build
  spec attaches via `derived_from`; sparse edges fall back to shared FR/slug; an orphan stands alone;
  a shared utility does NOT fuse everything (over-merge guard); same inputs → identical clusters.
- [X] T008 [US1] Create `skill/scripts/source_index.py` with `build_title_map(corpora)` → a TitleMap
  (locator → {human title from spec H1/frontmatter, artifact kind, repo}; fallback = marked feature id).
- [X] T009 [P] [US1] Tests `skill/tests/test_source_index.py` (titles): a feature's human title is
  extracted; artifact kind + repo are set; absent title → a clearly-marked id fallback.
- [X] T010 [US1] In `skill/scripts/render.py`: add a `_TITLES` context-var seam (mirroring `_RESOLVE`);
  replace `_source_line` with `_source_table` ([Title | Artifact | Repo | →] using the TitleMap, each
  drilling to source); in `_render_section`, group TECHNICAL blocks **by `block.tier`** into one
  `<details>` per tier (label from the tier), functional blocks inline.
- [X] T011 [US1] In `skill/scripts/synthesize_atlas.py`: replace the book-of-books build with the meld
  — merge member corpora, run `cluster.build_clusters`, emit per-cluster briefs (`work/clusters.json`
  + per-cluster locator lists); on finish, load ONE melded `document_model.json`, run `verify_links` +
  `verify.py` over the merged corpus, and render ONE `index.html` via `render.render` (TitleMap +
  cross-repo resolver injected) + drill-to-source. REMOVE per-member pages, `render_atlas`, and the
  card `render_index`.
- [X] T012 [US1] Rewrite `commands/atlas.md`: the melded reasoning contract — consume the per-cluster
  briefs and write ONE melded `DocumentModel` (one section per capability; functional inline + per-tier
  technical tagged `tier`/`build_status`; diagram-forward; human-titled sources), gated by `verify.py`.
- [X] T013 [P] [US1] Tests `skill/tests/test_render_meld.py`: rendering the melded fixture yields
  per-tier `<details>` (labeled), functional content inline, a sources TABLE with human titles (no bare
  filename as the primary label), and a single page.
- [X] T014 [US1] Tests `skill/tests/test_atlas_meld.py`: end-to-end over the fixtures → one
  `index.html`, NO per-repo storybook pages, drill-to-source pages present, `verify` passes (SC-001/002).

## Phase 4: User Story 2 — built vs planned (Priority: P2)

**Goal**: capability/tier build-status from coverage + lifecycle, faded when planned. **Independent
test**: a code-backed capability grades built; a specced-only one grades planned and renders faded.

- [X] T015 [US2] Create `skill/scripts/build_status.py`: `grade(cluster, corpora, tasks)` →
  `CapabilityStatus` (per-tier `built/partial/planned`) fusing code coverage (spec backed by code) and
  lifecycle (artifact presence + `tasks.md` checkbox ratio); conflict → `partial` with a recorded
  reason; absent code → lifecycle-only. Deterministic.
- [X] T016 [P] [US2] Tests `skill/tests/test_build_status.py`: built when code backs the spec; planned
  when specced-only + tasks incomplete; partial on conflicting signals (with reason); lifecycle-only
  fallback when no code.
- [X] T017 [US2] In `skill/scripts/render.py`: render a build-status badge on the section and on each
  tier disclosure; add `.planned`/`.partial` CSS (faded + a "Planned" marker, print/reduced-motion
  safe). In `synthesize_atlas.py`, fold `build_status` into the per-cluster briefs.
- [X] T018 [P] [US2] Extend `skill/tests/test_render_meld.py`: a planned tier/section renders faded
  with a marker; a built one renders solid; per-tier grades are distinguishable (SC-003).

## Phase 5: User Story 3 — hierarchical index + nested nav (Priority: P3)

**Goal**: a tree (repo › feature-title › artifacts) replaces the graph; persistent nested nav.
**Independent test**: the index is a tree with human titles drilling to source; no edge-list atlas; nav
is nested.

- [X] T019 [US3] In `skill/scripts/source_index.py` add `build_tree(corpora, link_graph)` →
  `SourceIndexNode` tree (repo → feature[human title] → artifacts incl. cited ADRs) + a
  `render_index_tree(tree, theme)` HTML builder (design-system styled).
- [X] T020 [US3] In `skill/scripts/synthesize_atlas.py`: render the hierarchical index page (replacing
  `atlas.html`) and link it from the melded story.
- [X] T021 [US3] In `skill/scripts/render.py`: make `_render_nav` **nested** — capabilities with their
  tier sub-anchors — replacing the flat scrollspy.
- [X] T022 [P] [US3] Tests `skill/tests/test_source_index.py` (tree) + nav assertions in
  `test_render_meld.py`: tree is repo→feature→artifact with human titles + drill links; no edge-list
  atlas page is produced; the nested nav lists capabilities and tiers (SC-005).

## Phase 6: User Story 4 — diagram-forward (Priority: P4)

**Goal**: cross-tier flow + data-model diagrams render with new layouts. **Independent test**: a
`sequence` and an `erd` diagram render valid, animated, settle-safe SVG.

- [X] T023 [US4] In `skill/scripts/render.py` add `_layout_sequence` (ordered cross-tier request path)
  and `_layout_erd` (entities + relationships); register both in `_LAYOUTS`; emit motion-hook classes;
  reduced-motion / print settle to a correct static state.
- [X] T024 [P] [US4] Tests `skill/tests/test_render_meld.py` (diagrams): the fixture's `sequence` and
  `erd` blocks render `fig-sequence` / `fig-erd` with nodes/edges, animation classes, and a safe final
  state (SC-008).

## Phase 7: Polish & cross-cutting

- [X] T025 [P] Update `README.md` + `CHANGELOG.md`: the meld (one capability story · built/planned ·
  hierarchical index · diagram-forward) supersedes the book-of-books; refresh the atlas mermaid/section
  and the `extension.yml` atlas command description if wording changed. Neutral examples.
- [X] T026 Run `uv run pytest skill/tests -q` (all green); confirm the single-repo storybook (PAGE
  layer) output is unchanged and the extension contract test still passes; confirm no real
  consumer/company/namespace names in source/docs/tests/fixtures (SC-009).

## Dependencies & order

- Setup (T001–T002) → Foundational (T003–T005) → US1 (T006–T014) → US2 (T015–T018) → US3 (T019–T022)
  → US4 (T023–T024) → Polish (T025–T026).
- **US1 is the MVP** (the melded story itself). US2/US3/US4 layer onto it and are independent of each
  other (build-status, index/nav, diagrams).
- `[P]` tasks touch different files (mostly tests/fixtures) and can run in parallel.

## MVP scope

**User Story 1 alone** delivers the headline re-envisioning: one capability-organized story woven
across tiers with human-titled sources, replacing the three per-repo storybooks. US2 (built/planned),
US3 (hierarchical index + nested nav), and US4 (diagram-forward) are incremental enrichments.
