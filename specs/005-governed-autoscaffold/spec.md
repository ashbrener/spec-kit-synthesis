# Feature Specification: Governed auto-scaffold + one-command atlas (the reader)

**Feature Branch**: `005-governed-autoscaffold`

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "On a governed workspace, the operator installs the synthesis plugin and runs ONE command with no hand-authored workspace manifest — synthesis derives the manifest from the governance contracts it already reads, then runs the existing atlas pipeline. In code only, no runtime dependency on the governance extension, read-only on consumer repos, ungoverned projects unchanged. Neutral examples only (CORE/API/WEB)."

## Overview

Today, producing a multi-repo portal requires the operator to hand-author a workspace manifest
(`synthesis.workspace.json`): list every member, pick each member's source path and ingestion
shape, and — because the declared-topology file is read only from the manifest's own directory —
know that the manifest must physically sit next to it. On a **governed** workspace, every one of
those facts is already declared by the governance contracts the reader consumes (the domain
manifest declares members/roles/namespaces/locators; each repo's governance config declares its
specs and decision-record locations). This feature removes the hand-authoring step for governed
workspaces: the operator runs one command and the reader derives the manifest from the declared
signal, then proceeds through the unchanged build pipeline.

This is a **reader-side convenience layer**, strictly additive in front of the existing stages.
It changes nothing about how pages are reasoned, how cross-repo links are graded, or how the
fail-closed verification gate behaves. An ungoverned workspace is wholly unaffected.

## Clarifications

### Session 2026-06-15

- Q: How is the auto-derived workspace manifest carried into the build pipeline? → A: In-memory
  (best architecture) — the derivation produces the manifest as an object passed directly to the
  pipeline; the domain manifest is resolved from the discovered authority path; no manifest file is
  written by default. Inspection is served by the hand-off note (FR-011), and override by an
  operator-authored manifest (FR-010).
- Q: How does a declared domain member map to ingestion when a source repo has specs AND ADRs AND
  docs? → A: 1:1 member with merged multi-source ingestion — exactly one workspace member per domain
  member (one index card per repo), but that member's corpus merges multiple sources: its specs
  ingested structure-aware, and its declared decision-record location ingested as decision records
  (plus free-form docs for a source repo).
- Q: Is a build repo's code ingested by default in the one-command run? → A: No — specs only by
  default (keeps the hands-off run fast and tractable); code ingestion is opt-in via an
  operator-authored manifest overlay.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One command on a governed workspace (Priority: P1) 🎯 MVP

An operator has a governed workspace: a source repo that owns the domain manifest, and one or
more build repos, each carrying its own governance config. They have installed the synthesis
plugin. From any one of those repos, they ask for the portal **without** writing a manifest.
The reader discovers the workspace's structure from the governance contracts, derives the set of
members and how to ingest each, and hands off to the normal build — producing a portal whose
topology matches what governance declares.

**Why this priority**: This is the entire value of the feature — "install and run, no manifest."
Without it the operator must still hand-author the manifest, which is the friction being removed.
Parts 2 and 3 are subsumed by making this story actually work.

**Independent Test**: In a governed fixture workspace (source `CORE` owning the domain manifest;
build `API`, `WEB`), invoke the portal build from any member with no manifest argument; assert a
portal is produced whose members, roles, and namespaces equal those declared in the domain
manifest, and that the operator supplied no manifest.

**Acceptance Scenarios**:

1. **Given** a governed workspace and no `synthesis.workspace.json`, **When** the operator runs the
   one-command build from the source repo, **Then** the reader derives a manifest covering exactly
   the declared members and proceeds into the normal adapt → reason → verify → render pipeline.
2. **Given** the same workspace, **When** the operator runs the build from a **build** repo (not the
   source), **Then** the reader still locates the source repo's domain manifest and derives the same
   member set — the launch location does not change the result.
3. **Given** a build whose derivation succeeded, **When** the portal is produced, **Then** each
   member's role and namespace match the domain manifest and are graded `declared`.

---

### User Story 2 - Derivation is faithful to what governance declares (Priority: P2)

The reader must build the manifest only from facts the governance files actually state — never
inventing a member, a path, or an ingestion location. Each member's source location comes from the
domain manifest's declared locator; what to ingest from that member (its specifications and its
decision records) comes from that repo's own governance config. The derivation is transparent: the
operator can see what was read and from where before any reasoning happens.

**Why this priority**: Faithfulness is the project's first principle; an auto-derived manifest that
guesses would poison the whole portal. This makes the convenience trustworthy.

**Independent Test**: Against the governed fixture, run only the derivation step and inspect its
output: assert every member maps to a declared domain member, each member's ingestion locations
equal the `specs_dir`/`adr_dir` declared in that repo's governance config, and a hand-off note
lists each member's role/namespace/locator and the per-repo locations read.

**Acceptance Scenarios**:

1. **Given** a domain manifest with members `CORE`/`API`/`WEB`, **When** derivation runs, **Then**
   the derived member set is exactly those three (no more, no fewer) with their declared locators.
2. **Given** a repo whose governance config declares a specifications location and a decision-record
   location, **When** that member is derived, **Then** its specifications are ingested and its
   decision records are ingested (so decision-record citations can later resolve).
3. **Given** an optional declared member whose repo is not present on disk, **When** derivation runs,
   **Then** that member is reported as skipped and the build continues coverage-honestly.
4. **Given** derivation completes, **When** the operator reviews the hand-off note, **Then** it
   states, per member, the role/namespace/locator taken as `declared` and the per-repo locations
   read — nothing is inferred silently.

---

### User Story 3 - Operator overrides and ungoverned fallback (Priority: P3)

A hand-authored manifest, when present, remains authoritative: it overlays presentation (titles,
descriptions, theme) and may add or adjust members on top of the derived set. And a workspace with
no governance signal behaves exactly as it does today — the operator is asked for a manifest; no
derivation is attempted.

**Why this priority**: Protects the two ends of the spectrum — power users who curate presentation,
and ungoverned projects that must keep working unchanged. Important but not the headline.

**Independent Test**: (a) With both a domain manifest and a partial hand-authored manifest present,
assert presentation comes from the hand-authored manifest while structural topology comes from the
declared signal. (b) In a workspace with neither a domain manifest nor any governance config,
assert the build behaves exactly as before (requires a manifest; no derivation).

**Acceptance Scenarios**:

1. **Given** a governed workspace **and** a hand-authored manifest supplying titles/theme, **When**
   the build runs, **Then** structure comes from the declared signal and presentation comes from the
   hand-authored manifest.
2. **Given** a hand-authored manifest that adds a member not in the domain manifest, **When** the
   build runs, **Then** that extra member is included alongside the derived members.
3. **Given** an ungoverned workspace with no manifest, **When** the build runs, **Then** the
   operator is told a manifest is required and no manifest is invented.

---

### Edge Cases

- **No authority found**: a workspace where no reachable repo owns a domain manifest → treated as
  ungoverned (fall through to requiring a hand-authored manifest), with a clear message.
- **Malformed domain manifest**: a present-but-invalid domain manifest → reported as an error; the
  reader falls back to its own record rather than deriving from bad data (consistent with existing
  manifest-validation behavior).
- **Launch from the source repo vs a build repo**: discovery must reach the same authority from
  either; a build repo points at its source, the source repo owns the manifest directly.
- **A repo's governance config omits a specifications or decision-record location**: derive only what
  is declared for that member; do not assume a conventional location that was not stated.
- **A declared member's repo is absent on disk**: if marked optional, skip with a warning; if
  required, the build stops (unchanged fail-closed behavior).
- **Cyclic or self-referential source pointers** between repos must not cause discovery to loop
  indefinitely.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The reader MUST, from any governed repo in a workspace, locate the authority repo that
  owns the domain manifest — using the launching repo's own governance config (its declared pointer
  to its source repo) when the launching repo is not itself the authority.
- **FR-002**: When the launching repo itself owns a domain manifest, the reader MUST use it directly
  without further discovery.
- **FR-003**: When no authority can be located, the reader MUST treat the workspace as ungoverned and
  fall through to the existing behavior (require a hand-authored manifest), emitting a clear message;
  it MUST NOT invent a manifest.
- **FR-004**: When an authority with a valid domain manifest is found, the reader MUST derive a
  workspace manifest containing exactly one member per declared domain member (a 1:1 mapping — one
  index card per repo).
- **FR-004a**: A derived member's corpus MUST be assembled by **merged multi-source ingestion**: a
  single member may draw from more than one source location within its repo (e.g. its specifications
  and its decision records), all stamped under that one member's origin. This reconciles the 1:1
  member mapping (FR-004) with a source repo's need to contribute specifications, decision records,
  and docs together.
- **FR-005**: For each derived member, the reader MUST take its source location, role, and namespace
  from the domain manifest's declarations, graded `declared`.
- **FR-006**: For each derived member, the reader MUST take what to ingest (its specifications and its
  decision records) from that repo's own governance config — using the declared specifications
  location and the declared decision-record location — so that decision-record citations can later be
  discovered and resolved. Specifications MUST be ingested structure-aware (not as generic prose), and
  the declared decision-record location MUST be ingested as decision records even when that location
  is not detectable by filename/path convention alone.
- **FR-007**: Ingestion shape MUST default by declared role: a source repo contributes its
  specifications, its decision records, and its free-form docs; a build repo contributes its
  specifications **only** by default. A build repo's code is **not** ingested by default — code
  ingestion is opt-in via an operator-authored manifest overlay (FR-010).
- **FR-008**: The reader MUST NOT require the operator to place the derived manifest beside the domain
  manifest — the location from which the build is launched MUST be decoupled from the location where
  the domain manifest lives. The domain manifest MUST be resolved from the **discovered authority
  path**, not from the derived manifest's location.
- **FR-009**: The reader MUST NOT invent any member, source location, or ingestion location that the
  governance files do not declare.
- **FR-010**: When a hand-authored manifest is present, it MUST override/overlay the derived one:
  presentation (titles, descriptions, theme) always comes from the operator's manifest, and the
  operator may add or adjust members on top of the derived set.
- **FR-011**: The reader MUST emit a reviewable hand-off note before reasoning, stating per member the
  role/namespace/locator taken as `declared` and the per-repo specifications/decision-record
  locations read, plus any members skipped (e.g. a missing optional repo).
- **FR-012**: The single-command experience MUST run the derivation as additive setup in front of the
  unchanged pipeline (adapt → per-member reasoning → fail-closed verification → render); the
  derivation MUST NOT alter any of those stages.
- **FR-013**: The reader MUST remain read-only on consumer repos. By default it writes **no**
  manifest file anywhere (the derived manifest is carried in-memory); the only writes remain the
  build's own working-directory artifacts and the rendered site (both outside the consumer repos).
  An operator MAY still author their own manifest, but the feature MUST NOT require or auto-write one
  into a consumer repo.
- **FR-014**: The feature MUST introduce no runtime dependency on the governance extension — the
  governance contracts are read as a documented format only.
- **FR-015**: An ungoverned workspace MUST behave exactly as before this feature (no derivation, no
  behavioral change).
- **FR-016**: Source, docs, tests, and fixtures MUST use neutral examples only (e.g. CORE/API/WEB) —
  never a real consumer, company, or namespace.

### Key Entities *(include if feature involves data)*

- **Workspace authority**: the repo that owns the domain manifest — the structural source of truth
  for the workspace's topology.
- **Domain manifest (declared topology)**: the registry of members, each with a role, namespace, and
  source locator. Read-only input; the basis of every derived member's structural facts.
- **Per-repo governance config**: a repo's own declaration of its namespace, its specifications
  location, its decision-record location, and (for a build repo) its pointer to its source repo.
- **Derived workspace manifest**: the in-memory manifest object the reader builds from the declared
  signal — the bridge between governance declarations and the existing build pipeline. Not written to
  disk by default; carried directly into the pipeline.
- **Hand-off note**: the reviewable, coverage-honest summary of what was derived and from where,
  emitted before any reasoning.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a governed workspace, an operator produces a correct multi-repo portal with **zero**
  lines of hand-authored manifest.
- **SC-002**: The derived member set exactly equals the declared domain members (100% match; no
  invented or missing members) across the governed fixtures.
- **SC-003**: The build succeeds identically whether launched from the source repo or from any build
  repo (same derived topology in every case).
- **SC-004**: For every governed workspace, each member's specifications and decision records are
  ingested from the locations its governance config declares, so that any decision-record citation
  present in the corpus can resolve (no citation is lost to a missed ingestion location).
- **SC-005**: An ungoverned workspace's build output is byte-for-byte unchanged from pre-feature
  behavior (pure additive enhancement).
- **SC-006**: Before any reasoning begins, the operator can read a hand-off note that accounts for
  every derived member's declared facts and per-repo locations, and lists every skipped member —
  with nothing inferred silently.
- **SC-007**: No real consumer/company/namespace name appears anywhere in source, docs, tests, or
  fixtures.

## Assumptions

- The governance contracts already consumed by the reader (the domain manifest and per-repo configs)
  are the authoritative, sufficient source for deriving structural topology and ingestion locations;
  this feature reads them, it does not extend or redefine them.
- A build repo's governance config declares a reachable pointer to its source repo (this is how
  discovery reaches the authority from a build repo); where it does not, the workspace is treated as
  ungoverned from that launch point.
- Presentation defaults (titles/descriptions) derivable from a member's name/role are acceptable when
  no hand-authored manifest supplies them; the operator can always override.
- The derived manifest is carried in-memory by default; no manifest file is written into any consumer
  repo. The domain manifest is resolved from the discovered authority path, decoupling the launch
  location from where the domain manifest lives.
- Lean plugin packaging (which files ship to consumers) is a sibling concern handled separately and
  is out of scope here.
- The existing per-member reasoning contract and the fail-closed verification gate are unchanged and
  are relied upon as-is.
