# Research — Governed auto-scaffold + one-command atlas

Four design decisions resolve the feature. The first three were ratified in the spec's
Clarifications session (2026-06-15); this document records rationale and rejected alternatives, plus
the one decision left to engineering judgment.

## D1 — Carry the derived manifest in-memory (no file written by default)

**Decision**: The scaffold produces a `WorkspaceManifest` object passed directly to the pipeline; the
domain manifest is resolved from the discovered authority path. No `synthesis.workspace.json` is
written anywhere by default.

**Rationale**: It is the strongest read-only guarantee (FR-013) and the cleanest expression of the
constitution's "generated, never authored" principle (V) — a written manifest is a hand-editable
artifact that rots into a competing source of truth. Inspection is served by the scaffold report
(FR-011); override by an operator-authored manifest (FR-010). It also dissolves the base-dir problem:
with no file, there is no "where does the file live" question — the authority path is passed
explicitly.

**Alternatives rejected**:
- *Write to the build work dir* — reuses the path-based CLI unchanged, but adds a throwaway file and
  still needs an explicit base; no real benefit over in-memory once the entry point accepts an object.
- *Write into the workspace* — most discoverable/editable, but writes into a consumer repo (weakens
  read-only) and reintroduces the base-dir coupling. Rejected for the default; the operator can still
  author their own manifest if they want a persistent, editable one.

## D2 — 1:1 member with merged multi-source ingestion

**Decision**: Exactly one workspace member per declared domain member (one index card per repo), but a
member's corpus is assembled by **merging** several ingestion sources: structure-aware specs (the
`speckit` adapter over `specs_dir`) + the declared decision records (the `doc` adapter over `adr_dir`,
ADR-forced) + (for a source repo) free-form docs.

**Rationale**: Resolves the FR-004 ↔ FR-007 tension directly. Strict 1:1 keeps the portal's
book-of-books model clean (one card per repo, matching the domain manifest exactly) while merged
ingestion gives each page the best available material: specs parsed *as specs* (not generic prose, as
a single `doc` adapter would do) and ADRs guaranteed to be ingested as ADRs even when `adr_dir` is not
a filename/path the `doc` adapter would auto-classify (e.g. a non-conventional decisions directory).
The stage-0 dry run confirmed a single `doc` adapter still yields shared-identifier edges, but it
treats specs as prose — weaker pages; merged ingestion is strictly better.

**Alternatives rejected**:
- *1:1, single adapter over the repo* — simplest, proven to still produce cross-repo edges, but specs
  become generic prose (lower-fidelity storybook) and ADR classification depends on directory naming.
- *Expand a repo into multiple members* — richest separation but breaks the clean 1:1 with the domain
  manifest and shows several cards per repo, muddying the book-of-books.

## D3 — Discover the authority by following `sources`

**Decision**: From any governed repo, locate the authority by: (a) if the repo itself owns
`.spec-arch-domain.yml`, use it; else (b) read the repo's `.spec-arch-governance.yml` and follow a
`sources` entry with `role: source` to the source repo, recursing with a visited-set cycle guard and a
small hop bound; (c) exhausted → ungoverned.

**Rationale**: This is the signal governance already publishes — `backend/.spec-arch-governance.yml`
carries `sources: [{id: docs, locator: ../docs, role: source}]`. Following it means the operator can
launch from *any* member (the source repo or a build repo) and reach the same authority — satisfying
SC-003 and the US1 "run from a build repo" acceptance scenario. `gov_config.RepoConfig` currently
drops `sources` (extra=ignore); adding a typed `sources` field is the only contract-read change needed.

**Alternatives rejected**:
- *Require launching from the source repo* — simplest but fails the "let any repo drive" expectation
  the operator naturally has, and the stage-0 friction showed this is exactly the assumption to avoid
  baking in.
- *Filesystem search for a domain manifest among siblings* — guesses at topology the governance files
  already declare; violates "no invention" (FR-009) and could bind the wrong authority.

## D4 — Base/authority decoupling (engineering judgment)

**Decision**: In `synthesize_atlas.main`, when scaffolding, set `base = authority dir` and read the
domain manifest from the authority; member paths in the derived manifest compose the domain `locator`
with each repo's declared sub-dirs, expressed relative to that base. The launch directory (`--from`,
default cwd) only seeds discovery; it does not have to equal the base. When no authority is found but a
hand-authored manifest is given, `base = manifest.parent` (today's behavior, unchanged).

**Rationale**: The domain manifest's `locator`s are already authored relative to the authority repo
(`docs: .`, `backend: ../backend`), so anchoring `base` at the authority makes the declared locators
resolve verbatim — no path rewriting, minimal change to the existing resolution code. It removes the
operator-visible base-dir constraint (FR-008) without inventing a new path convention.

**Alternatives considered**: absolute paths in the derived manifest (works, but noisier and couples
the in-memory object to one machine's layout); a separate `--domain-manifest` path flag (more surface
area than needed — the authority dir already implies it).

## Cross-cutting

- **No new dependencies.** `pyyaml` (for `sources`) and `pydantic` are already present.
- **Fixtures.** The existing `skill/tests/fixtures/governed/` (CORE/API/WEB) gains `sources:` pointers
  in the build repos' configs and explicit `specs_dir`/`adr_dir`, so discovery-from-build and merged
  ingestion are exercised on neutral data.
- **Ungoverned safety (SC-005).** When discovery returns `None` and no manifest is supplied, the
  command errors with a clear message and invents nothing; when a manifest *is* supplied on an
  ungoverned workspace, the code path is byte-for-byte today's.
