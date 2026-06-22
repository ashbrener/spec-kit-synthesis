# Phase 1 Data Model: Source-Anchored Capability Clustering

The engine stays a pure function over the existing IR. No new pydantic models are required; one optional additive field is allowed for clarity. The "model" here is the in-process membership computation.

## Entities (in-process)

### Feature unit
The unit of clustering. Derived from the corpora, not persisted.

- **key**: `(origin, feature_key)`; a fragment with no `feature_key` forms a singleton unit keyed `(origin, "#<fragment-id>")`.
- **fragments**: the fragment ids belonging to the unit.
- **role**: `source` | `build` (from the unit's origin role).
- **shape**: `spec` | `code` | `adr` | `other` — derived from the unit's fragment kinds (`adr` if it is an ADR unit; `code` if code/code-symbol; `spec` if spec/plan/tasks/data-model/contract/research; else `other`). Used to apply the typed rules and the existing classification.

### Anchor
A feature unit with `role == source` and a real `feature_key`. Seeds exactly one capability. **Anchors are never added as members of another capability.**

### Typed strong edge (unit-level)
Induced from `LinkGraph` strong edges (`derived_from`/`cites`/`implements`) by mapping each endpoint locator to its owning unit. The weak `references` relation is excluded (over-merge guard, FR-003). Carries `(rel, src_unit, dst_unit, evidence_note)`.

## Membership rules (the fixpoint)

For each anchor `S`, capability `C(S)` starts as `{S}` and grows to a fixpoint. A unit `U` is added to `C(S)` only if `U` is **not an anchor** and one of:

| Rule | Condition (some member `m ∈ C(S)`) | Adds | Direction note |
|---|---|---|---|
| R1 derived_from | `derived_from(U → m)`, `m.shape ∈ {spec}` (incl. the source seed) | build-spec unit `U` | derivation lineage; chains allowed |
| R2 implements | `implements(U → m)`, `m.shape == spec` | code unit `U` | implementation of a member spec |
| R3 cites | `cites(m → U)`, `m.shape == spec`, `U.shape == adr` | ADR unit `U` | decision a member spec/plan cites |

**Sinks:** the fixpoint never expands *from* a unit whose `shape ∈ {adr, code}` — they are attached (R2/R3) but contribute no outgoing propagation. This is the property that prevents the shared-ADR / shared-code bridge.

Every add records an `evidence_note` (e.g. `be:002-auth-api derived_from docs:002-architecture`). Determinism: members and edges are processed in sorted order; the fixpoint converges because membership only grows and is bounded by the unit set.

## Orphans, decisions, background

After all anchors are resolved, any unit in **no** `C(S)`:

- **uncited ADR / lone decision unit** → its own `decision` cluster (seed `None`).
- **build feature with no source tie** → its own orphan `capability` cluster (seed `None`); orphan units may union among themselves over strong edges **excluding ADR-as-bridge**, so the remainder cannot re-collapse.
- **free-form narrative with no feature_key and no strong edge** → `background` cluster or `unclustered` (a lone, feature-less, edge-less fragment), exactly as today.

## Classification & ordering (unchanged contract, spec 007)

- `_classify` stays: a cluster with a spec/code member → `capability`; only ADRs → `decision`; only narrative → `background`.
- Order stays deterministic: kind rank (`capability` < `decision` < `background`), then source-seeded before orphans, then by id.

## Schema (`skill/scripts/schema.py`) — additive only

`CapabilityCluster` and `ClusterSet` are unchanged in shape. A fragment id MAY now appear in the `members` of more than one cluster (multi-membership) — this was always representable; the change is that the builder no longer guarantees a partition.

- `CapabilityCluster.seed` — unchanged (anchor feature_key, `None` for orphans).
- `CapabilityCluster.members` — unchanged `dict[origin → list[fid]]`; same fid may recur across clusters.
- `CapabilityCluster.evidence` — unchanged `list[str]`; now records the typed placement notes.
- *(optional, additive)* `CapabilityCluster.shared: bool = False` — convenience flag set when any member also appears in another cluster, to let render/meld key off it without recomputation. Include only if a downstream consumer needs it; default keeps golden output stable for single-membership clusters.

## Invariants (assert in tests)

1. **Anchors 1:1** — each source feature anchors exactly one `capability` cluster; no cluster contains fragments anchored to two different source features (SC-002).
2. **Anti-over-merge** — adding a build unit that relates to two anchors does not reduce the capability count (the two anchors stay separate; the unit is in both).
3. **ADR sink** — two specs in different capabilities citing the same ADR do not become co-members; the ADR is a member of both capabilities, but neither spec leaks into the other's capability.
4. **No singleton for cited ADRs** — an ADR cited by a capability's spec is a member of that capability, not a standalone `decision`.
5. **Honest standalones** — an uncited ADR / untied narrative remains its own `decision`/`background`/unclustered.
6. **Evidence** — every non-anchor membership has an evidence note.
7. **Determinism** — identical inputs → byte-identical serialized `ClusterSet`.
8. **Weak-relation guard** — a `references`-only link never confers membership.
