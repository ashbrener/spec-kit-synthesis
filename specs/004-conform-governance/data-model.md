# Data model — Conform to arch-governance contracts

## LinkRel (changed)
The cross-repo relation enum, reconciled to the contract:
`derived_from` (spec→spec) · `cites` (spec/plan→adr) · `implements` (code→spec) ·
`supersedes` (adr→adr) · `references` (untyped fallback, incl. docs↔spec).
- Removed: `specified_by`. Renamed: `derives_from`→`derived_from`. Added: `cites`.
- Must equal `vendor/vocabulary.json` `relations` keys (drift test).

## ADR identifier (read model)
- **bare**: matches `^ADR-\d{3,}$` — repo-local; qualified at read time to `<namespace>-ADR-NNN`
  using the owning repo's `namespace` (from its `.spec-arch-governance.yml`). Never cross-matched bare.
- **qualified**: matches `^[A-Z][A-Z0-9]*-ADR-\d{3,}$` — cross-repo resolvable as-is.

## DomainManifest (new read model — validated against vendored domain.schema.json)
- `version: str`
- `members: [Member]`, each `{ name, role(source|build|standalone), namespace, locator }`.
- Cross-member uniqueness of `name`/`namespace` is a writer invariant (not re-enforced; trusted).

## Topology resolution (new)
A resolved view combining declared + presentation:
- structural fields (members, roles, namespaces, locators): **manifest if present**, else the
  reader's `synthesis.workspace.json` (fallback).
- presentation fields (title, description, theme, order): always from `synthesis.workspace.json`.
- precedence: manifest wins on overlapping structural fields; manifest has no presentation fields.

## Evidence tier (existing — `LinkEvidenceKind`)
`declared` (manifest/front-matter/config) > `identifier` (shared qualified id) > `prose` (text).
Every `LinkEdge` already carries one; manifest/config-derived edges MUST be `declared`.

## Untouched
`Fragment`, `FragmentCorpus`, `Claim`, `ArchitectureModel`, `DocumentModel`, `Block`, the verify
contracts — no changes. This feature only changes the cross-repo (`LinkRel`/`LinkGraph`) + topology
read path.
