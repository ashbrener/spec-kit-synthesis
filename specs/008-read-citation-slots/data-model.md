# Data Model — Read the governed citation slots

## Changed — vendored contract (`skill/scripts/vendor/vocabulary.json`)

Re-pinned `version: "0.2.0"` → `"0.3.0"` (verbatim from the published contract), gaining the
`citation_slots` block: `slots` (derived_from→spec.md front-matter, cites→plan.md front-matter),
the `derived_from`/`cites` value grammars, and `keys` (configurable via `citation_keys`, defaults
`source_specs→derived_from`, `adrs→cites`).

## Changed — `RepoConfig` (`gov_config.py`)

| Field | Type | Notes |
|---|---|---|
| `citation_keys` | `dict[str, str]` = `{}` | A repo's optional override of the slot key names — `{source_specs: <key>, adrs: <key>}`. Absent → the contract defaults. |

(`extra="ignore"` already tolerates other keys.)

## New — slot grammars (parsed, not stored as models)

- **derived_from** value: `^([a-z0-9-]+):([0-9]+-[a-z0-9-]+)$` (cross-repo `<source-member-id>:<spec-feature-id>`)
  or `^([0-9]+-[a-z0-9-]+)$` (intra-repo `<spec-feature-id>`). Colon = cross-repo discriminator.
- **cites** value: `^([A-Z][A-Z0-9]*-)?ADR-\d{3,}$` — qualified `<NS>-ADR-NNN` (cross-repo) or bare
  `ADR-NNN` (intra-repo, qualified under the citing repo's namespace).

## New — `discover_slot_edges` (in `discover_links.py`)

```
discover_slot_edges(manifest, corpora, namespaces, citation_keys) -> (list[LinkEdge], list[str])
```

| Output | Notes |
|---|---|
| edges | `LinkEdge`s graded `evidence_kind = declared`; `evidence` = the raw slot value; `rel` = derived_from / cites. src = the citing feature's spec/plan fragment; dst = the resolved target (source feature representative, or ADR fragment). |
| unresolved | human-readable notes for slot values that didn't resolve (reported, never an edge). |

Helpers:
- **feature representative**: for a given (origin, feature_key), the min fragment id — a stable edge
  endpoint.
- **locator→feature map**: `{fragment_id → (origin, feature_key)}` from the corpora, used by the
  feature-pair dedup.
- **front-matter parse**: read the `--- … ---` preamble of the feature's `spec.md` / `plan.md`
  fragment via `pyyaml`; pull the configured key (or default).

## Changed — `build_link_graph` merge order + dedup (`discover_links.py`)

Order: **slot edges (declared) → declared manifest → identifier → adr-text → prose**. Keep the
locator-precise `_key` for same-tier dedup. Add a feature-pair guard:

```
declared_pairs = {(o_src, feat_src, o_dst, feat_dst, rel) for declared slot edges}
# when adding a lower-tier edge, skip if its feature-pair+rel ∈ declared_pairs
```

So a slot edge wins over an incidental identifier/prose edge for the same feature pair; distinct
same-tier edges (different FRs) are preserved; clustering still sees per-feature edges.

## Changed — `synthesize_atlas.py`

Alongside the per-member `namespaces` it already builds, gather per-member `citation_keys` (from each
repo's `.spec-arch-governance.yml` via `gov_config`) and pass both into `build_link_graph`.

## Flow

```
corpora + manifest + namespaces + citation_keys
        │  discover_slot_edges: parse spec.md/plan.md front-matter → resolve → declared edges (+unresolved)
        ▼
build_link_graph: [slot(declared) , declared-manifest , identifier , adr-text , prose] → dedup
        │  (exact _key for same-tier; feature-pair suppression of lower-tier under a declared slot)
        ▼
verify_links (unchanged) → cluster (unchanged: per-feature edges intact) → meld
```

No change to `verify.py`, `verify_links.py`, `cluster.py`, `render.py`, or the PAGE-layer contract.
