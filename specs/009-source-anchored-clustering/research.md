# Phase 0 Research: Source-Anchored Capability Clustering

## Problem restated

`build_clusters` (spec 006/007) defines a capability as a **connected component** of union-find over strong cross-repo edges (`derived_from`/`cites`/`implements`) plus same-feature grouping. Two failure modes on a densely cross-cited docs-authority workspace:

- **Over-merge (Q1):** union-find *merges* any two roots joined by a strong edge. A build artifact relating to two source features bridges them; the bridge is transitive, so the whole graph collapses to one cluster (~495 fragments observed).
- **Fragmentation (Q2):** ADRs / dir-keyed fragments with no strong spec-edge stay as lone components → one cluster per ADR/dir.

The two are the same root cause: **"capability = connected component" couples separability to graph connectivity**, which a single shared neighbour destroys.

## Decision: typed, bounded, multi-membership propagation anchored at source features

A capability is **anchored at exactly one source feature** and never merged with another anchor. Membership is computed by a **typed one-hop fixpoint**, not free graph reachability:

Work over **feature units** = `(origin, feature_key)` with their fragment sets (a fragment with no `feature_key`, e.g. a code symbol, is its own singleton unit). Edges between units are induced from the strong-edge `LinkGraph`.

- **Anchors** = units whose origin is a *source* role and that carry a `feature_key` (a real source feature). Each anchor seeds one capability with its own fragments.
- **Propagation rules** (applied to each capability `C` anchored at `S`, to a fixpoint; a unit `U` is added only if `U` is **not itself an anchor**):
  1. **derived_from** `B → m` where `m ∈ C` is a spec/source unit ⟹ add build-spec unit `B` (derivation lineage; chains allowed).
  2. **implements** `K → m` where `m ∈ C` is a spec unit ⟹ add code unit `K`.
  3. **cites** `m → A` where `m ∈ C` is a spec/plan unit ⟹ add ADR unit `A`.
- **Sinks:** ADRs and code are **membership sinks** — they are *attached* (rules 2/3) but the fixpoint **never traverses outward from** an ADR or a code unit. This is the single property that kills both pathologies:
  - the **shared-ADR bridge** can't form (we never go ADR → other citer),
  - a **cited ADR** is no longer a singleton (rule 3 attaches it to its capability).
- **Multi-membership:** because each anchor computes its own membership independently and anchors are never added to one another, a unit reachable from several anchors is a member of **each** — separability is preserved while honest cross-cutting is shown.
- **Orphans:** any unit not placed in any source capability is emitted honestly — an orphan capability (build feature with no source tie), a standalone `decision` (uncited ADR), or `background`/`unclustered` (free-form narrative). Orphans are grouped by their own feature unit (same-feature fragments together) and a restricted strong-edge link among non-source units **excluding ADR-as-bridge**, so the orphan remainder cannot re-introduce over-merge.

### Why this is correct (worked cases)

| Case | Old (component) | New (typed propagation) |
|---|---|---|
| `B derived_from S1` and `B derived_from S2` | S1+S2+B fuse into one cluster | `B ∈ cap(S1)` and `B ∈ cap(S2)`; S1, S2 stay separate |
| `B1 cites ADR-X`, `B2 cites ADR-X` (B1∈S1, B2∈S2) | S1+S2 fuse via ADR-X | `ADR-X ∈ cap(S1)` and `∈ cap(S2)`; B2 ∉ cap(S1) (ADR is a sink) |
| `K implements B`, `B derived_from S` | all in one component (fine) | `K, B ∈ cap(S)` via rules 1→2 (the melded source→spec→code chain) |
| ADR cited by nobody | own singleton `decision` | own singleton `decision` (honest, unchanged) |
| Build feature with no source edge | own component | own orphan capability (honest) |

## Rationale

- **Encodes the melded grammar directly.** The story is *source ⟵derived_from⟵ spec ⟵implements⟵ code*, and *spec/plan ⟶cites⟶ decision*. Typed propagation is that grammar; component union-find is a blunt proxy that overshoots.
- **Separability is a property of anchors, not connectivity.** Making anchors un-mergeable is what guarantees N source features → ~N capabilities regardless of cross-citation density (SC-001/002).
- **Honest by construction.** Every placement is one typed edge from an existing member → trivially evidence-backed (FR-007) and fail-closed (FR-010). No new trust surface.
- **Cheap + deterministic.** Membership grows monotonically to a fixpoint over a small unit graph; sorted iteration ⟹ byte-identical output (FR-008). Pure stdlib (FR-009).

## Alternatives considered

- **Community detection (Louvain / label propagation).** Rejected: needs tuning, risks nondeterminism, and reads as an "external graph algorithm" against the spec-006 FR-006 decision; also opaque (hard to give per-membership evidence).
- **Single-primary assignment** (each fragment in exactly one capability via a tie-break). Rejected by the user in clarify: a genuinely cross-cutting artifact would vanish from every capability but one, making the others look thinner than they are. Multi-membership is the faithful choice.
- **Keep union-find but exclude `cites` from merging.** Rejected: removes the ADR-bridge but not the `derived_from`/`implements` bridges; a build spec deriving from two sources still fuses them. Doesn't solve Q1 generally.
- **Cap cluster size / split largest component heuristically.** Rejected: arbitrary, nondeterministic-feeling, and destroys faithful membership; treats the symptom.

## Determinism strategy

- Sort origins, units, fragment ids, and edges before iteration.
- Fixpoint via a worklist seeded in sorted order; membership sets are sorted on emit.
- Multi-membership means a fragment id may appear in multiple clusters — clusters are still emitted in the existing deterministic order (kind rank, then source-seeded before orphans, then id).
- No `Date`/random/set-iteration leakage (matches the rest of the engine).

## Downstream impact (to verify, not redesign)

- **schema:** `CapabilityCluster`/`ClusterSet` need no breaking change; a fragment in multiple clusters is already representable. Add evidence notes per placement (already a list field). Any addition is additive.
- **meld (`synthesize_atlas`)** and **render:** must tolerate the same fragment id surfacing under more than one capability. Source *content* stays bundled once (one source page) and is cited from each capability (FR-011) — render already drills chips to a single bundled source page, so no body duplication. Confirm with regression tests; adjust only if a hidden disjointness assumption surfaces.
