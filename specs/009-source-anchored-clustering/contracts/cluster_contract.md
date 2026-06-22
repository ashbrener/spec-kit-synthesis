# Contract: `build_clusters()` — source-anchored multi-membership

The reader's public clustering contract. The signature is unchanged; the **guarantees** change from "partition into connected components" to "source-anchored multi-membership."

## Signature (unchanged)

```python
def build_clusters(
    corpora: dict[str, FragmentCorpus],   # origin -> origin-stamped corpus
    link_graph: LinkGraph,                # typed, evidence-graded edges
    source_origins: set[str],             # origins whose role is "source" (anchors come from here)
) -> ClusterSet: ...
```

Pure + deterministic. Stdlib only. No external graph system / DB / embeddings / new runtime dependency.

## Guarantees

1. **Anchored 1:1.** Every source feature `(origin ∈ source_origins, feature_key)` with content anchors exactly one `capability` cluster (`seed == feature_key`). No cluster mixes fragments anchored to two different source features.
2. **Never merges anchors.** No strong edge between (or transitively across) two anchors fuses them into one cluster — the count of source-anchored capabilities does not collapse as cross-citation density rises.
3. **Multi-membership.** A non-anchor unit (build spec / code / ADR) that legitimately relates to several source capabilities is a member of **each** (a fragment id may appear in more than one cluster's `members`).
4. **Typed one-hop propagation with ADR/code as sinks.** Membership is added only by `derived_from` (add deriving spec), `implements` (add implementing code), `cites` (add cited ADR). The traversal never expands outward from an ADR or code unit. The weak `references` relation never confers membership.
5. **Honest standalones (fail-closed).** A unit with no qualifying tie is emitted as its own `decision` (uncited ADR), orphan `capability` (untied build feature), or `background`/`unclustered` — never force-attached, never fabricated.
6. **Evidence.** Every membership beyond a capability's own anchor feature carries an evidence note naming the relation (and endpoints) that placed it.
7. **Classification & ordering preserved.** `capability`/`decision`/`background` per spec 007; deterministic order (kind rank, source-seeded before orphans, then id).
8. **Determinism.** Identical inputs ⟹ byte-identical serialized `ClusterSet`.

## Downstream tolerance contract

Consumers of `ClusterSet` MUST tolerate a fragment id appearing in more than one cluster:

- **meld (`synthesize_atlas`)**: may surface a shared fragment under each capability it serves; MUST NOT crash or double-count coverage because of overlap.
- **render**: source **content** stays bundled once (one source page per source file) and is cited from each capability — capabilities repeat the *reference*, never the source body (FR-011).
- **build_status / source_index**: per-cluster status and the hierarchical index compute over the (possibly overlapping) membership without assuming a partition.

## Negative guarantees (must NOT happen)

- A shared ADR does NOT make two capabilities' specs co-members.
- A build spec deriving from two sources does NOT merge those sources.
- A `references`-only link does NOT create membership.
- No membership exists without a real edge / same-feature basis.
