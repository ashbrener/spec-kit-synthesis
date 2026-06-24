# Implementation Plan: Contract-Driven Capability Clustering

**Branch**: `010-contract-driven-clustering` | **Date**: 2026-06-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-contract-driven-clustering/spec.md`

## Summary

Make clustering a faithful projection of the **declared** governance graph. Three changes, all in the deterministic reader engine:

1. **R1 — gate membership by evidence tier (`cluster.py`).** Only `declared` edges + same-feature grouping confer capability membership; an `identifier` edge confers membership **only for a source↔build pair**, never build↔build; `prose` never. This removes the spurious build↔build chaining that produced the near-duplicate catch-alls.
2. **R3 — ingest only source-of-truth (`adapter_doc.py`).** Extend the deterministic skip-set to exclude archive/audit directories and well-known agent/process meta files so they form no fragments/clusters (folds in Q3).
3. **FR-004 — faithful hub flag (`schema.py` + `cluster.py`).** Do not demote/split hubs; render the declared grain and add an **additive** "broad (hub)" annotation (count of distinct features declaring the anchor) as a governance signal.

The cross-tier naming grain (Auth/Authz/…) is explicitly governance's, not solved here (FR-006).

## Technical Context

**Language/Version**: Python ≥3.11 · **Primary Dependencies**: pydantic (only runtime dep), stdlib · **Storage**: N/A (pure function over in-memory IR) · **Testing**: pytest (`uv run pytest skill/tests -q`) · **Project Type**: library (the reader engine) · **Determinism**: byte-identical `ClusterSet` for identical inputs · **Constraints**: stdlib only, no external graph/DB/embeddings; fail-closed; additive schema.

## Constitution Check

| Principle | Status | How |
|---|---|---|
| I. Faithfulness (NON-NEGOTIABLE) | ✅ | Membership rests only on `declared` + same-feature (+ source↔build identifier); inferred noise no longer places fragments; hubs rendered as declared, never re-shaped. |
| II. Organized by architecture | ✅ | Capabilities still anchored to features; no spec numbers in prose. |
| III. Current-state only | ✅ | No historical content introduced. |
| IV. Fail-closed on gaps | ✅ | Coarse declared grain → faithfully coarse + flagged; never invented. |
| V. Stateless; generated | ✅ | Pure function of (corpora, link graph, source_origins). |
| Arch: source-agnostic core | ✅ | Operates on typed graph + corpora; R3 is an adapter-level ingestion rule. |
| Arch: reasoning vs determinism | ✅ | All deterministic; agent still names only. |
| Arch: uv / pydantic-only | ✅ | No new dependency. |
| Quality gates | ✅ | `verify*`/gates untouched; pytest green before push. |

**Result: PASS** — and this feature *strengthens* Principle I (it removes the only place inferred evidence was silently conferring membership). No Complexity Tracking needed.

## Project Structure

```text
specs/010-contract-driven-clustering/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/clustering_contract.md
└── tasks.md   (/speckit-tasks)

skill/scripts/
├── cluster.py        # R1 evidence-tier gating + FR-004 hub flag
├── schema.py         # additive: CapabilityCluster hub annotation
└── adapter_doc.py    # R3 default meta/archive skip-set
skill/tests/
├── test_cluster.py        # R1 + FR-004 (membership gating, hub flag)
└── test_adapter_doc.py    # R3 (meta/archive excluded)
```

**Structure Decision**: Single-library engine; changes localised to `cluster.py` (membership), `adapter_doc.py` (ingestion), `schema.py` (additive field). Render/meld consumers unchanged (multi-membership already tolerated).

## Phase 0 — Research

See [research.md](./research.md). No open NEEDS CLARIFICATION — both design decisions resolved (faithful, best-practice): evidence-tier gating with source↔build identifier admission; strictly-faithful hub flagging (no demotion).

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — the evidence-tier gate, the hub annotation, the ingestion skip-set, invariants.
- [contracts/clustering_contract.md](./contracts/clustering_contract.md) — `build_clusters()` membership guarantees (declared-driven), the hub-flag contract, the ingestion contract.
- [quickstart.md](./quickstart.md) — verify + the three acceptance checks.
- Agent context: point `CLAUDE.md` SPECKIT markers at this plan.

## Complexity Tracking

No violations — section intentionally empty.
