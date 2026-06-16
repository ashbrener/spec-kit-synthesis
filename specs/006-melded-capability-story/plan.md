# Implementation Plan: Melded capability story (the SITE layer, re-architected)

**Branch**: `006-melded-capability-story` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-melded-capability-story/spec.md`

## Summary

Replace the book-of-books SITE layer with ONE melded, capability-organized story. The key leverage:
the meld **reuses the existing `DocumentModel` + `render.py` page engine** — the atlas produces a
single melded `DocumentModel` (sections = capabilities) instead of N per-member ones. Three small
schema additions (`Block.tier`, `Block.build_status`, `Section.build_status`, two diagram layouts)
carry the new information; the renderer groups technical blocks by tier into per-tier disclosures,
fades planned work, renders a nested nav and human-titled source tables. Two new deterministic
modules — `cluster.py` (capability clustering over the existing typed link graph) and
`build_status.py` (built/partial/planned from coverage + lifecycle) — plus a deterministic
hierarchical index replace the graph atlas. No external graph system, no new runtime dependency; the
fail-closed gates (`verify.py` / `verify_links.py`) are unchanged.

## Technical Context

**Language/Version**: Python ≥3.11 (stdlib only for the new logic; `pydantic` + `pyyaml` already present).

**Primary Dependencies**: `pydantic` (IR + validation) — **no new dependency** (clustering is stdlib
union-find; FR-006).

**Storage**: Filesystem build cache (`--work`) + rendered site (`--out`); read-only on sources.

**Testing**: `pytest` (`uv run pytest skill/tests -q`).

**Target Platform**: the `speckit.synthesis.atlas` command (CLI + the in-session agent as engine).

**Project Type**: Single project (`skill/scripts`, `skill/tests`).

**Performance Goals**: Deterministic stages negligible; the meld adds code ingestion + clustering
(O(edges) union-find) — sub-second at workspace scale.

**Constraints**: no external graph/knowledge-graph/db; no new runtime dep; gates unchanged; PAGE-layer
unchanged; single self-contained HTML page output; neutral examples only (CORE/API/WEB).

**Scale/Scope**: a few–dozen repos, scores of features, hundreds of edges; one melded page.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Note |
|---|---|---|
| I. Faithfulness is architectural | ✅ | Every melded claim resolves against the merged corpus; `verify.py` runs unchanged over the melded `DocumentModel`; clustering only groups real fragments — it asserts no claims. |
| II. Organized by architecture, not spec history | ✅ **Strengthens** | The meld is *the* realization of "organized by architecture" — capabilities, not spec/repos. Spec ids stay in citation chips only. |
| III. Current-state only | ✅ | Build-status surfaces built vs planned as current fact, not a changelog; supersession unchanged. |
| IV. Fail-closed on gaps | ✅ | Unclustered fragments surfaced honestly (FR-015); missing tiers shown as absent, not fabricated; conflicting build signals → `partial`, not a silent pick. |
| V. Stateless; generated, never authored | ✅ | Clusters, build-status, index all regenerated each run; reproducible (SC-006). |
| Source-agnostic core | ✅ | Reuses adapters + DocumentModel; clustering consumes the existing link graph. |
| Reasoning vs determinism split | ✅ | Clustering/build-status/index/titles are deterministic; the agent only names themes + writes prose, gated by verify. |
| Toolchain uv / pydantic / ≥3.11 | ✅ | No new deps. |
| Quality gates | ✅ | `verify.py` + `verify_links.py` unchanged; `pytest` green before push. |

**No violations.** Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/006-melded-capability-story/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/meld-contract.md
├── checklists/requirements.md
└── tasks.md   (/speckit-tasks)
```

### Source Code (repository root)

```text
skill/scripts/
├── cluster.py            # NEW — deterministic capability clustering over the typed link graph
├── build_status.py       # NEW — built/partial/planned per (capability, tier) from coverage + lifecycle
├── source_index.py       # NEW — human titles + the hierarchical source-index tree (deterministic)
├── schema.py             # CHANGED — Block.tier, Block.build_status, Section.build_status; 2 diagram layouts
├── render.py             # CHANGED — per-tier disclosures, build-status fading, nested nav, source TABLE,
│                         #            _layout_sequence + _layout_erd, a _TITLES resolver seam
├── synthesize_atlas.py   # CHANGED — meld build: cluster → (agent meld) → verify → render ONE page +
│                         #            hierarchical index; drop per-member pages + render_atlas
├── discover_links.py     # (reused — the graph clustering consumes)
├── render_sources.py     # (reused — drill-to-source; index links into it)
└── verify.py / verify_links.py   # UNCHANGED (gates)

commands/atlas.md         # CHANGED — the melded reasoning contract (cluster briefs → one woven doc)
skill/tests/
├── test_cluster.py · test_build_status.py · test_source_index.py
├── test_render_meld.py   # per-tier disclosure, fading, nested nav, source table, new layouts
├── test_atlas_meld.py    # end-to-end meld over a fixture (hand-authored melded document_model)
└── fixtures/governed_ws/ # CHANGED — add build-repo code + a melded document_model fixture
```

**Structure Decision**: Single project, existing layout. The meld is additive deterministic modules +
targeted edits to schema/render/synthesize_atlas; the PAGE engine and gates are untouched.

## Architecture (the decided design)

1. **Cluster (`cluster.py`, deterministic).** Build capability clusters by union-find over the link
   graph: seed one cluster per **source-repo feature**; attach a build feature to the source feature
   it `derived_from` / shares a qualified ADR `cites` with; fall back to shared `FR-NNN` / feature-slug
   when edges are sparse; orphans become their own cluster. Output `CapabilityCluster` records
   (members grouped by origin/tier + the evidence). Reproducible ordering. Membership only — names no
   capability.

2. **Build status (`build_status.py`, deterministic).** Per cluster and per tier, grade
   `built/partial/planned` from BOTH: code **coverage** (build-repo `code` fragments implementing the
   tier's specs → built) and **lifecycle** (artifact presence + `tasks.md` checkbox ratio). Conflict →
   `partial` with the reason recorded. Absent code → lifecycle-only with lower confidence.

3. **Agent meld (gated reasoning).** Stage 0 emits, per cluster, a brief (its fragments by tier +
   build-status + locators). The agent writes ONE melded `DocumentModel`: one `Section` per capability
   (named — the only semantic step), functional blocks (tier=None) inline, technical blocks tagged
   `tier` (e.g. "backend"/"frontend") and `build_status`, diagram-forward. `verify.py` validates it
   against the merged corpus unchanged.

4. **Schema (minimal, additive).** `Block.tier: Optional[str]`, `Block.build_status:
   Optional[Literal["built","partial","planned"]]`, `Section.build_status: Optional[...]`;
   `DiagramGraph.layout` gains `"sequence"` (cross-tier request path) and `"erd"` (data model). All
   optional → existing fixtures/tests unaffected.

5. **Render (`render.py`).** `_render_section` groups technical blocks **by tier** into one
   `<details>` per tier (label = tier title, carrying its build-status), functional inline; a
   section build-status badge by the heading; planned blocks/tiers rendered **faded** with a marker
   (CSS only, print/reduced-motion safe). `_source_line` → a **sources table** ([Title | Artifact |
   Repo | →]) via a deterministic `_TITLES` resolver (locator → human title/kind/repo, like the
   existing `_RESOLVE` seam). `_render_nav` → **nested** (capability → its tiers). Add
   `_layout_sequence` + `_layout_erd` to `_LAYOUTS`.

6. **Hierarchical index (`source_index.py`, deterministic).** From the corpora: a tree repo → feature
   (human title from spec H1/frontmatter) → artifacts (spec/plan/tasks/contract/data-model + cited
   ADRs), each linking to drill-to-source. Rendered as the portal's reference surface, **replacing**
   `render_atlas`.

7. **`synthesize_atlas` meld build.** Stage 0 adapts members **including build-repo code** (the meld
   needs coverage), clusters, computes build-status, writes per-cluster briefs + merged corpus +
   titles + the deterministic index. Finish: `verify_links` (cross-repo edges) + `verify.py` (melded
   doc vs merged corpus), then render the single melded page + the hierarchical index + drill-to-source.
   The per-member storybook pages and the edge-list `atlas.html` are **removed**.

## Phase 0 / 1

- [research.md](./research.md) — clustering algorithm choice (union-find, no lib), build-status signal
  fusion, single-page reuse of DocumentModel, the two new diagram layouts, why no external graph.
- [data-model.md](./data-model.md) — `CapabilityCluster`, `TierGroup`, `BuildStatus`, the schema deltas,
  `SourceIndexNode`, the titles map.
- [contracts/meld-contract.md](./contracts/meld-contract.md) — what the meld guarantees (one story,
  woven tiers, deterministic clusters, build-status honesty, human-titled sources, hierarchical index,
  gates unchanged).
- [quickstart.md](./quickstart.md) — the one-command meld and what the reader gets.

## Complexity Tracking

No constitution violations — table intentionally empty.
