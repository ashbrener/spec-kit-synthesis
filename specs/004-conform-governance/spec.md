# Feature Specification: Conform to arch-governance contracts (the reader)

**Feature Branch**: `004-conform-governance`

**Created**: 2026-06-14

**Status**: Ready (clarified)

**Input**: Governance handoff (v2): make synthesis genuinely conform to the published contracts
(shared vocabulary v0.2.0 + the domain-manifest schema) and read the manifest as the topology
registry — in code only, no runtime dependency, read-only on consumer repos, still working on
ungoverned ones.

## Overview

Synthesis reads a project's sources and renders them into a storybook/portal with a cross-repo
traceability atlas. When a project is **governed** (it adopts the architecture-governance
convention), it publishes structured, trustworthy facts — typed citations, namespaced decisions,
a declared topology. Synthesis currently can't read most of that, and in one case speaks a
*different dialect* than the contract it claims to follow. This feature makes synthesis a faithful
**reader** of those contracts so a governed project produces a richer, correctly-typed,
evidence-graded portal — while an ungoverned project produces exactly what it does today.

Synthesis conforms **as a documented format** (its adapters are coded to the contract, the way the
spec-kit adapter is coded to spec-kit's folder layout) — never a runtime dependency on the
governance extension.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — The citation graph becomes visible and correctly typed (Priority: P1)

A reader opens the portal of a governed multi-repo project. Today, the relationships between specs,
code, and decisions are flattened to a generic "references" (or mis-typed), and the spec/plan→decision
**citations the governance layer produces are invisible entirely**. After this feature, the atlas
shows *typed, directional* relationships — "this plan **cites** that decision," "this code
**implements** that spec," "this spec is **derived from** that one" — matching the shared vocabulary.

**Why this priority**: This is the core value and a **correctness blocker** — synthesis presently
claims to speak the contract's relations but uses different names, and lacks the *citation* edge
that is the entire point of a governance layer. Without it, the governed signal can't be read at all.

**Independent Test**: Point synthesis at a governed fixture whose plans cite decisions and whose
code implements specs; the rendered atlas shows `cites` and `implements` edges with the correct
direction. Delivers the typed-traceability payoff on its own.

**Acceptance Scenarios**:

1. **Given** a governed project where a plan declares a citation to a decision, **When** the portal is built, **Then** the atlas shows a typed `cites` edge from that plan to that decision.
2. **Given** a project that previously rendered a relationship as the old/divergent name, **When** rebuilt, **Then** the relationship is rendered under the contract's canonical name (no divergent dialect remains).
3. **Given** an ungoverned project, **When** the portal is built, **Then** its output is unchanged from before this feature.

---

### User Story 2 — A declared topology is trusted over guesswork (Priority: P2)

A governed multi-repo project declares its members, their roles, their namespaces, and where each
lives. When synthesis sees that declaration, it uses it as the **source of truth** for the project's
structure instead of inferring it — and marks those facts as the highest-trust tier. A project that
declares nothing still works from the reader's own description.

**Why this priority**: This is the integration that turns "guessed" cross-repo structure into
"declared" fact — measurably richer signal — without breaking ungoverned projects.

**Independent Test**: Provide a project with a declared topology manifest; the rendered topology
(members, roles, namespaces) matches the manifest exactly. Remove the manifest; the reader still
produces a portal from its own record.

**Acceptance Scenarios**:

1. **Given** a project with a valid declared topology manifest, **When** the portal is built, **Then** members/roles/namespaces/locators come from the manifest, and the reader's own record supplies only presentation (titles, descriptions, theme).
2. **Given** a manifest field and a presentation-record field that overlap on structure, **When** both are present, **Then** the manifest wins on the structural field.
3. **Given** no manifest, **When** the portal is built, **Then** the reader's own record supplies the topology (fallback) and the build succeeds.
4. **Given** a manifest that does not match the published shape, **When** the portal is built, **Then** the reader reports it as invalid and falls back rather than trusting malformed structure.

---

### User Story 3 — Unprefixed decisions are understood without renaming (Priority: P3)

A repo stores its decisions as plain, unprefixed identifiers (the common real-world case). Synthesis
reads each such decision under the repo's *configured namespace*, so its decisions are correctly
attributed and citable — with **no file renames required**. A bare identifier stays local to its
repo; only fully-qualified identifiers connect across repos.

**Why this priority**: Removes the single biggest adoption-friction (we previously had to rename
files to be recognised) — valuable, but the typed graph (US1) and declared topology (US2) deliver
the headline value first.

**Independent Test**: A governed repo with bare decision ids and a configured namespace; its
decisions render attributed to that namespace, and a cross-repo citation resolves only when written
in the qualified form.

**Acceptance Scenarios**:

1. **Given** a repo with a configured namespace and a bare decision id, **When** read, **Then** the decision is treated as that-namespace-qualified, with no file renamed.
2. **Given** a bare decision id, **When** another repo references it, **Then** it is NOT matched across the repo boundary (only the qualified form is).

---

### Edge Cases

- A manifest references a member whose source isn't present → the member is reported missing/skipped, not fabricated (coverage-honest), and the build still completes.
- A fully-qualified decision id whose prefix doesn't match its repo's configured namespace → flagged, not silently accepted.
- A governed repo with no namespace configured → bare ids stay unqualified (repo-local) and render honestly; no guess.
- The pinned contract copy and the reader's own relation set diverge → the conformance check fails loudly (drift guard), rather than rendering a silent mistruth.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The reader's cross-repo relation vocabulary MUST match the shared contract's relations exactly: `derived_from`, `cites`, `implements`, `supersedes`, `references`. Reconciliation: the old `derives_from` spelling → `derived_from`; the code→spec edge → `implements`; the current **docs↔spec** edge → `references` (the contract has no docs↔spec relation — use the untyped fallback rather than mistype it); `cites` is added; `supersedes`/`references` already match. No silent local divergence remains.
- **FR-002**: The reader MUST be able to represent and read the **`cites`** relation (a spec/plan → decision citation) — the citation edge the governance layer produces.
- **FR-003**: The reader MUST accept **bare** decision identifiers (`ADR-NNN`) and interpret each under the owning repo's configured namespace (`<namespace>-ADR-NNN`), and MUST continue to accept the fully-qualified form. A bare identifier is repo-local and MUST NOT be matched across a repo boundary; cross-repo references resolve only in the qualified form.
- **FR-004**: When a project declares a topology manifest, the reader MUST validate it against the published manifest schema and, if valid, use it as the **source of truth** for structural topology — members, roles, namespaces, locators.
- **FR-005**: The reader's own project record MUST remain (a) the topology **fallback** when no manifest is present, and (b) the **presentation overlay** (titles, descriptions, theme, ordering) always. When both are present, the manifest wins on overlapping *structural* fields; the manifest never carries presentation.
- **FR-006**: The reader MUST grade every discovered cross-repo fact by **evidence tier** — `declared` (from manifest/config), `identifier` (shared qualified identifier), `prose` (text cross-reference) — and that grade MUST be surfaced.
- **FR-007**: The reader MUST keep a **pinned, vendored copy** of the contracts it conforms to, and a check (run in CI) MUST fail if the reader's relation/enum set no longer matches the pinned copy (drift guard).
- **FR-008**: Conformance MUST be **in code only** — no runtime/import dependency on the governance extension; operation MUST be **read-only** on consumer repos; and an **ungoverned** project MUST produce output unchanged from before this feature.
- **FR-009**: No real consumer, company, or namespace name may appear in synthesis source, docs, fixtures, or tests — neutral examples only (e.g. `CORE` / `API` / `WEB`).

### Key Entities

- **Relation**: a typed, directional edge between two artefacts; its allowed values are exactly the contract's relations.
- **Decision identifier**: either *bare* (`ADR-NNN`, repo-local, qualified by the repo's namespace) or *qualified* (`<NS>-ADR-NNN`, cross-repo-resolvable).
- **Topology manifest**: the declared registry of a governed domain — a list of members, each with a name, role, namespace, and locator. Owns structure, never presentation.
- **Presentation record**: the reader's own project description — titles, descriptions, theme; also the topology fallback when no manifest exists.
- **Evidence tier**: the trust grade of a discovered fact — `declared` > `identifier` > `prose`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a governed multi-repo fixture, **100%** of authored spec/plan→decision citations appear as typed `cites` edges in the atlas (today: 0% — the edge type does not exist).
- **SC-002**: A repo that stores decisions as bare identifiers has its decisions correctly attributed to its namespace with **zero file renames**.
- **SC-003**: When a topology manifest is present, the rendered members/roles/namespaces match it exactly; when absent, the reader still produces a complete portal from its own record (no failure, no regression).
- **SC-004**: Every cross-repo relationship in the atlas carries an evidence grade, so a reader can tell a *declared* fact from a *guessed* one.
- **SC-005**: The conformance check fails the build when the reader's relation set diverges from the pinned contract (proven by a deliberate mismatch).
- **SC-006**: An ungoverned project produces byte-identical output to the pre-feature baseline (no regression).

## Assumptions

- The contracts (`vocabulary.json` v0.2.0 and the domain-manifest schema) are published, versioned, and vendorable at a pinned tag; on any disagreement the machine-readable files are authoritative.
- A governed repo carries its namespace in its own per-repo config; the authority repo of a domain carries the topology manifest.
- Conformance is "as a format" (no runtime dependency), per the writer↔reader boundary.
- The faithfulness engine and the fail-closed verify gate are **out of scope** and untouched; this feature only enriches what the reader *extracts* and *renders*.

## Resolved decisions

- **docs↔spec edge → `references`.** The handoff assumed the reader's old `specified_by` was a code↔spec edge; it is actually a **docs↔spec** pair, and the contract has no docs↔spec relation. Decision: map it to the contract's untyped `references` fallback — faithful to the contract today, no silent divergence. (Optional future: raise to governance as feedback if a typed docs↔spec relation is ever wanted; not required for this feature.)
