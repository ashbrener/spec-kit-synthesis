# Research — Conform to arch-governance contracts (the reader)

## Decision 1 — docs↔spec edge → `references` (resolved clarification)
- **Decision**: map the reader's current docs↔spec edge to the contract's untyped `references`.
- **Rationale**: the contract (vocabulary 0.2.0) has no docs↔spec relation; `implements` is code→spec,
  `derived_from` is spec→spec. `references` is the honest untyped fallback — no silent divergence.
- **Alternatives**: `derived_from` (stretches a spec→spec verb to docs→spec); a vocabulary addition
  (contract feedback — deferred, not needed now).

## Decision 2 — LinkRel reconciliation
- **Decision**: `LinkRel` = `derived_from`, `cites`, `implements`, `supersedes`, `references`.
  Rename `derives_from`→`derived_from`; drop `specified_by` (docs↔spec now → `references`); **add
  `cites`** (spec/plan→adr); `supersedes`/`references` unchanged.
- **Rationale**: match the authoritative `vocabulary.json` exactly; `cites` is the citation edge the
  governance layer produces — without it the citation graph is unreadable.
- **Alternatives**: keep the local dialect (rejected — the correctness blocker).

## Decision 3 — bare `ADR-NNN` qualified by repo namespace
- **Decision**: recognise bare `ADR-NNN` (`^ADR-\d{3,}$`) and qualify with the owning repo's
  namespace from its `.spec-arch-governance.yml` → `<namespace>-ADR-NNN`. Keep matching the
  fully-qualified form. A bare id is **repo-local** — never matched across a repo boundary; only the
  qualified form resolves cross-repo.
- **Rationale**: vocabulary 0.2.0 Amendment 1 — adoption with zero renames; prevents false
  cross-repo matches between two repos that both have `ADR-001`.

## Decision 4 — topology precedence (per INTEGRATION.md)
- **Decision**: when `.spec-arch-domain.yml` is present and valid (against the vendored
  `domain.schema.json`), it is the source of truth for **members, roles, namespaces, locators**.
  `synthesis.workspace.json` stays the **presentation overlay** (titles/descriptions/theme) always
  and the **topology fallback** when no manifest is present. Manifest wins on overlapping structural
  fields; the manifest carries no presentation.
- **Rationale**: one source of structural truth; ungoverned projects keep working unchanged.

## Decision 5 — vendoring + drift guard (ARCH-ADR-000 §8)
- **Decision**: vendor pinned copies of `vocabulary.json`@0.2.0 + `domain.schema.json` under
  `skill/scripts/vendor/`; a test asserts the reader's relation/role/kind/evidence enums equal the
  vendored copy and that the manifest validates against the vendored schema.
- **Rationale**: durable conformance, no runtime dependency; drift fails CI loudly.

## Decision 6 — YAML dependency
- **Decision**: add `pyyaml` (governed configs/manifest are YAML). Generic parser, not a dependency
  on the extension. Recorded in plan Complexity Tracking.

## Decision 7 — evidence tiers (already modelled)
- **Decision**: reuse the existing `LinkEvidenceKind` (`declared`/`identifier`/`prose`); tag
  manifest/config-derived facts `declared`, shared-qualified-identifier matches `identifier`, prose
  cross-refs `prose`. Mostly present — ensure manifest/config edges are tagged `declared`.
