# Implementation Plan: Read the governed citation slots as typed edges

**Branch**: `008-read-citation-slots` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-read-citation-slots/spec.md`

## Summary

Make synthesis read the governed **citation slots** (vocabulary.json@0.3.0 `citation_slots`) and emit
typed cross-repo edges directly, instead of only inferring links from shared prose identifiers. A new
`discover_slot_edges` pass parses the `derived_from` slot from each feature's `spec.md` front-matter
and the `cites` slot from `plan.md` front-matter (honoring a repo's configured `citation_keys`),
resolves `<source-member-id>:<spec-feature-id>` against the workspace and qualified `<NS>-ADR-NNN`
against decisions, and emits `derived_from`/`cites` edges graded **`declared`**. These merge into
`build_link_graph` **first** (so they win dedup), with a feature-pair-aware suppression that collapses
a lower-tier inferred edge already covered by a declared slot edge. Vendored contract re-pinned to
0.3.0 + drift guard updated. No new dependency; gates, single-repo, and no-slot workspaces unchanged.

## Technical Context

**Language/Version**: Python ≥3.11 (`pyyaml` already present — used to parse front-matter; `pydantic`).

**Primary Dependencies**: `pydantic` + `pyyaml` — **no new dependency** (FR-011).

**Storage**: Filesystem; read-only on consumer repos (incl. reading the governance contract read-only).

**Testing**: `pytest` (`uv run pytest skill/tests -q`).

**Target Platform**: the atlas link-discovery stage (deterministic; runs before the agent meld).

**Project Type**: Single project (`skill/scripts`, `skill/tests`).

**Performance Goals**: negligible — one front-matter parse per feature + dictionary resolution.

**Constraints**: no runtime dep on the extension; gates unchanged; ungoverned/no-slot graph identical;
deterministic; neutral examples only.

**Scale/Scope**: a handful of members, dozens of features/ADRs, a few citations per spec.

## Constitution Check

| Principle | Status | Note |
|---|---|---|
| I. Faithfulness is architectural | ✅ | Slot edges resolve to real fragments; an unresolved slot mints NO edge; `verify_links` unchanged. |
| II. Organized by architecture | ✅ | No narrative change; better cross-tier edges → better capability organization. |
| III / IV / V | ✅ | Current-state; unresolved slot reported not invented (fail-closed on gaps); regenerated each run, reproducible. |
| Source-agnostic core | ✅ | Reuses fragments + the link graph; adds one deterministic discovery pass. |
| Reasoning vs determinism | ✅ | Slot parsing/resolution is deterministic; the agent meld is downstream, gated. |
| Toolchain / deps | ✅ | pyyaml already a dep; no new dep. |
| Quality gates | ✅ | drift guard + `pytest` green before push; no-slot baseline byte-identical (SC-005). |

**No violations.** Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/008-read-citation-slots/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/slot-reading-contract.md
├── checklists/requirements.md
└── tasks.md   (/speckit-tasks)
```

### Source Code (repository root)

```text
skill/scripts/
├── vendor/vocabulary.json   # CHANGED — re-pinned 0.2.0 → 0.3.0 (verbatim), adds citation_slots
├── gov_config.py            # CHANGED — RepoConfig.citation_keys (configurable slot key names)
├── discover_links.py        # CHANGED — discover_slot_edges (parse front-matter slots → declared edges)
│                            #            + merge them first + feature-pair-aware dedup
├── synthesize_atlas.py      # CHANGED — gather per-member citation_keys; pass to build_link_graph
└── (verify_links, cluster, render — unchanged)

skill/tests/
├── test_contract_conformance.py  # CHANGED — pin 0.3.0 + assert citation_slots shape
├── test_gov_config.py            # CHANGED — citation_keys parsing
├── test_slot_edges.py            # NEW — parse + resolve + grade + dedup; unresolved → none; no-slot → unchanged
└── fixtures/slots/               # NEW — build spec with derived_from slot (slug NOT in source prose) + plan cites slot
```

**Structure Decision**: Single project, existing layout. One new discovery pass + a contract re-pin +
a config field; everything else additive.

## Architecture (the decided design)

1. **Vendor + drift (vocabulary.json@0.3.0).** Copy the published 0.3.0 verbatim into `vendor/`;
   `test_contract_conformance` pins `version == 0.3.0` and asserts the `citation_slots` block (slots →
   files/locations, the `derived_from`/`cites` grammars, the configurable-keys defaults) matches.

2. **Configured keys (`gov_config`).** `RepoConfig.citation_keys: dict[str,str]` (e.g.
   `{source_specs: "derived_from", adrs: "cites"}`); absent → the contract defaults. These name the
   **front-matter keys** to read (source-spec derivations vs adr citations).

3. **Slot parse + resolve (`discover_links.discover_slot_edges`).** For each member feature:
   - locate the feature's `spec.md` front-matter (the preamble fragment whose text begins `---`) and
     `plan.md` front-matter; parse YAML (`pyyaml`).
   - **derived_from**: read the configured source-spec key (default `derived_from`) → list. For each
     value: `a:b` (colon) → cross-repo, member `a` (origin) + feature `b`; bare `b` → intra-repo,
     this member + feature `b`. Resolve to the **feature representative** (min fragment id of that
     feature) and emit a `derived_from` edge `citing-spec-fragment → source-representative`.
   - **cites**: read the configured adr key (default `cites`) → list of `<NS>-ADR-NNN` (qualified,
     cross-repo) or bare `ADR-NNN` (qualified under the citing repo's namespace). Resolve to the ADR
     fragment (reuse spec-004 qualification) and emit a `cites` edge.
   - grade every slot edge **`declared`**; carry the raw slot value as `evidence`.
   - an unresolved value mints **no** edge and is collected into a returned "unresolved" note list.

4. **Merge + dedup (`build_link_graph`).** Put `discover_slot_edges` **first** in the merge order
   (declared slot → declared manifest → identifier → adr-text → prose). Keep the existing
   locator-precise `_key` (clustering needs per-feature edges). Add a **feature-pair suppression**:
   record `(src.origin, src-feature, dst.origin, dst-feature, rel)` for each declared slot edge (via
   a locator→feature map from the corpora); skip a later lower-tier edge whose feature-pair+rel is
   already covered. Same-tier distinct edges (e.g. two different FR identifier edges) are preserved.

5. **Wire-through (`synthesize_atlas`).** Where it already computes per-member `namespaces`, also
   compute per-member `citation_keys` (from each repo's `.spec-arch-governance.yml` via `gov_config`),
   and pass both to `build_link_graph`.

The existing identifier/adr-text/prose discovery, `verify_links`, clustering, and the single-repo
storybook are unchanged; with no slots present, the merged graph is identical to before.

## Phase 0 / 1

- [research.md](./research.md) — why slot-first + feature-pair dedup (not coarsening `_key`); front-matter
  location; declared tier; no new dep.
- [data-model.md](./data-model.md) — `RepoConfig.citation_keys`; the slot grammars; `discover_slot_edges`
  output (edges + unresolved); the feature-representative + locator→feature map.
- [contracts/slot-reading-contract.md](./contracts/slot-reading-contract.md) — the reader's slot guarantees.
- [quickstart.md](./quickstart.md) — what authoring `derived_from:`/`cites:` now does.

## Complexity Tracking

No constitution violations — table intentionally empty.
