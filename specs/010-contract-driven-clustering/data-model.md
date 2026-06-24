# Phase 1 Data Model: Contract-Driven Capability Clustering

Pure function over the existing IR; one additive schema field. No new models.

## The evidence-tier membership gate (R1, `cluster.py`)

When lifting `LinkGraph` edges to unit-level strong edges, gate each edge by its `evidence_kind` and endpoint roles before it can confer membership:

| evidence_kind | confers membership? |
|---|---|
| `declared` | always (trusted governed slot) |
| `identifier` | only if **exactly one** endpoint origin is a source (source↔build); never build↔build, never source↔source |
| `prose` | never |

Same-feature grouping (fragments sharing `origin + feature_key`) confers membership unconditionally (structural, not edge-derived) — unchanged.

`LinkEdge` already carries `evidence_kind: LinkEvidenceKind` (`declared`/`identifier`/`prose`) and origin on each endpoint; `source_origins` is already a parameter of `build_clusters`. So the gate is local to the strong-edge build loop — no new inputs.

The spec-009 typed fixpoint (R1 derived_from, R2 implements, R3 cites, R4 cites-meld) and multi-membership are unchanged; they simply operate over the **gated** edge set.

## Hub annotation (FR-004, additive)

`CapabilityCluster` gains one optional, additive field:

- `hub_dependents: int = 0` — the count of **distinct features** that declare `derived_from` the cluster's anchor feature (0 for orphans/planned/non-hub). A cluster with `hub_dependents >= 2` is "broad (hub)" — a governance signal that the declared grain is coarse. Default 0 keeps existing golden output stable.

Computed deterministically from the declared edge set (in-degree of the anchor over `declared derived_from`). The reader does NOT act on it (no demotion/split); render/meld may surface it later (out of scope here).

## Ingestion skip-set (R3, `adapter_doc.py`)

Extend `_is_skipped(rel, extra)` with deterministic defaults (in addition to hidden dot-dirs + existing `SKIP_DIRS` + caller `extra`):

- **dirs**: any path part whose lowercase name contains `archive` or `audit`.
- **files**: basename (case-insensitive) in {`claude.md`, `agents.md`, `gemini.md`, `resume.md`, `worktrees.md`} or containing `handoff`.

Pure name test; applies at any depth; existing genuine docs/specs/ADRs unaffected.

## Invariants (asserted in tests)

1. **Declared confers; inferred (mostly) does not.** Removing all build↔build identifier and all prose edges leaves `ClusterSet` membership unchanged.
2. **Source↔build identifier still works.** On an un-governed workspace (no declared slots), a source↔build identifier edge still groups the pair.
3. **No build↔build identifier membership.** Two build features joined only by an identifier edge are never co-members.
4. **Hubs faithful + flagged.** A feature declared `derived_from` by N≥2 features renders as the declared capability with `hub_dependents == N`; it is not split or re-anchored.
5. **Leaf/planned anchors.** A declared feature with no dependents anchors its own capability.
6. **Ingestion hygiene.** Archive/audit dirs and agent/handoff/resume/worktrees meta files produce no fragments.
7. **Determinism.** Identical inputs → byte-identical `ClusterSet`.
8. **Classification + ordering preserved** (spec 007); cited-ADR behaviour preserved, restricted to declared `cites`.
