# Feature Specification: Read the governed citation slots as typed edges

**Feature Branch**: `008-read-citation-slots`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "Synthesis must read the typed citation slots governance codified in vocabulary.json@0.3.0 (ARCH-ADR-000 Amendment 2) — recovering derived_from/cites edges directly from the declared slots instead of inferring them from prose. In code only, no runtime dependency, read-only on consumer repos, ungoverned/non-slotted repos unchanged. Neutral examples only (CORE/API/WEB)."

## Overview

Governance produces the cross-tier signal as **typed citation slots** — a build spec declares, in its
front-matter, the source feature it derives from and the decisions it cites. Synthesis (the reader)
does not yet consume those slots: it only infers cross-tier links from identifiers that happen to
appear in two repos' prose. So a build spec that correctly declares `derived_from: [docs:002-architecture]`
produces no edge — the source spec's own body never repeats that slug — and the capability never melds.

This feature makes synthesis **read the declared slots**. It conforms to the published contract
(`vocabulary.json@0.3.0`'s `citation_slots`) as a documented format — vendored, drift-guarded, no
runtime dependency — parses the `derived_from`/`cites` slots from the relevant fragments, resolves
each against the workspace, and emits typed cross-repo edges directly. The edges are graded as
author-declared citations (the highest-trust deterministic tier) and merged additively with existing
discovery. Ungoverned or non-slotted repos are unchanged; the fail-closed gates and the single-repo
storybook are untouched. This is the synthesis-side enabler that, paired with governance's authoring,
finally lights up the cross-tier melded story.

## Clarifications

### Session 2026-06-17

- Q: What evidence tier should a slot-derived edge carry (ladder: declared > identifier > prose)? →
  A: **`declared`** — an author explicitly declared the citation in a governed slot, which is strictly
  more trustworthy than an inferred shared identifier or a prose mention; dedup prefers it. This
  broadens the meaning of the `declared` tier from "manifest-declared topology" to "explicitly
  declared (manifest OR citation slot)" — no contract change, reusing the existing evidence enum.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Declared derivation melds the capability (Priority: P1) 🎯 MVP

A build spec declares in its front-matter that it derives from a source feature
(`derived_from: [docs:002-architecture]`). Synthesis reads that declaration and places the build spec
and the source feature in the **same capability** — even though the source spec's body never mentions
the slug. The melded story finally weaves the tiers from the governed signal, not from prose
coincidence.

**Why this priority**: This is the whole point — the cross-tier edge that the governed authoring
produces but synthesis was blind to. Without it, governance's derivation citations are invisible.

**Independent Test**: On a fixture where a build spec's front-matter declares
`derived_from: [<source>:<feature>]` and the source spec body does NOT repeat the slug, build the
graph and assert a `derived_from` edge (build → source feature) exists, and the two cluster together.

**Acceptance Scenarios**:

1. **Given** a build spec whose front-matter declares a cross-repo `derived_from` to a source feature,
   **When** the graph is built, **Then** a typed `derived_from` edge from the build spec to that
   source feature exists — without the slug appearing in the source's prose.
2. **Given** that edge, **When** capabilities are clustered, **Then** the build spec and the source
   feature are in the same capability.
3. **Given** a bare (no-colon) `derived_from` value, **When** resolved, **Then** it resolves to a
   feature within the citing repo (intra-repo derivation).

---

### User Story 2 - Declared citations attach decisions (Priority: P2)

A plan declares the decisions it cites in its front-matter (`cites: [CORE-ADR-007]`). Synthesis reads
the slot and emits a `cites` edge to that decision, so the decision attaches to the citing capability
— deterministically, from the declaration, regardless of whether the qualified id also happened to
appear in prose.

**Why this priority**: Completes the typed-citation reading; decisions attach by declaration, not by
coincidence. The qualified-id-in-text path already worked, but reading the slot makes it explicit and
honors the configured key.

**Independent Test**: On a fixture plan whose front-matter declares a cross-repo `cites` to a source
decision, assert a `cites` edge to that decision exists and it attaches to the citing capability.

**Acceptance Scenarios**:

1. **Given** a plan whose front-matter declares a cross-repo `cites` to a qualified decision id, **When**
   the graph is built, **Then** a `cites` edge from the plan to that decision exists.
2. **Given** a bare `cites` value, **When** resolved, **Then** it is interpreted under the citing
   repo's namespace (intra-repo), consistent with existing bare-ADR handling.

---

### User Story 3 - Conformance, trust, and no regression (Priority: P3)

The reader conforms to the pinned contract version, grades slot edges as the highest-trust tier,
never fabricates an edge for an unresolved slot, and changes nothing for repos that don't use slots.

**Why this priority**: Guards correctness and blast radius — pin the contract, keep the gates and
ungoverned behavior intact, and never invent.

**Independent Test**: (a) the vendored contract is at the pinned version and the drift guard enforces
it; (b) a slot whose target doesn't resolve produces no edge (and is noted); (c) a workspace with no
slots produces the same graph as before.

**Acceptance Scenarios**:

1. **Given** the vendored contract, **When** the drift guard runs, **Then** it confirms the pinned
   version and the slot grammar match the published contract.
2. **Given** a slot edge and an incidentally-inferred shared-identifier edge for the same pair, **When**
   merged, **Then** they collapse to one edge at the higher (declared) tier.
3. **Given** a slot whose target does not resolve in the workspace, **When** the graph is built, **Then**
   no edge is created for it (and it is reported), and the fail-closed gate still applies.
4. **Given** a workspace whose specs declare no slots, **When** built, **Then** the graph is identical
   to before this feature.

---

### Edge Cases

- **Configured key names** differ from the defaults (a repo sets its `citation_keys`): the configured
  key is honored; absent config, the defaults (`source_specs→derived_from`, `adrs→cites`) apply.
- **Malformed slot value** (not matching the grammar): skipped with a note, never a fabricated edge.
- **Unresolvable target** (source member/feature or decision not in the workspace, e.g. an optional
  repo not checked out): no edge, reported honestly.
- **Slot present but value list empty**: nothing to emit (this is the orphan governance surfaces, not
  synthesis's concern).
- **Both a declared slot edge and a prose/identifier edge** for the same pair: deduped to one, graded
  at the strongest tier (declared).
- **A source repo that itself declares intra-repo derivations** between its own features: resolved
  within that repo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Synthesis MUST vendor the published contract at the pinned version that defines the
  citation slots, and read its `citation_slots` definition as a documented format (no runtime
  dependency on the governance extension).
- **FR-002**: The drift-guard conformance check MUST be updated to the pinned contract version and
  MUST fail the build if the vendored copy diverges from the published contract.
- **FR-003**: Synthesis MUST parse the `derived_from` and `cites` citation slots from the declared
  location (the feature's front-matter), honoring a repo's configured slot key names when present and
  the documented defaults otherwise.
- **FR-004**: A `derived_from` slot value of the form `<source-member-id>:<spec-feature-id>` MUST emit
  a typed `derived_from` edge from the citing spec to a representative fragment of that source
  feature; the source-member-id is resolved as a workspace member and the spec-feature-id as a feature
  under that member's specifications.
- **FR-005**: A `derived_from` slot value with no colon MUST be resolved as an intra-repo derivation
  (a feature within the citing repo).
- **FR-006**: A `cites` slot value MUST emit a typed `cites` edge to the referenced decision; a
  cross-repo value MUST be the fully-qualified `<namespace>-ADR-NNN`, while a bare value is interpreted
  under the citing repo's namespace (consistent with existing bare-ADR handling).
- **FR-007**: Slot-derived edges MUST be graded at the **`declared`** evidence tier — the highest-trust
  deterministic tier, above shared-identifier inference and above prose. The `declared` tier thereby
  means "explicitly declared" (manifest topology OR a governed citation slot); no contract change, the
  existing evidence enum is reused.
- **FR-008**: A slot whose target does not resolve in the workspace MUST NOT produce an edge; it MUST
  be reported (coverage-honest), and the fail-closed cross-repo gate MUST still apply.
- **FR-009**: Slot edges MUST be merged additively with existing discovery (declared manifest links,
  shared-identifier, prose) and de-duplicated per directed pair+relation, preferring the higher tier.
- **FR-010**: When no citation slots are present (ungoverned, or specs that don't use them), the graph
  MUST be identical to before this feature; the fail-closed gates and the single-repo storybook MUST
  be unchanged.
- **FR-011**: The feature MUST introduce no new runtime dependency and no external graph/knowledge
  system; slot parsing + resolution are deterministic in-repo code.
- **FR-012**: Source, docs, tests, and fixtures MUST use neutral examples only (CORE/API/WEB) — never
  a real consumer, company, or namespace.

### Key Entities *(include if feature involves data)*

- **Citation slot definition**: the contract's description of where each typed citation lives (file +
  front-matter location), its value grammar, and the configurable key names with defaults.
- **derived_from slot value**: `<source-member-id>:<spec-feature-id>` (cross-repo) or
  `<spec-feature-id>` (intra-repo) — resolved to a source feature.
- **cites slot value**: a qualified `<NS>-ADR-NNN` (cross-repo) or bare `ADR-NNN` (intra-repo) —
  resolved to a decision.
- **Slot-derived edge**: a typed cross-repo edge (`derived_from` / `cites`) graded `declared`,
  carrying the slot value as its evidence.
- **Configured citation keys**: a repo's optional override of the default slot key names.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A build spec that declares a cross-repo `derived_from` slot melds with its source
  feature **even when the slug never appears in the source's prose** (the case that produces 0 edges
  today).
- **SC-002**: For every resolvable declared `derived_from` / `cites` slot, a corresponding typed edge
  exists (declared-tier); **zero** edges are produced for unresolvable slots.
- **SC-003**: A slot edge and an incidentally-inferred edge for the same pair collapse to exactly one
  edge, at the declared tier.
- **SC-004**: The vendored contract is at the pinned version and the drift guard passes against the
  published contract.
- **SC-005**: A workspace with no citation slots produces a graph byte-identical to before this
  feature.
- **SC-006**: No new runtime dependency is introduced; parsing/resolution is deterministic and
  reproducible.
- **SC-007**: No real consumer/company/namespace name appears in source, docs, tests, or fixtures.

## Assumptions

- The published contract (`vocabulary.json@0.3.0`, ARCH-ADR-000 Amendment 2) is the authoritative
  definition of the citation slots; synthesis reads it as a documented format and does not redefine it.
- The slot locations and grammar are as published: `derived_from` in `spec.md` front-matter,
  `cites` in `plan.md` front-matter, with per-repo configurable key names (defaults
  `source_specs→derived_from`, `adrs→cites`).
- A source member id in a `derived_from` slot corresponds to a workspace member origin (the citing
  repo's declared source pointer), and a spec-feature-id corresponds to a feature under that member's
  specifications — the same identities synthesis already uses.
- This builds on specs 004 (vendored contract + bare-ADR qualification), 006 (clustering), and 007
  (structure-aware source ingestion). The existing shared-identifier and prose discovery remain as
  additive fallbacks.
- Reading the contract from the governance repo is read-only; this feature never modifies it.
