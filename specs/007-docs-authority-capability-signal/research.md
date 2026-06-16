# Research — Docs-authority capability signal

## D1 — Structure-aware source ingestion is the lever (not a new signal)

**Decision**: Ingest a `source` member as `speckit(specs_dir)` + `doc(adr_dir)` + `doc(repo, exclude=
[specs_dir, adr_dir])`, instead of one doc pass over the whole repo.

**Rationale**: The dogfood blocker was that a docs-authority source, doc-adapted in one pass, gives
its spec-kit specs `feature_key = top-level dir` (e.g. all of `docs/specs/*` collapse to `"specs"`).
So build specs had no distinct source feature to `derived_from`, and cross-tier melding failed. Read
the source's specs with the **speckit adapter** and each becomes a distinct feature — the seed the
existing `derived_from` edges land on. The existing signal was right; it just never fired because one
end wasn't structure-aware. This is the smallest change that unblocks everything downstream.

**Rejected**: a new/different cross-tier signal (embeddings, title similarity, a graph tool) — the
project forbids ungated inference + new deps, and it's unnecessary once the seeds are structure-aware.

## D2 — Avoid double-ingest with a path-PREFIX exclude

**Decision**: The free-form narrative doc pass excludes `specs_dir` and `adr_dir` by **path prefix**.
Add `IngestionSource.exclude: list[str]`; the adapters' `_is_skipped` matches an entry containing `/`
as a relpath prefix (and a bare name as today); hidden dot-dirs are always skipped.

**Rationale**: If the narrative pass also walked `specs_dir`/`adr_dir`, those files would be ingested
twice (structure-aware AND as prose) — corrupting clusters and citations. A **name**-based exclude
(the #23 shape) is too coarse: `adr_dir` is often multi-segment (`docs/adr`, `02_System_Architecture/
ADRs`) and a leaf name like `ADRs` could over-match. A path-prefix matches exactly the declared
subtree. Reuses the existing skip mechanism — no new walk.

## D3 — Classify clusters so signal-less content can't pose as a capability

**Decision**: Label each cluster `capability` (≥1 spec/code fragment), `decision` (only ADRs), or
`background` (only free-form narrative). Cited ADRs already union into the citing spec's cluster (the
`cites` strong rel, 006), so they ride inside capabilities; uncited ADRs are `decision`; narrative is
`background`. The agent makes capabilities the sections and folds the rest in (FR-009).

**Rationale**: After D1/D2 the right things cluster, but a docs repo still has many ADRs and narrative
dirs; without a label each becomes a pseudo-capability and buries the story. Classification is a pure
function of membership — deterministic, reviewable, no reasoning. It also encodes coverage-honesty:
nothing is dropped, it's just placed (capability / appendix / background / catalog).

**Strict background (clarified)**: signal-less narrative is never auto-attached to a capability — no
fuzzy "this doc is about auth" inference. The agent may *reference* background in prose, but cluster
membership stays deterministic and reproducible.

## D4 — Fold-in presentation (clarified)

**Decision**: A cited decision renders inline within its capability; uncited decisions gather in a
**Decisions appendix**; background gets a short **Overview/Background** section; everything also stays
in the catalog. This is an agent-contract change (`commands/atlas.md`) + the cluster `kind` the brief
exposes — no renderer change required (these are ordinary sections/blocks the agent composes).

**Rationale**: Keeps the read coverage-honest (nothing dropped) while keeping capability sections
about capabilities. Leaves *how* to compose to the gated agent; the deterministic layer only supplies
the classification.

## Cross-cutting

- **No new dependency** (pydantic + pyyaml only); **no new signal** (derived_from + cites unchanged);
  determinism + the fail-closed gates preserved.
- **Blast radius**: build/standalone member ingestion is unchanged; an ungoverned or non-docs-authority
  workspace is unaffected (the new source-ingestion shape only applies to a `source` member that
  declares `specs_dir`/`adr_dir`).
- **Fixture**: a new `docs_authority/` workspace — a source repo with `specs_dir` (≥2 features), an
  `adr_dir` (a cited + an uncited ADR), and narrative dirs; build repos whose specs `derived_from` the
  source specs and cite an ADR — exercises cross-tier melding, classification, and no-double-ingest on
  neutral data.
