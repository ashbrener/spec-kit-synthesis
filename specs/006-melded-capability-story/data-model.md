# Data Model — Melded capability story

New structures + the minimal schema deltas. Pydantic, `extra="forbid"` unless noted, consistent with
`schema.py` / the existing IR.

## Schema deltas (`schema.py`) — minimal, additive, back-compatible

### `Block` (add two optional fields)

| Field | Type | Notes |
|---|---|---|
| `tier` | `Optional[str]` = `None` | The contributing tier/member origin (e.g. `"backend"`, `"frontend"`). `None` = functional/source layer (always-visible). The renderer groups technical blocks by `tier` into per-tier disclosures. |
| `build_status` | `Optional[Literal["built","partial","planned"]]` = `None` | Per-block build grade; `planned` renders faded. `None` = inherit the tier/section grade. |

### `Section` (add one optional field)

| Field | Type | Notes |
|---|---|---|
| `build_status` | `Optional[Literal["built","partial","planned"]]` = `None` | Capability-level grade shown as a badge by the heading. |

### `DiagramGraph.layout` (extend the Literal)

Add `"sequence"` and `"erd"` to the existing eight (`pipeline/mapping/ladder/flow/panel/hub/stack/
timeline`). Default unchanged.

All deltas are optional → existing fixtures, golden files, and tests are unaffected.

## New — clustering (`cluster.py`)

`CapabilityCluster`:

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | stable, deterministic cluster id (from the seed source feature, else the orphan feature) |
| `seed` | `Optional[str]` | the source feature `feature_key` that seeded it (None for an orphan build/standalone cluster) |
| `members` | `dict[str, list[str]]` | origin → fragment ids belonging to this cluster (grouped by tier) |
| `tiers` | `list[str]` | the origins contributing, in role order (source first, then build) |
| `evidence` | `list[str]` | why members joined (e.g. `"backend/007 derived_from CORE/auth"`) — reviewable |

`ClusterSet`: `clusters: list[CapabilityCluster]` + `unclustered: list[str]` (fragment ids that joined
nothing — surfaced honestly, never dropped).

## New — build status (`build_status.py`)

`BuildGrade` = `Literal["built","partial","planned"]`.

`TierStatus`:

| Field | Type | Notes |
|---|---|---|
| `origin` | `str` | the tier/member |
| `grade` | `BuildGrade` | fused grade |
| `coverage` | `Optional[str]` | the coverage signal (spec_backed / specced_only / none) |
| `lifecycle` | `Optional[str]` | the lifecycle signal (e.g. `"tasks 6/8"`, `"no tasks"`) |
| `reason` | `Optional[str]` | set when signals conflicted → `partial` |

`CapabilityStatus`: `cluster_id: str`, `overall: BuildGrade`, `tiers: list[TierStatus]`. `overall` =
built only if every present tier is built; planned if all planned; else partial.

## New — source index + titles (`source_index.py`)

`SourceIndexNode` (a tree node):

| Field | Type | Notes |
|---|---|---|
| `kind` | `Literal["repo","feature","artifact"]` | level in the tree |
| `label` | `str` | human title (feature title from spec H1/frontmatter; repo title; artifact kind) |
| `href` | `Optional[str]` | drill-to-source link (artifact nodes) |
| `children` | `list[SourceIndexNode]` | nested nodes |

`TitleMap` = `dict[str, SourceTitle]` keyed by locator, where `SourceTitle` = `{title, artifact_kind,
repo}` — the deterministic human-readable label used by the renderer's source tables (injected via a
`_TITLES` context-var seam, mirroring the existing `_RESOLVE` seam). Title derivation: feature's
`spec.md` H1 (or frontmatter `title`); fallback = the feature id, clearly marked.

## Flow

```
merged corpus + link_graph
        │  cluster.build_clusters() ─────────────► ClusterSet (membership, deterministic)
        │  build_status.grade(cluster, corpora) ─► CapabilityStatus per cluster
        │  source_index.build_titles/build_tree ─► TitleMap + SourceIndexNode tree
        ▼
per-cluster briefs  ──(agent, gated)──►  ONE melded DocumentModel (sections=capabilities,
                                          blocks tagged tier + build_status)
        ▼
verify_links + verify.py (UNCHANGED)  ──►  render.py (per-tier disclosure, fading, nested nav,
                                            source tables, sequence/erd diagrams) + hierarchical index
```

Nothing here changes `verify.py`, `verify_links.py`, the adapters, or the PAGE-layer reasoning
contract.
