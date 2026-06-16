# Data Model — Docs-authority capability signal

Minimal, additive deltas. Pydantic, consistent with the existing IR.

## Changed — `IngestionSource` (`schema.py`)

| Field | Type | Notes |
|---|---|---|
| `exclude` | `list[str]` = `[]` | Path-prefixes (or bare names) the ingestion of THIS source skips, in addition to the always-skipped hidden/tooling dirs. A entry with `/` matches a relpath prefix; a bare name matches a path part. |

Existing fields (`adapter`, `path`, `adr_dir`, `include`) unchanged.

## Changed — adapter skip logic (`adapter_doc.py`, `adapter_code.py`)

`_is_skipped` gains path-prefix matching. Conceptually:

```
skip(rel) =  any part of rel is hidden (startswith ".")  OR
             any part in SKIP_DIRS                         OR
             for e in exclude:  (("/" in e) ? rel == e or rel.startswith(e + "/")
                                            : e in rel.parts)
```

`build_corpus` passes the file's posix relpath so prefix entries resolve; `--exclude` stays
comma-separated (values may contain `/`).

## Changed — `CapabilityCluster` / `ClusterSet` (`cluster.py`)

| Field | Type | Notes |
|---|---|---|
| `CapabilityCluster.kind` | `Literal["capability","decision","background"]` | Classification from membership (see below). |

`build_clusters(...)` classifies each cluster after membership is fixed; ordering keeps capabilities
first (then decisions, then background) for a stable, reviewable brief.

### Classification (pure function of membership, deterministic)

Given a cluster's fragment ids resolved to fragments via the corpora:

| Condition (first match wins) | `kind` |
|---|---|
| contains ≥1 fragment that is a **spec** (kind in spec/plan/tasks/data-model/contract/research, or `SourceType.SPEC`) **or code** (`SourceType.CODE`) | `capability` |
| else contains ≥1 **ADR** fragment (kind `adr` / `SourceType.ADR`) | `decision` |
| else (only free-form `design-doc` narrative) | `background` |

Cited ADRs do not form `decision` clusters — they are already unioned into the citing spec's
`capability` cluster by the `cites` strong rel (006). Uncited ADRs stand alone → `decision`.

## New — source ingestion plan (in `scaffold.derive_manifest`, no new type)

For a `source` member, the derived `WorkspaceMember.sources` becomes (omitting a pass when its dir is
undeclared):

| Pass | adapter | path | adr_dir | exclude |
|---|---|---|---|---|
| specs | `speckit` | `<locator>/<specs_dir>` | — | — |
| ADRs | `doc` | `<locator>/<adr_dir>` | `"."` | — |
| narrative | `doc` | `<locator>` | — | `[specs_dir, adr_dir]` |

Build/standalone members keep their 005/006 ingestion unchanged.

## Flow

```
scaffold.derive_manifest → source member.sources = [speckit(specs), doc(adr), doc(repo, exclude)]
        │  build_member_corpus merges the 3 passes → one origin-stamped corpus (no double-ingest)
        ▼
merged corpus + link_graph → cluster.build_clusters → ClusterSet (each cluster.kind classified)
        │  capabilities = seeds w/ cross-tier members; decisions = uncited ADRs; background = narrative
        ▼
briefs (clusters.json carries kind) → agent: capabilities as sections; cited decisions inline;
        uncited decisions → appendix; background → overview  → verify (unchanged) → render
```

No change to `verify.py`, `verify_links.py`, `render.py` schema, or the PAGE-layer contract.
