# Implementation Plan: Docs-authority capability signal

**Branch**: `007-docs-authority-capability-signal` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-docs-authority-capability-signal/spec.md`

## Summary

Fix the *signal* so the melded story produces real capabilities on a docs-authority workspace. Three
small, additive changes: (1) **structure-aware source ingestion** — a `source` member is ingested as
speckit(`specs_dir`) + doc(`adr_dir`) + doc(repo, **excluding** `specs_dir`/`adr_dir`), so its specs
become distinct feature seeds (not one doc-lumped bucket) and nothing is double-counted; (2) a
**path-prefix exclude** on an ingestion source, honored by the adapters (which already skip hidden
dirs); (3) **cluster classification** — each cluster is labelled `capability` (has a spec), `decision`
(only ADRs), or `background` (only narrative), so signal-less content can't masquerade as a
capability and the agent folds decisions/background in (inline-cited / appendix / overview). The
cross-tier signal (derived_from + cites) is unchanged and now fires because both ends are
structure-aware. No new dependency, gates unchanged, single-repo + ungoverned + build/standalone
untouched.

## Technical Context

**Language/Version**: Python ≥3.11 (stdlib; `pydantic` + `pyyaml` already present).

**Primary Dependencies**: `pydantic` — **no new dependency** (FR-010).

**Storage**: Filesystem; read-only on consumer repos.

**Testing**: `pytest` (`uv run pytest skill/tests -q`).

**Target Platform**: the `speckit.synthesis.atlas` command + the in-session agent.

**Project Type**: Single project (`skill/scripts`, `skill/tests`).

**Performance Goals**: negligible — one extra adapter pass per source member + an O(fragments) classify.

**Constraints**: no new/external signal, no graph system, no new runtime dep; deterministic; gates
unchanged; PAGE-layer + ungoverned + build/standalone ingestion unchanged; neutral examples only.

**Scale/Scope**: a source repo with a handful of spec features, dozens of ADRs, several narrative dirs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Note |
|---|---|---|
| I. Faithfulness is architectural | ✅ | No claims authored; clustering only groups real fragments; `verify`/`verify_links` unchanged. |
| II. Organized by architecture | ✅ **Strengthens** | Capabilities (not doc files / ADR ids) become the organizing unit — the point of the fix. |
| III. Current-state only | ✅ | Unaffected. |
| IV. Fail-closed on gaps | ✅ | Signal-less narrative is honestly classified `background`, never inflated into a capability; nothing dropped. |
| V. Stateless; generated | ✅ | Ingestion + classification regenerated each run; reproducible. |
| Source-agnostic core | ✅ | Reuses the speckit/doc adapters + the existing merged-ingestion path (005 FR-004a). |
| Reasoning vs determinism split | ✅ | Ingestion + classification deterministic; the agent only names/folds, gated. |
| Toolchain uv / pydantic / ≥3.11 | ✅ | No new deps. |
| Quality gates | ✅ | `pytest` green before push; ungoverned/single-repo baselines unchanged. |

**No violations.** Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/007-docs-authority-capability-signal/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/ingestion-and-classification-contract.md
├── checklists/requirements.md
└── tasks.md   (/speckit-tasks)
```

### Source Code (repository root)

```text
skill/scripts/
├── schema.py            # CHANGED — IngestionSource.exclude: list[str]
├── adapter_doc.py       # CHANGED — _is_skipped supports a path-PREFIX exclude (entry with "/")
├── adapter_code.py      # CHANGED — same path-prefix exclude (shared shape)
├── synthesize_atlas.py  # CHANGED — _adapt_one passes --exclude from IngestionSource.exclude
├── scaffold.py          # CHANGED — source member = speckit(specs)+doc(adr)+doc(repo, exclude=specs,adr)
├── cluster.py           # CHANGED — classify each cluster: capability | decision | background
└── (gov_config, render, verify, verify_links — unchanged)

commands/atlas.md        # CHANGED — fold-in contract (inline cited decisions · Decisions appendix · Overview/Background)
skill/tests/
├── test_cluster.py            # CHANGED — classification cases
├── test_adapter_doc.py        # CHANGED — path-prefix exclude
├── test_scaffold.py           # CHANGED — source member ingestion shape (speckit+doc+doc-excluding)
├── test_docs_authority.py     # NEW — end-to-end signal: cross-tier melding on a docs-authority fixture
└── fixtures/docs_authority/   # NEW — source repo (specs_dir + adr_dir + narrative) + build repos
```

**Structure Decision**: Single project, existing layout. All edits are additive/local; no module moves.

## Architecture (the decided design)

1. **Path-prefix exclude (`schema.py` + adapters).** `IngestionSource.exclude: list[str] = []`. The
   adapters' `_is_skipped` gains path-prefix matching: an entry containing `/` matches when the
   file's relpath equals it or starts with `entry + "/"`; a bare name keeps the existing name match;
   hidden dot-dirs are always skipped. `build_corpus` passes the relpath (not just parts) so prefixes
   resolve. `_adapt_one` (synthesize_atlas) forwards the source's `exclude` as `--exclude`.

2. **Structure-aware source ingestion (`scaffold.derive_manifest`).** For a `source` member, replace
   the single doc pass with merged multi-source:
   - `speckit` over `specs_dir` (distinct feature keys — the seeds);
   - `doc` over `adr_dir` with `adr_dir="."` (decisions);
   - `doc` over the repo root with `exclude=[specs_dir, adr_dir]` (free-form narrative, no
     double-count).
   When `specs_dir`/`adr_dir` is absent, omit that pass (degrade honestly). Build/standalone members
   are unchanged.

3. **Cluster classification (`cluster.py`).** After building clusters, label each by membership
   (looked up from the corpora): `capability` if it contains ≥1 spec/code fragment (source or build);
   else `decision` if it contains only ADR fragments; else `background` (only design-doc/narrative).
   Cited ADRs already union into the citing spec's cluster (the `cites` strong rel from 006), so they
   ride inside capabilities; uncited ADRs form `decision` clusters; narrative forms `background`.
   `CapabilityCluster.kind` carries the label; `ClusterSet` exposes it for the brief.

4. **Fold-in contract (`commands/atlas.md`).** The brief tells the agent: capabilities are the
   sections; a cited decision renders inline in its capability; uncited decisions → a Decisions
   appendix; background → a short Overview/Background section; never promote a lone decision or
   signal-less narrative to a capability. (Strict deterministic background — FR-009a.)

The cross-tier signal (derived_from + cites) and the clustering union-find are unchanged — they now
fire because source specs are structure-aware seeds.

## Phase 0 / 1

- [research.md](./research.md) — why structure-aware source ingestion is the lever; path-prefix vs
  name exclude; classification rules; why no new signal/dependency.
- [data-model.md](./data-model.md) — `IngestionSource.exclude`; `CapabilityCluster.kind`; the source
  ingestion plan; the classification function.
- [contracts/ingestion-and-classification-contract.md](./contracts/ingestion-and-classification-contract.md)
  — guarantees: structure-aware source, no double-ingest, classification, cross-tier melding, fold-in,
  determinism, gates unchanged.
- [quickstart.md](./quickstart.md) — what changes on a docs-authority workspace.

## Complexity Tracking

No constitution violations — table intentionally empty.
