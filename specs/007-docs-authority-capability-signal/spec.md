# Feature Specification: Docs-authority capability signal

**Feature Branch**: `007-docs-authority-capability-signal`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Make the melded capability story produce SEMANTIC capabilities on a docs-authority workspace — fix the source-repo ingestion so its specs are structure-aware, attach ADRs/narrative correctly, and confirm the existing cross-tier signal is sufficient. Single-repo storybook + gates unchanged. Neutral examples only (CORE/API/WEB)."

## Overview

The melded story (spec 006) organizes a multi-repo workspace by capability. It works when capability
clusters form across tiers. On a **docs-authority workspace** — where the source repo is a
documentation repository (narrative folders, an ADR directory, and spec-kit specs under its declared
specs dir) — it currently does not: the source repo is ingested in a single free-form documentation
pass, so its spec-kit specs collapse into one bucket, its decision records each become a separate
bucket, and its narrative folders each become a spurious "capability". Build repos can no longer
attach to distinct source features, so the cross-tier melding the whole feature depends on barely
happens.

This feature fixes the **signal**, not the engine. It ingests a source repo structure-aware (its
specs as specifications, its decision records as decisions, its narrative as background — without
double-counting), and it classifies clusters so signal-less content cannot masquerade as a
capability. The cross-tier signal itself (a build spec deriving from a source spec; a spec citing a
decision) is unchanged and sufficient once both ends are structure-aware. The single-repo storybook
and the fail-closed gates are untouched; ungoverned and non-docs-authority workspaces are unaffected.

## Clarifications

### Session 2026-06-16

- Q: How should decisions and background appear in the melded story (vs the catalog, where everything
  always lives)? → A: **Inline cited + appendix/overview** — a decision a capability cites renders
  inline within that capability; uncited decisions gather in a **Decisions appendix**; free-form
  background gets a short **Overview/Background** section. Everything also remains in the catalog;
  nothing is dropped from the read (coverage-honest).
- Q: Should signal-less narrative ever auto-attach to a capability, or stay strictly background? → A:
  **Strict background, deterministic** — narrative with no derive-from/cites tie is classified
  background and never auto-attached to a capability; clustering stays reproducible (the agent may
  still reference background in prose, but membership is not fuzzily inferred).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cross-tier capabilities actually form (Priority: P1) 🎯 MVP

On a docs-authority workspace, a build repo's specification and the source specification it derives
from land in the **same capability** — so a reader sees one woven "Authentication" capability
spanning the source intent and the build tiers, not a lone source bucket plus disconnected build
buckets. The source repo's specifications are read as distinct features, not collapsed into one.

**Why this priority**: This is the whole point — without cross-tier capabilities the melded story
degrades to per-repo silos on exactly the workspace shape it most needs to serve. Everything else
refines it.

**Independent Test**: On a docs-authority fixture (a source repo with a specs dir, an ADR dir, and
narrative folders; build repos whose specs derive from the source specs), build and inspect the
clusters: each source specification is a distinct feature, and a build spec lands in the same cluster
as the source spec it derives from.

**Acceptance Scenarios**:

1. **Given** a source repo whose specs dir holds several features, **When** the workspace is ingested,
   **Then** those features are read as distinct, individually-identified specifications — not merged
   into one bucket.
2. **Given** a build spec that derives from a particular source feature, **When** clusters are formed,
   **Then** the build spec and that source feature are in the **same** capability cluster.
3. **Given** the source repo's narrative and decision records, **When** ingested alongside its specs,
   **Then** no content is ingested twice (a spec is not also read as free-form prose).

---

### User Story 2 - Decisions and background don't masquerade as capabilities (Priority: P2)

The story's sections are real capabilities. A lone decision record is not presented as a capability;
neither is a narrative folder. Decisions a capability relies on are attached to that capability;
decisions nothing references are gathered as decisions; narrative nothing references is background.

**Why this priority**: After US1 the right things cluster, but the workspace still contains many
decision records and narrative folders; without classification they reappear as dozens of pseudo-
capabilities and bury the real story.

**Independent Test**: On the fixture, assert every cluster is classified — capability (has a
specification), decision (only decision records), or background (only narrative) — and a cited
decision attaches to the capability that cites it.

**Acceptance Scenarios**:

1. **Given** a cluster containing at least one specification, **When** classified, **Then** it is a
   **capability**.
2. **Given** a cluster of only decision records, **When** classified, **Then** it is a **decision**,
   not a capability.
3. **Given** a cluster of only narrative, **When** classified, **Then** it is **background**, not a
   capability.
4. **Given** a decision a specification cites, **When** clusters form, **Then** that decision is part
   of the citing capability (not a separate bucket).
5. **Given** the composed story, **When** rendered, **Then** capabilities are the sections, while
   decisions and background are folded in (e.g. a decisions appendix / a background overview) — never
   promoted to capability sections.

---

### User Story 3 - Confirmed signal; everything else unaffected (Priority: P3)

The cross-tier signal stays the existing typed traceability (derive-from + cites) — no new or
external signal, no graph system, no new dependency. An ungoverned or non-docs-authority workspace
produces the same output as before; clustering remains deterministic and reproducible; the gates are
unchanged.

**Why this priority**: Guards the blast radius — the fix must not regress the cases that already work
or smuggle in a dependency the project forbids.

**Independent Test**: (a) Re-run an ungoverned/non-docs-authority fixture and assert output is
unchanged; (b) assert clustering is reproducible across runs; (c) assert no new runtime dependency is
introduced.

**Acceptance Scenarios**:

1. **Given** a build/standalone repo, **When** ingested, **Then** its ingestion shape is unchanged by
   this feature.
2. **Given** an ungoverned or non-docs-authority workspace, **When** built, **Then** the result is the
   same as before this feature.
3. **Given** identical inputs, **When** clustered twice, **Then** the clusters are identical.

---

### Edge Cases

- **Source repo with no specs dir** (pure narrative + decisions): no specifications to seed from →
  produce decisions + background honestly; do not fabricate capabilities. (Surfaces the limit of a
  docs-only authority rather than inventing structure.)
- **A source feature with no build derivation**: stands as a source-only capability (intent not yet
  built) — consistent with the build-status model.
- **A decision cited by multiple capabilities**: attaches to each citing capability (shared decision),
  without duplicating its content as a separate bucket.
- **Narrative that a capability's prose references**: stays **background** (strict, deterministic —
  no auto-attach); the agent may mention it in the capability's prose, but it is not pulled into the
  capability's cluster.
- **specs dir / adr dir overlap or nesting** (e.g. ADRs inside the docs tree): the exclude must be a
  path-prefix so the free-form pass skips exactly those subtrees, not every similarly-named folder.
- **A non-docs-authority source** (e.g. a code-only source): unaffected — structure-aware ingestion
  applies what the repo actually declares.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A source repo MUST be ingested as merged multi-source within its single member: its
  declared specifications location read structure-aware (as specifications, each a distinct feature),
  its declared decision-record location read as decisions, and its remaining free-form narrative read
  as documentation.
- **FR-002**: The free-form narrative pass MUST EXCLUDE the specifications and decision-record
  locations (by path prefix) so no content is ingested twice.
- **FR-003**: The exclusion MUST be expressible per ingestion source and honored by the ingestion
  step (in addition to the always-skipped hidden/tooling directories).
- **FR-004**: A build/standalone repo's ingestion MUST be unchanged by this feature.
- **FR-005**: Each cluster MUST be classified by membership as a **capability** (contains ≥1
  specification, source or build), a **decision** (only decision records), or **background** (only
  free-form narrative).
- **FR-006**: A decision record that a specification cites MUST be part of the citing capability's
  cluster (not a standalone bucket).
- **FR-007**: A source repo's specifications MUST NOT be collapsed into a single bucket; each declared
  source feature MUST be individually identifiable as a cluster seed.
- **FR-008**: A build specification MUST cluster together with the source specification it derives
  from (cross-tier capability formation).
- **FR-009**: The reasoning hand-off MUST present capabilities as the story's sections and fold the
  rest in: a **cited** decision renders **inline** within the capability that cites it; **uncited**
  decisions gather in a **Decisions appendix**; free-form **background** gets a short
  **Overview/Background** section. It MUST NOT promote a lone decision or signal-less narrative to a
  capability section. (All content also remains in the catalog; nothing is dropped — coverage-honest.)
- **FR-009a**: Signal-less narrative (no derive-from/cites tie) MUST be classified **background**
  deterministically and MUST NOT be auto-attached to a capability cluster; the agent may reference it
  in prose but cluster membership is never fuzzily inferred.
- **FR-010**: The cross-tier signal MUST remain the existing typed traceability (derive-from + cites);
  the feature MUST introduce no new or external signal, no graph system, and no new runtime
  dependency.
- **FR-011**: Clustering MUST remain deterministic and reproducible; the fail-closed gates MUST be
  unchanged.
- **FR-012**: An ungoverned or non-docs-authority workspace MUST produce output unchanged from before
  this feature; nothing reverts to per-repo silos.
- **FR-013**: Source, docs, tests, and fixtures MUST use neutral examples only (CORE/API/WEB) — never
  a real consumer, company, or namespace.

### Key Entities *(include if feature involves data)*

- **Source ingestion plan**: for a source repo, the set of ingestion passes (specifications →
  structure-aware; decision records → decisions; narrative → documentation, with the first two
  excluded) merged under the one member.
- **Ingestion exclusion**: a path-prefix list on an ingestion source that the ingestion step skips
  (beyond the always-skipped hidden/tooling dirs).
- **Cluster classification**: the label assigned to each cluster — capability / decision / background
  — from its membership.
- **Capability / decision / background**: the three kinds of cluster the story treats differently —
  capabilities are sections; decisions and background are folded in.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the docs-authority fixture, the number of source specifications read as distinct
  features equals the number of declared source features (no collapse-to-one).
- **SC-002**: For every build spec that derives from a source spec, both appear in the **same**
  capability cluster (cross-tier melding rate for derived specs = 100%).
- **SC-003**: **No** content is ingested twice (a specification never also appears as a free-form
  narrative fragment).
- **SC-004**: **Zero** clusters made only of narrative or only of a lone decision are presented as
  capability sections.
- **SC-005**: Every cited decision attaches to the capability that cites it.
- **SC-006**: Clustering is reproducible (identical inputs → identical clusters) and introduces no new
  runtime dependency.
- **SC-007**: An ungoverned / non-docs-authority workspace's output is unchanged from before.
- **SC-008**: No real consumer/company/namespace name appears in source, docs, tests, or fixtures.

## Assumptions

- The source repo declares its specifications and decision-record locations (the governance per-repo
  config already carries these); structure-aware ingestion reads exactly what is declared.
- A source repo's spec-kit specifications are the right capability seeds for a docs-authority
  workspace; narrative folders are background (strict — never auto-attached to a capability).
- The existing typed traceability (derive-from + cites) is the sufficient cross-tier signal once both
  ends are structure-aware — confirmed by this feature, not replaced.
- This builds on specs 005 (governed auto-scaffold / ingestion) and 006 (melded story / clustering);
  the agent's theme-grouping (006) still collapses fine capability clusters into named themes.
- "Background" and "decisions" are presented as supporting material, not omitted — coverage-honesty is
  preserved (nothing is dropped).
