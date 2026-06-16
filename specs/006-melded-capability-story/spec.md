# Feature Specification: Melded capability story (the SITE layer, re-architected)

**Feature Branch**: `006-melded-capability-story`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Re-architect the multi-repo portal from a book-of-books (one isolated storybook per repo) into ONE melded, capability-organized architecture story — woven across tiers, build-status aware, diagram-forward, with a hierarchical source index. The single-repo storybook engine and the fail-closed gates are unchanged. Neutral examples only (CORE/API/WEB)."

## Overview

Today the multi-repo portal is a **book-of-books**: each repository is reasoned in isolation into
its own storybook, then an index and an edge-list graph are added on top. A reader gets three
parallel stories and a filing-cabinet graph — they never see *the system*, only its repositories.

This feature re-architects the **SITE layer** so the portal is **one melded story organized by
capability**, not by repository. Each section is a capability (e.g. "Authentication", "Reporting")
woven across the tiers: a plain-English functional narrative from the source layer, then technical
detail from each build tier, each linking back to its own repository's content. Built work renders
solid; planned work renders faded. A hierarchical source index replaces the useless graph.

The **PAGE layer** (the single-repo storybook engine) and the **fail-closed faithfulness gates**
(`verify.py` / `verify_links.py`) are unchanged. The capability spine is the existing cross-repo
traceability graph, clustered **deterministically in code** — there is no dependency on any external
graph system, knowledge-graph tool, graph database, or embeddings linker, and no new runtime
dependency. A fabricated edge or capability must remain impossible.

## Clarifications

### Session 2026-06-16

- Q: What decides a capability section's boundary (granularity)? → A: Deterministic clustering fixes
  membership (which fragments belong together, via the graph); the agent then groups related clusters
  into a **named theme** section (e.g. "Identity & Access") and may merge adjacent clusters for
  readability, but **never fabricates membership** and never splits a cluster's traceability. A
  capability name is the agent's theme name, anchored to the underlying source feature(s).
- Q: What shape should the melded story take? → A: **One self-contained HTML page** — capabilities as
  sections, with a persistent nested in-page navigation; drill-to-source remains separate pages.
  (Consistent with the single-repo storybook; fully self-contained/offline.)
- Q: At what level is "built vs planned (faded)" applied? → A: **Per capability AND per tier** — a
  capability carries an overall grade, and each tier disclosure (e.g. backend / frontend) carries its
  own; fading applies at that block level (not per individual claim). A capability may be
  functionally built yet have a planned frontend tier.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One melded capability story (Priority: P1) 🎯 MVP

A reader opens the portal and gets **one** architecture story, organized by capability. Each
capability section opens with a plain-English functional narrative (what it is, how it works), then
offers per-tier technical detail — a backend disclosure (endpoints, data model, services) and a
frontend/integration disclosure (how the client calls the API across tiers) — every claim drilling
into the owning repository's actual source. The three separate per-repository storybooks are gone.

**Why this priority**: This is the entire re-envisioning — "one story, not three," woven across
tiers. Without it nothing else matters; with it alone the portal already delivers the headline value.

**Independent Test**: On a governed multi-repo fixture (a `source` repo + `build` repos), build the
portal and assert it produces a single story whose sections are capabilities (not repositories), each
section contains functional content sourced from the source layer and per-tier technical content
sourced from the build layers, and the standalone per-repository storybooks are not produced.

**Acceptance Scenarios**:

1. **Given** a workspace whose source feature is derived-from by build specs across repos, **When**
   the portal builds, **Then** those related fragments appear together in one capability section, not
   split across three repository stories.
2. **Given** a capability section, **When** a reader reads only the top (functional) layer, **Then**
   they understand what the capability does without any repository or tier detail.
3. **Given** a capability section, **When** the reader expands the backend tier, **Then** they see
   that tier's technical detail (endpoints / data model / services) sourced from and linking to the
   backend repository; expanding the frontend tier shows the cross-tier integration likewise.
4. **Given** any claim in the story, **When** the reader follows its source, **Then** it drills into
   the actual rendered content of the owning repository (faithfulness preserved; gate unchanged).
5. **Given** the build completes, **When** the output is inspected, **Then** there are no standalone
   `<repo>.html` per-repository storybooks (the book-of-books is replaced).

---

### User Story 2 - Built vs planned, at a glance (Priority: P2)

The story shows **what exists** versus **what is intended**: capabilities and claims backed by real
code render solid; specced-but-not-yet-built content renders faded with a clear "planned" marker, so
a reader instantly sees the difference between the system as built and as designed.

**Why this priority**: A core part of the vision ("enriched by what has been built or is to be built,
faded"). It turns the story from a flat description into a build-aware map, but the story is readable
without it.

**Independent Test**: On a fixture where one capability is implemented in code and another is
specced-only, assert the first is graded built and the second planned, and that the rendered output
visibly distinguishes them (a planned marker + faded treatment).

**Acceptance Scenarios**:

1. **Given** a capability whose spec is backed by code, **When** rendered, **Then** it is graded
   **built** and rendered solid.
2. **Given** a capability that is specced-only (no implementing code, tasks incomplete), **When**
   rendered, **Then** it is graded **planned** and rendered faded with a marker.
3. **Given** a capability partly built, **When** rendered, **Then** it is graded **partial** and the
   built and planned parts are distinguished within it.
4. **Given** build status, **When** derived, **Then** it uses **both** code coverage (code backing a
   claim) and spec lifecycle (artifact presence + task-checkbox completion) — never inventing a status
   the evidence does not support.

---

### User Story 3 - Hierarchical source index + navigation (Priority: P3)

Instead of an edge-list graph, the reader gets a **navigable tree** — repository › feature (human
title) › its artifacts (spec, plan, tasks, contracts, data-model, the decisions it cites) — every
entry linking to the rendered source. And a **persistent, nested navigation** lets the reader move
across large capability sections and their tiers without losing place.

**Why this priority**: Makes a large melded story navigable and gives a genuinely useful reference
surface, replacing the graph that was "pretty useless." Valuable but secondary to the story itself.

**Independent Test**: Build the portal and assert (a) the graph atlas page is replaced by a tree
grouping artifacts under repository → feature (with a human title) → artifact kind, each linking to
drill-to-source; (b) a persistent nested navigation lists capabilities and their tiers.

**Acceptance Scenarios**:

1. **Given** the corpus, **When** the index renders, **Then** it is a tree of repository → feature
   (human title) → artifacts, deterministic from the corpus structure (no reasoning).
2. **Given** a feature in the index, **When** displayed, **Then** it shows a human-readable title, not
   a bare folder id, and each artifact entry drills to its rendered source.
3. **Given** a long story, **When** the reader scrolls, **Then** a persistent nested navigation tracks
   position across capabilities and their tiers.

---

### User Story 4 - Diagram-forward capabilities (Priority: P4)

Every capability carries the diagrams that fit it — an architecture-at-a-glance, a request/data flow
across tiers (client → API → store), and a data model — rendered with the existing semantic animated
layouts, extended where a needed shape (cross-tier sequence, entity/data-model) isn't covered.

**Why this priority**: Dramatically improves comprehension and was explicitly called out ("very
little" diagramming today), but the story is still faithful and readable without it.

**Independent Test**: On a capability whose sources describe a cross-tier call and a data model,
assert the composed section includes a flow diagram and a data-model diagram using appropriate
layouts, and that any newly added layout renders and animates within the existing renderer.

**Acceptance Scenarios**:

1. **Given** a capability with a cross-tier request path in its sources, **When** composed, **Then**
   the section includes a flow/sequence diagram of that path.
2. **Given** a capability with a data model in its sources, **When** composed, **Then** the section
   includes a data-model diagram.
3. **Given** the renderer's layout set is insufficient for a needed shape, **When** extended, **Then**
   the new layout renders, animates, and degrades safely (reduced-motion / print) like the existing
   ones.

---

### Edge Cases

- **Sparse traceability** (build specs don't cite ADRs / few `derived_from` edges): clustering falls
  back to shared FR-identifiers and feature-slug similarity; a fragment that joins no cluster is
  surfaced honestly (e.g. an "Other / unclustered" section), never dropped or force-fit.
- **A capability spanning only one tier** (source-only, or build-only): render what exists; do not
  fabricate the missing tiers — show only the tiers with real content.
- **Ungoverned workspace** (no graph signal): the meld degrades to clustering by shared identifiers /
  feature-slug; if even that yields nothing, fall back to a per-feature organization rather than
  per-repo silos.
- **Conflicting build signals** (coverage says built, tasks incomplete — or vice versa): grade
  **partial** and state the tension rather than silently picking one.
- **No code ingested** for a build repo: build status falls back to lifecycle only; planned/built is
  still derivable from artifacts + task checkboxes, with reduced confidence noted.
- **Two features with the same number in different repos**: kept distinct by repository (no
  cross-repo collision), consistent with the bare-ADR repo-locality rule.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The SITE layer MUST produce ONE melded story whose top-level sections are capabilities,
  not repositories, rendered as a **single self-contained HTML page** (capabilities as sections);
  drill-to-source remains separate pages. Self-contained/offline, consistent with the storybook.
- **FR-002**: Each capability section MUST weave the tiers: a functional narrative from the source
  layer (the always-visible layer), plus per-tier technical disclosures (one per build tier) revealed
  on demand.
- **FR-003**: Every claim MUST link to the actual source content of its owning repository
  (drill-to-source), across repositories, exactly as today.
- **FR-004**: The capability spine MUST be derived by **deterministic clustering** of the existing
  typed, evidence-graded cross-repo link graph — connected components seeded by source features,
  falling back to shared FR-identifiers / feature-slug where graph edges are sparse. Clustering fixes
  **membership** (which fragments belong together); it is reproducible across runs.
- **FR-004a**: The in-session agent groups the deterministic clusters into **named theme sections**
  (e.g. "Identity & Access") and MAY merge adjacent clusters for readability, but MUST NOT fabricate
  membership and MUST NOT split a cluster's traceability. A capability's name is the agent's theme
  name, anchored to its underlying source feature(s).
- **FR-005**: The in-session agent writes the woven narrative; the **fail-closed gates are unchanged**
  and a claim/edge with no resolving source still cannot ship.
- **FR-006**: The feature MUST introduce **no dependency** on any external graph system,
  knowledge-graph tool, graph database, or embeddings linker, and **no new runtime dependency**;
  clustering MUST be in-repo deterministic code.
- **FR-007**: The standalone per-repository storybooks MUST be replaced by the single melded story;
  drill-to-source pages MUST be retained.
- **FR-008**: Build status MUST be graded and rendered at **two levels — per capability AND per tier**
  (each tier disclosure carries its own grade): **built / partial / planned**, built solid and planned
  faded with a marker. Fading applies at the capability/tier block level, not per individual claim. A
  capability may be functionally built yet have a planned tier.
- **FR-009**: Build status MUST be derived from BOTH code coverage (a claim backed by real code) AND
  spec lifecycle (artifact presence + tasks-checkbox completion); conflicting signals → **partial**
  with the tension surfaced; status MUST never be asserted beyond the evidence.
- **FR-010**: Source citations MUST render with **human-readable titles** (feature title from its spec
  heading + artifact kind + owning repository), derived deterministically, presented as a per-section
  **sources table** ([Title | Artifact | Repo | link]); raw machine filenames MUST NOT be the
  primary label.
- **FR-011**: The portal MUST include a **hierarchical source index** — repository › feature (human
  title) › artifacts (spec, plan, tasks, contracts, data-model, cited decisions) — replacing the
  edge-list graph page; built deterministically from the corpus structure, each entry drilling to
  source.
- **FR-012**: The portal MUST provide a **persistent, nested navigation** spanning capabilities and
  their tiers (replacing the flat scrollspy), so a reader can move across large sections.
- **FR-013**: The compose phase MUST be **diagram-forward**: each capability includes the diagrams
  that fit it (architecture-at-a-glance, cross-tier request/data flow, data model), using the
  renderer's semantic animated layouts.
- **FR-014**: Where the existing layout set cannot express a needed shape (notably cross-tier sequence
  and entity/data-model), the renderer MUST be extended with a layout that renders, animates, and
  degrades safely (reduced-motion / print) consistent with the existing ones.
- **FR-015**: An **ungoverned or sparse** workspace MUST still produce a coherent melded (or, failing
  any clustering signal, per-feature) story rather than reverting to per-repository silos; unclustered
  fragments MUST be surfaced honestly, never dropped.
- **FR-016**: The PAGE-layer (single-repo storybook) reasoning contract MUST remain unchanged.
- **FR-017**: Source, docs, tests, and fixtures MUST use neutral examples only (CORE/API/WEB) — never
  a real consumer, company, or namespace.

### Key Entities *(include if feature involves data)*

- **Capability**: a unit of the system spanning tiers (e.g. "Authentication") — the spine of one
  story section. Derived from a cluster of related fragments; carries a human name, a build status,
  and per-tier content.
- **Capability cluster**: the deterministic grouping of fragments (a source feature + build specs that
  derive from it + cited decisions + implementing code) produced from the link graph.
- **Tier layer**: within a capability, the content drawn from one layer/repository (functional/source,
  backend, frontend/integration), each with its own sources and disclosure.
- **Build status**: built / partial / planned, with the evidence behind the grade (coverage and/or
  lifecycle).
- **Source reference (human-titled)**: a citation carrying a human title + artifact kind + owning
  repository, in addition to its resolving locator.
- **Source index node**: a node in the hierarchical tree (repository → feature → artifact).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The portal renders as **one** story whose sections are capabilities; **zero** standalone
  per-repository storybooks are produced.
- **SC-002**: For a capability whose sources span multiple repositories, **100%** of those related
  sources appear within that single capability section (none stranded in a separate repository story).
- **SC-003**: A reader can determine, for every capability, whether it is built / partial / planned
  from the rendered output alone.
- **SC-004**: **No** citation is shown only as a raw machine filename; every source carries a
  human-readable title in a sources table.
- **SC-005**: The reference surface is a hierarchical tree (repo → feature-title → artifacts) with
  **no** edge-list graph page remaining.
- **SC-006**: Capability clustering is **deterministic and reproducible** — the same inputs produce the
  same clusters across runs — and **no external graph system or new runtime dependency** is
  introduced.
- **SC-007**: Faithfulness is preserved end-to-end: every shipped claim and cross-repo edge resolves
  to real source (the gates pass), and no fabricated capability/edge can ship.
- **SC-008**: Each capability with a cross-tier flow and/or a data model in its sources renders at
  least one fitting diagram.
- **SC-009**: No real consumer/company/namespace name appears in source, docs, tests, or fixtures.

## Assumptions

- The cross-repo link graph already produced (typed, evidence-graded `derived_from` / `cites` /
  `implements` / `references`) is a sufficient substrate for capability clustering; this feature
  consumes it, it does not replace the link-discovery contract.
- Deterministic clustering (connected components / union-find over the small typed graph) is adequate
  at workspace scale; no graph library or service is needed (minimal-deps principle: pydantic + pyyaml
  only).
- Build-repo **code is ingested** as part of the meld (for coverage-based build status); where it
  isn't, build status degrades to lifecycle-only with reduced confidence.
- Human titles are derivable deterministically from each feature's spec heading / frontmatter; where a
  title is genuinely absent, the feature id is used as a clearly-marked fallback.
- The meld supersedes the book-of-books presentation of spec 002; the per-page (PAGE-layer) engine and
  its `verify.py` gate are reused unchanged, and `verify_links.py` continues to gate cross-repo edges.
- An external knowledge-graph tool may still be used by an operator for *ad-hoc exploration* of the
  same corpus, but is explicitly NOT a dependency of this faithful generator.
