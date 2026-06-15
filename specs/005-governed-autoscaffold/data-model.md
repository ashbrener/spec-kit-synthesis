# Data Model — Governed auto-scaffold + one-command atlas

New and changed structures. All are pydantic models (`extra="forbid"` unless a tolerant read
requires otherwise), consistent with the existing `schema.py` / `gov_config.py` style.

## New — `IngestionSource` (`schema.py`)

One source of fragments contributing to a single member's merged corpus.

| Field | Type | Notes |
|---|---|---|
| `adapter` | `Literal["speckit","code","doc"]` | which adapter ingests this source |
| `path` | `str` | source path, relative to the workspace base (authority dir) or absolute |
| `adr_dir` | `Optional[str]` | when set (doc adapter), forces ADR classification at/under this dir |
| `include` | `Optional[str]` | passthrough extension override (doc/code adapters); default `None` |

`model_config = {"extra": "forbid"}`.

## Changed — `WorkspaceMember` (`schema.py`)

Add one optional field; everything else unchanged (back-compatible — existing hand-authored manifests
and fixtures keep working with the single `adapter`/`path`).

| Field | Type | Notes |
|---|---|---|
| `sources` | `Optional[list[IngestionSource]]` = `None` | when present, **overrides** the single `adapter`/`path` for ingestion: each source is adapted and merged into one origin-stamped corpus. When `None`, the legacy single-adapter path is used. |

Validation: if `sources` is an empty list, treat as `None` (no member can ingest nothing — fall back
to single adapter). `adapter`/`path` remain required (defaulted) so the schema stays valid for the
legacy path and for an operator member that adds only presentation.

## Changed — `RepoConfig` + new `RepoSource` (`gov_config.py`)

`RepoConfig` currently has `namespace`, `adr_dir`, `specs_dir` with `extra="ignore"` (so `sources` is
silently dropped today). Add typed source pointers so authority discovery can follow them.

`RepoSource`:

| Field | Type | Notes |
|---|---|---|
| `id` | `Optional[str]` | the source repo's id (informational) |
| `locator` | `str` | path to the source repo, relative to this repo |
| `role` | `Optional[str]` | expected `"source"` for the authority pointer |

`RepoConfig` adds:

| Field | Type | Notes |
|---|---|---|
| `sources` | `list[RepoSource]` = `[]` | parsed from the config's `sources:` list; empty when absent |

`RepoConfig` keeps `extra="ignore"` (other governance keys remain irrelevant to the reader).

## New — `ScaffoldReport` + `ScaffoldMember` (`scaffold.py`)

The transparent, reviewable account of what was derived (FR-011) — printed before reasoning.

`ScaffoldMember`:

| Field | Type | Notes |
|---|---|---|
| `origin` | `str` | member id (= domain member name) |
| `domain_role` | `str` | source / build / standalone (declared) |
| `namespace` | `str` | declared ADR namespace |
| `locator` | `str` | declared repo locator |
| `specs_dir` | `Optional[str]` | the specifications location read from the repo config |
| `adr_dir` | `Optional[str]` | the decision-record location read from the repo config |
| `present` | `bool` | whether the repo exists on disk |
| `ingested` | `list[str]` | human-readable summary of the sources assembled (e.g. `"specs (speckit)"`, `"ADRs (doc)"`) |

`ScaffoldReport`:

| Field | Type | Notes |
|---|---|---|
| `authority` | `str` | the authority repo path that owns the domain manifest |
| `members` | `list[ScaffoldMember]` | one per declared domain member |
| `skipped` | `list[str]` | origins skipped (optional member, repo absent) |
| `governed` | `bool` | `True` when an authority+valid domain manifest were found |

## New — `AuthorityResult` (`scaffold.py`, internal)

The outcome of discovery (may be represented simply as `Optional[Path]` plus a discovery trail for the
report). Minimal shape:

| Field | Type | Notes |
|---|---|---|
| `authority_dir` | `Path` | dir holding `.spec-arch-domain.yml` |
| `hops` | `list[str]` | the discovery trail (start → … → authority), for the report/debug |

## Role mapping (declared domain role → badge role)

The atlas index badge role is `docs|spec|code|intent`. The scaffold maps the declared domain role:

| Domain role | Badge `role` | Default ingestion |
|---|---|---|
| `source` | `docs` | specs (speckit) + ADRs (doc, adr-forced) + free-form docs (doc) |
| `build` | `spec` | specs (speckit); code only if opted in |
| `standalone` | `spec` | specs (speckit); ADRs (doc) if `adr_dir` declared |

## Relationships & flow

```
discover_authority(start)  ──►  authority dir (owns .spec-arch-domain.yml)
        │  (follows RepoConfig.sources[role=source] with cycle guard)
        ▼
derive_manifest(authority)  ──►  (WorkspaceManifest with per-member `sources`,  +  ScaffoldReport)
        │  reads DomainManifest (declared) + each repo's RepoConfig (specs_dir/adr_dir)
        ▼
overlay_manifest(derived, operator?)  ──►  final WorkspaceManifest
        ▼
synthesize_atlas: stage-0 adapt (merged build_member_corpus) → reason → verify_links → render
```

Nothing in this model alters `DocumentModel`, `LinkGraph`, `verify_links`, or the per-member reasoning
contract.
