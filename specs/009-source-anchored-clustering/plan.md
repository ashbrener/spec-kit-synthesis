# Implementation Plan: Source-Anchored Capability Clustering

**Branch**: `009-source-anchored-clustering` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-source-anchored-clustering/spec.md`

## Summary

Replace the clustering engine's membership model (`skill/scripts/cluster.py`) from **connected-component union-find** to **source-anchored, typed, bounded multi-membership propagation**. Today a capability is a connected component of the strong-edge graph, so a build artifact that relates to two source features bridges them and the transitive closure collapses everything into one mega-cluster (Q1); ADRs/dirs with no strong spec-edge fall out as singletons (Q2). The new model anchors one capability per source feature, never merges anchors, and lets build/code/ADR units *attach* (possibly to several capabilities) via a typed one-hop rule in which ADRs and code are membership sinks. This eliminates both pathologies while preserving determinism, stdlib-only purity, fail-closed honesty, and reviewable evidence.

## Technical Context

**Language/Version**: Python ≥3.11

**Primary Dependencies**: pydantic (only runtime dep); stdlib otherwise. No new dependency (FR-009).

**Storage**: N/A — pure function over in-memory `FragmentCorpus` + `LinkGraph`; the IR is a per-run build cache.

**Testing**: pytest (`uv run pytest skill/tests -q`).

**Target Platform**: CLI / in-session reader pipeline (cross-platform Python).

**Project Type**: Library (the synthesis reader engine) + its skill/command surface.

**Performance Goals**: Deterministic, linear-ish in fragments/edges; workspaces are small (≤ a few thousand fragments). No perf concern beyond avoiding accidental O(n²) blowups.

**Constraints**: Pure + deterministic (byte-identical `ClusterSet` for identical inputs; no clock/rng/iteration-order nondeterminism). Stdlib only, no external graph system/DB/embeddings. Fail-closed: no fabricated membership. Weak `references` relation never confers membership. Additive schema only.

**Scale/Scope**: One module rewrite (`cluster.py` membership core) + its tests (`test_cluster.py`) + verification that downstream meld/render consumers (`synthesize_atlas.py`, `build_status`, `source_index`, render) tolerate multi-membership.

## Constitution Check

*GATE: must pass before Phase 0; re-checked after Phase 1.*

| Principle | Status | How this feature complies |
|---|---|---|
| I. Faithfulness is architectural | ✅ | Membership only ever rests on a real typed edge or same-feature grouping; every non-anchor placement carries an evidence note. No edge → no membership. |
| II. Organized by architecture, not spec history | ✅ | Clusters are capabilities anchored to source features; naming/theming stays the agent's job. No spec numbers enter prose. |
| III. Current-state only | ✅ | Membership reflects the current link graph; nothing historical introduced. |
| IV. Fail-closed on gaps | ✅ | A unit with no qualifying tie stays an honest standalone `decision`/`background` cluster or unclustered — never force-attached (FR-005, FR-010). |
| V. Stateless; generated not authored | ✅ | Pure function of (corpora, link graph, source_origins); regenerated every run. |
| VI. General reader | N/A (engine) | Improves the index's readability indirectly (real capabilities, not a blob or noise). |
| Arch: source-agnostic core | ✅ | Operates on the typed `LinkGraph` + `FragmentCorpus`; no source-kind knowledge added. |
| Arch: reasoning vs determinism | ✅ | Membership is deterministic Python; naming remains the agent's reasoning phase. |
| Arch: toolchain `uv`, pydantic-only | ✅ | No new dependency; stdlib union/propagation. |
| Quality gates | ✅ | `verify_links.py` unaffected (it grades edges, not clusters); `pytest` green before push; gates never edited to pass. |

**Result: PASS.** No violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/009-source-anchored-clustering/
├── plan.md              # This file
├── research.md          # Phase 0 — algorithm decision + alternatives
├── data-model.md        # Phase 1 — feature units, capabilities, membership rules
├── quickstart.md        # Phase 1 — how to run + verify
├── contracts/
│   └── cluster_contract.md   # build_clusters() public contract + invariants
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
skill/
├── scripts/
│   ├── cluster.py            # PRIMARY — membership model rewrite (build_clusters, _UF retired/retained for orphans)
│   ├── schema.py             # CapabilityCluster / ClusterSet — additive only (no breaking change)
│   ├── synthesize_atlas.py   # meld consumer — verify multi-membership tolerated
│   ├── build_status.py       # built/partial/planned — verify per-cluster status still correct
│   └── source_index.py       # hierarchical index — verify shared members render sanely
└── tests/
    ├── test_cluster.py       # PRIMARY — rewrite/extend: anchors-stay-separate, multi-membership, ADR sink, determinism
    ├── test_atlas_meld.py    # regression — meld over multi-membership clusters
    └── test_render_meld.py   # regression — render tolerates a fragment in >1 section
```

**Structure Decision**: Single-library layout (the existing `skill/scripts` engine). The change is concentrated in `cluster.py`; everything else is regression verification that multi-membership is tolerated downstream.

## Phase 0 — Research

See [research.md](./research.md). Resolves the algorithm choice (typed bounded propagation vs. alternatives), the anchor/sink rules, orphan handling, and the determinism strategy. No NEEDS CLARIFICATION remain (the membership-model fork was resolved with the user: multi-membership).

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — feature units, the anchor set, the typed propagation rules, classification, ordering, and schema (additive) deltas.
- [contracts/cluster_contract.md](./contracts/cluster_contract.md) — `build_clusters()` signature, invariants (anchors 1:1, multi-membership, ADR/code sinks, determinism, evidence, fail-closed), and the downstream tolerance contract.
- [quickstart.md](./quickstart.md) — regenerate + verify, including the determinism and anti-over-merge checks.
- Agent context: update the plan pointer in `CLAUDE.md` (SPECKIT markers) to this plan.

## Complexity Tracking

No constitution violations — section intentionally empty.
