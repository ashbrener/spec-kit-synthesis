# Feature Specification: Contract-Driven Capability Clustering

**Feature Branch**: `010-contract-driven-clustering`

**Created**: 2026-06-24

**Status**: Draft

**Input**: User description: "Make clustering a faithful, deterministic projection of the DECLARED governance graph — render the capability grain the source declares, never invent one. Membership rests on declared edges (+ same-feature); identifier/prose edges never confer membership on their own (esp. build↔build); declared-ancestor hub features are shared context, not catch-alls; ingest only source-of-truth artifacts."

## Context

Spec 009 replaced the connected-component clustering with source-anchored multi-membership, removing the single 495-fragment mega-cluster. A structural assessment on a real docs-authority workspace then showed the over-merge had **changed shape, not disappeared**: instead of one blob, the built work fused into **three near-duplicate ~380-fragment catch-all capabilities**, each swallowing nearly all build work, beside a couple of small planned ones. Three measured causes:

1. **Inferred edges confer membership.** Identifier-inferred `derived_from` edges — notably ~7 spurious *build↔build* edges minted from shared requirement/slug tokens — chain the build features so every coarse capability transitively absorbs them all.
2. **Coarse hub features anchor catch-alls.** A broad source document that many distinct build features declare `derived_from` (a functional/architecture/PRD overview) becomes the anchor of a giant capability instead of shared context.
3. **Non-source artifacts are ingested.** Repo-meta and archives (an archive directory, top-level agent/handoff/audit/standards files) become background "clusters" — noise.

The fix is architectural, not heuristic: **clustering must be a faithful, deterministic projection of the declared governance graph.** It renders the capability grain the source *declares* and never manufactures one. Where the declared grain is coarse, the output is faithfully coarse — that is a governance/authoring gap, handed to the writer, not patched by the reader.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inferred edges never collapse capabilities (Priority: P1)

A reader opens the portal for a workspace whose build features share incidental identifiers (common requirement codes, slugs). The capabilities reflect what the source **declared** — they do not silently fuse because two unrelated features happened to mention the same token.

**Why this priority**: This is the dominant measured cause of the catch-all collapse. Inferred (identifier/prose) edges are the weakest evidence rung; letting them confer membership is what chains everything together.

**Independent Test**: Build a corpus where two build features share an identifier (an inferred edge) but declare no governance relationship to each other; assert they do not become co-members of a capability, and no capability absorbs both via that inferred edge.

**Acceptance Scenarios**:

1. **Given** two build features joined only by an identifier-inferred edge (no declared slot between them), **When** clusters are built, **Then** neither is pulled into the other's capability by that edge.
2. **Given** a declared `derived_from`/`cites` edge, **When** clusters are built, **Then** it confers membership (declared evidence is trusted).
3. **Given** a workspace with declared slots, **Then** the capability membership is identical whether or not incidental identifier edges are present (inferred edges add no membership of their own).

---

### User Story 2 - Broad (hub) features render faithfully and are flagged, not re-shaped (Priority: P1)

A reader sees a broad reference document that many features cite rendered as the capability the **contract declares** — and where that makes a capability broad, the tool **flags it** as a governance signal ("broad — refine the source to split this capability"), rather than the reader silently inventing a finer split.

**Why this priority**: This is the faithfulness boundary in practice. The reader must not manufacture a grain the source does not declare; a broad capability is the honest signal that the docs need finer features. (Decided: strictly faithful — no reader-side hub demotion or splitting.)

**Independent Test**: Build a corpus where many distinct features declare `derived_from` one broad source feature; assert the capability is rendered as declared (the broad feature anchors, members are exactly its declared dependents) and is annotated as broad/hub — and that the reader applies no heuristic split or re-anchor.

**Acceptance Scenarios**:

1. **Given** a source feature that several others declare `derived_from`, **When** clusters are built, **Then** it is rendered as the declared capability (not split, not re-anchored) and carries an additive "broad (hub)" annotation naming how many distinct features declare it.
2. **Given** a source feature with no declared dependents, **When** clusters are built, **Then** it anchors its own capability (including planned, source-only ones).
3. **Given** the assessment workspace, **Then** the near-duplicate catch-alls disappear because inferred-edge contamination is removed (US1) — each capability's members are exactly its declared dependents; remaining breadth is faithful and flagged, not hidden.

---

### User Story 3 - Only source-of-truth artifacts are clustered (Priority: P2)

A reader's index is free of repo-meta and archive noise — agent instructions, resume/handoff notes, audit logs, writing standards, and archived drafts do not appear as capabilities or background clusters.

**Why this priority**: Folds in the long-standing ingestion-residue finding (Q3); it directly removes noise clusters that inflate the index.

**Independent Test**: Point ingestion at a tree containing an archive directory and top-level repo-meta files; assert those fragments are not ingested and produce no clusters.

**Acceptance Scenarios**:

1. **Given** an archive directory and top-level repo-meta files in a member, **When** the workspace is ingested, **Then** those files are excluded and form no clusters.
2. **Given** genuine source artifacts (specs, ADRs, narrative) in the same member, **When** ingested, **Then** they are unaffected (only the non-source residue is excluded).

---

### Edge Cases

- A workspace with **no declared slots at all** (un-governed / pre-citation): membership must still form sensibly — see the identifier-edge fork (Assumptions).
- A `derived_from` chain through several declared features (A→B→C): membership follows the declared chain deterministically and terminates.
- A feature that is **both** a declared hub (has dependents) **and** itself derives from a coarser feature: it is context for its dependents and a member of its own parent's context — handled by multi-membership without merging anchors.
- A cited ADR shared across capabilities: stays the spec-008/009 behaviour — attached to each citing capability (multi-member), never bridging them.
- Same-feature grouping (fragments of one feature) always cohere — this is structural, not inferred, and is never gated out.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Capability membership MUST be conferred only by (a) the governed **declared** citation edges (`derived_from`/`cites` slots) and (b) same-feature grouping (fragments sharing origin + feature key). 
- **FR-002**: Identifier-inferred and prose-inferred edges MUST NOT, on their own, confer capability membership. They may remain as supporting evidence/links elsewhere, but they do not place a fragment in a capability.
- **FR-003**: A build↔build identifier-inferred edge MUST never confer membership (the specifically unreliable case that chained the catch-alls).
- **FR-004**: The reader MUST render a broad/hub feature (one several others declare `derived_from`) as the capability the contract declares — it MUST NOT heuristically demote, re-anchor, or split it. The system MUST instead annotate such a capability with an additive, reviewable "broad (hub)" signal (e.g. the count of distinct features declaring it) so governance can refine the source grain.
- **FR-005**: A declared feature with no declared dependents MUST anchor its own capability, including planned (source-only) features.
- **FR-006**: The reader MUST NOT manufacture a capability grain the source does not declare; where the declared grain is coarse, the rendered capabilities are faithfully coarse (no heuristic splitting/merging/re-anchoring to "improve" the shape). The crisp cross-tier split is achieved only by governance declaring finer features.
- **FR-007**: Ingestion MUST exclude non-source-of-truth artifacts — archive directories and top-level repo-meta (agent instructions, resume/handoff notes, audit logs, writing standards, worktree notes) — so they form no fragments or clusters.
- **FR-008**: Clustering MUST remain deterministic and pure (identical inputs → byte-identical `ClusterSet`); no clock, randomness, or iteration-order nondeterminism.
- **FR-009**: Clustering MUST use only in-process stdlib logic over the typed graph — no external graph system, database, embeddings, or community detection.
- **FR-010**: Every membership MUST rest on a real declared edge or same-feature basis and carry reviewable evidence; nothing fabricated (fail-closed).
- **FR-011**: Existing classification (`capability`/`decision`/`background`) and deterministic ordering MUST be preserved; schema changes MUST be additive.
- **FR-012**: The cited-ADR behaviour (an ADR a capability's spec cites rides inside that capability; a shared ADR never bridges two capabilities) MUST be preserved, restricted to **declared** `cites` per FR-001.

### Key Entities *(include if feature involves data)*

- **Declared edge**: a governance citation slot (`derived_from`/`cites`) — the only relation that confers capability membership.
- **Evidence tier**: `declared` > `identifier` > `prose`; only `declared` (and structural same-feature) places a fragment in a capability.
- **Feature unit**: fragments sharing origin + feature key — the unit of membership.
- **Declared hub**: a feature with ≥1 declared dependent; shared context, not an anchor.
- **Anchor (leaf feature)**: a declared feature with no declared dependents; anchors one capability.
- **Source-of-truth artifact**: a spec/plan/tasks/ADR/narrative that is genuinely part of the documented system — as opposed to repo-meta/archive.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the assessment workspace, the three near-duplicate ~380-fragment catch-all capabilities are eliminated; each capability's members are exactly its declared dependents (no inferred-edge contamination).
- **SC-002**: No capability's membership depends on a build↔build identifier edge or any prose edge; removing those leaves the `ClusterSet` membership unchanged.
- **SC-003**: No capability is split, merged, or re-anchored by reader heuristics; broad/hub capabilities are rendered as declared and carry the additive "broad (hub)" annotation.
- **SC-004**: Repo-meta and archive artifacts produce zero clusters; the count of background noise clusters drops to genuine narrative only.
- **SC-005**: Re-running clustering on identical inputs yields byte-identical output.
- **SC-006**: 100% of memberships carry a declared-edge or same-feature evidence basis; 0 rest on inferred edges.
- **SC-007**: All existing reader tests pass; meld/render need no change (multi-membership already tolerated).

## Assumptions

The two design decisions are **resolved** (best-practice, faithful to the architecture) — no open forks:

- **Membership signal (decided):** declared edges + same-feature grouping confer membership; an identifier edge is admitted as membership **only for a source↔build pair** (a real spec→implementation refinement signal) and **never build↔build** (the measured noise); prose never confers membership. This keeps clustering working on un-governed / single-repo workspaces while removing the contamination.
- **Hub handling (decided — strictly faithful):** the reader does **not** demote, re-anchor, or split a broad/hub feature. It renders the declared grain as-is and **flags** broad capabilities (FR-004). De-coarsening into named cross-tier capabilities is achieved by governance declaring finer features — not by reader heuristics.
- **Same-feature grouping** confers membership unconditionally (structural, not inferred).
- The crisp cross-tier capability grain (uniting a backend feature with its frontend counterpart into one named capability) is a **governance/authoring** concern, not solved here; a note is handed to the writer session.
- Out of scope: UX (build-status fade, source-type color taxonomy, nav scaling) and packaging (Q5).
- The assessment that motivated this (post-#27, real docs-authority workspace: 3 catch-alls, spurious build↔build edges, cross-cutting ADRs, repo-meta residue) is the empirical basis; fixtures will encode each cause.
