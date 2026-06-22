# Feature Specification: Source-Anchored Capability Clustering

**Feature Branch**: `009-source-anchored-clustering`

**Created**: 2026-06-22

**Status**: Draft

**Input**: User description: "Source-anchored capability clustering — fix over-merge and singleton fragmentation (dogfood Q1/Q2). Re-model capability membership so capabilities map to source features and stay separable when a build artifact relates to several; attach decisions/background to the capability that cites them instead of leaving singletons; keep it deterministic, stdlib-only, fail-closed, evidence-backed."

## Context

The reader groups a federated workspace's fragments into **capabilities** — the sections of the melded story (spec 006). Today a capability is a *connected component* of the typed cross-repo link graph (strong relations only: `derived_from` / `cites` / `implements`). On a densely cross-cited docs-authority workspace this model fails in two opposite directions at once, both observed when dogfooding on a real workspace:

- **Over-merge (Q1):** a single build spec that legitimately relates to **two** source features bridges them; the transitive closure then cascades until nearly everything fuses into one cluster (observed ~495 fragments in a single cluster). Distinct capabilities can no longer be told apart.
- **Fragmentation (Q2):** decisions (ADRs) and narrative with no strong spec-edge fall out as lone singleton buckets — one cluster per ADR or per directory — so the index is littered with noise instead of capabilities.

The desired shape: capabilities **anchored to source features**, cohesive yet **separable** even when build artifacts span more than one, with decisions and background attaching to the capability they belong to rather than fragmenting.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bridging build artifacts no longer collapse capabilities (Priority: P1)

A reader opens the portal for a workspace where build specs honestly cite several source features. The index shows **one section per source capability**, each separable and recognisable — not one giant merged blob — even though some build artifacts contribute to more than one capability.

**Why this priority**: This is the defining defect (Q1). Without it the melded capability story is unusable on any realistically cross-cited workspace — the product's central promise (sections = capabilities) breaks.

**Independent Test**: Build a corpus where one build feature relates (via strong edges) to two distinct source features that are otherwise unconnected. Assert the result has two source-anchored capabilities, not one merged cluster; assert each source feature anchors exactly one capability.

**Acceptance Scenarios**:

1. **Given** source features S1 and S2 with no edge between them, **When** build feature B relates to both S1 and S2 via strong edges, **Then** S1 and S2 remain two separate capabilities (B does not fuse them into one).
2. **Given** a chain S1 ← B1 and S2 ← B2 where B1 and B2 share an identifier-only (`references`) link, **Then** S1 and S2 stay separate (weak relations never merge capabilities).
3. **Given** a workspace with N source features, **Then** the count of `capability`-kind clusters does not collapse toward 1 as build cross-citation density rises.

---

### User Story 2 - Decisions and background attach where they belong (Priority: P2)

A reader browsing a capability sees the decisions (ADRs) that capability's specs cite presented **within that capability**, not scattered as dozens of standalone single-ADR entries in the index.

**Why this priority**: This is Q2 (fragmentation). It directly determines whether the hierarchical index reads as a small set of meaningful capabilities or a noisy list of singletons.

**Independent Test**: Build a corpus where a spec in capability S1 cites ADR-A, and ADR-B is cited by nothing. Assert ADR-A is a member of S1's capability and does not form its own cluster; assert ADR-B remains an honest standalone `decision` cluster (it genuinely belongs to no capability).

**Acceptance Scenarios**:

1. **Given** a spec anchored to capability S1 that cites ADR-A, **When** clusters are built, **Then** ADR-A is a member of S1 (not a singleton `decision` cluster).
2. **Given** an ADR cited by no spec/plan, **Then** it remains its own honest `decision` cluster (not force-attached to an unrelated capability).
3. **Given** free-form narrative with no strong tie to any source feature, **Then** it remains `background` and is not fabricated into a capability.

---

### User Story 3 - Membership stays reviewable, deterministic, and honest (Priority: P3)

A maintainer auditing the output can see, for every fragment's placement, the evidence (which typed edge or feature grouping put it there), can re-run and get byte-identical output, and can trust that no membership was invented.

**Why this priority**: The whole pipeline is fail-closed and reproducible; a new membership model must preserve those guarantees or it cannot ship.

**Independent Test**: Run clustering twice on the same inputs and assert byte-identical `ClusterSet`; assert every non-anchor membership carries an evidence note naming the relation that placed it; assert no fragment appears in a capability without a real edge/feature basis.

**Acceptance Scenarios**:

1. **Given** identical inputs, **When** clustering runs twice, **Then** the serialized `ClusterSet` is byte-identical.
2. **Given** any fragment placed in a capability it does not anchor, **Then** an evidence note names the strong relation (or feature grouping) that placed it there.
3. **Given** a fragment with no feature key and no strong edge, **Then** it is reported as unclustered/background rather than attached to a capability.

---

### Edge Cases

- A build fragment relates to **multiple** source features → see the membership-model decision below (the defining design fork).
- A source feature with **no** dependents → remains its own (single-tier) capability, honestly.
- Two source features connected **only** through a chain of build artifacts (B derives from S1 and S2) → must NOT merge S1 and S2 (the over-merge that this feature removes).
- An ADR that cross-references another ADR → already handled (spec 008 B2 fix); must not re-introduce ADR↔ADR merging here.
- A cycle among build artifacts and sources → membership resolution must remain deterministic and terminate.
- A fragment reachable from a source feature only via a **weak** (`references`) edge → never joins that capability (over-merge guard preserved).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST anchor each capability to a single source feature; a source feature MUST anchor exactly one capability.
- **FR-002**: The system MUST NOT merge two source features into one capability solely because a build artifact relates to both — capabilities stay separable across bridging build artifacts.
- **FR-003**: The system MUST attach a build/decision fragment to a capability only via a **strong** relation (`derived_from` / `cites` / `implements`) or same-feature grouping; the weak untyped `references` relation MUST NOT confer capability membership.
- **FR-004**: The system MUST place a decision (ADR) cited by a capability's spec/plan within that capability rather than as a standalone singleton cluster.
- **FR-005**: A decision or narrative fragment with no qualifying tie to any source feature MUST remain an honest standalone `decision`/`background` cluster (or unclustered) — never force-attached.
- **FR-006**: The system MUST preserve the existing cluster classification (`capability` / `decision` / `background`, spec 007) and a deterministic, reproducible cluster ordering.
- **FR-007**: Every membership beyond a capability's own anchor feature MUST carry reviewable evidence naming the relation (or feature grouping) that placed it.
- **FR-008**: Clustering MUST remain deterministic and pure: identical inputs produce a byte-identical `ClusterSet`, with no dependence on wall-clock, randomness, or iteration-order nondeterminism.
- **FR-009**: Clustering MUST use only the in-process typed link graph and standard-library logic — no external graph system, graph database, embeddings, or new runtime dependency (carries forward the spec 006 FR-006 decision).
- **FR-010**: The system MUST NOT fabricate membership: a fragment may appear in a capability only when a real edge or feature grouping justifies it (fail-closed).
- **FR-011**: Changes to the membership model MUST be additive to the `CapabilityCluster` / `ClusterSet` schema so downstream meld/render consumers continue to function. Under multi-membership a fragment may be a member of several capabilities; the rendered **source content** MUST remain bundled once (on its source page) and be *cited* from each capability it serves — capabilities intentionally repeat the reference/membership, never duplicate the source body.
- **FR-012**: When a build fragment relates to more than one source feature via strong edges, the system MUST attach it (multi-membership) to **every** source capability it *directly* relates to (one-hop strong edge), deterministically and with evidence per placement. A fragment MUST NOT be silently dropped from a capability it genuinely serves, nor assigned to only one.

### Key Entities *(include if feature involves data)*

- **Capability**: a unit of the melded story, anchored to one source feature; has members (fragments grouped by tier/origin), a classification kind, and evidence. Maps to `CapabilityCluster`.
- **Source feature**: a feature belonging to a source-role origin; the anchor that names and seeds a capability.
- **Build artifact fragment**: a spec/plan/code/ADR fragment from a non-source origin that attaches to one or more capabilities via strong relations.
- **Strong relation**: `derived_from` / `cites` / `implements` — the only relations that confer capability membership.
- **ClusterSet**: the full deterministic output — the ordered capabilities plus anything genuinely unclustered.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a workspace with N source features, the number of `capability`-kind clusters is proportional to the number of source features that have content, and does NOT collapse to a single mega-cluster as build cross-citation density increases (the ~495-in-one-cluster pathology is eliminated).
- **SC-002**: No single capability contains fragments anchored to more than one source feature (anchors are 1:1 with capabilities).
- **SC-003**: The count of standalone single-ADR `decision` clusters drops to only those ADRs genuinely cited by nothing; every ADR cited by a capability's spec/plan appears within that capability.
- **SC-004**: Re-running clustering on identical inputs yields byte-identical output (determinism preserved).
- **SC-005**: 100% of non-anchor memberships have an evidence note explaining placement; 0 memberships exist without an edge/feature basis.
- **SC-006**: All existing reader tests continue to pass, and the meld/render output remains valid for both single-source and multi-source workspaces.

## Assumptions

- **Membership model (decided):** **multi-membership** — a build/decision fragment attaches to every source capability it *directly* relates to via a strong edge — because the melded story honestly shows a cross-cutting artifact under each capability it serves. Source content is bundled once and cited from each capability (no body duplication); see FR-011/FR-012.
- "Source-role" origins are already known to the clusterer (passed in as `source_origins`), unchanged from spec 006/007.
- Capability *naming and theming* remain the in-session agent's job (spec 006 FR-004a); this feature changes only deterministic membership, not naming.
- "Directly relates" means a one-hop strong edge between the build fragment and the source feature's fragments (no transitive closure across source features); ADRs reachable via a capability's spec/plan `cites` edge count as belonging to that capability.
- The B1/B2 ADR-edge fixes (spec 008 follow-up, PR #26) are in place, so the strong-edge inputs are already clean.
- Scope is the deterministic membership engine (`cluster.py`) and its consumers/tests; adapter residue (Q3), ADR `SourceType` (Q4, shipped), packaging (Q5), and governance items (G1–G3) are out of scope.
