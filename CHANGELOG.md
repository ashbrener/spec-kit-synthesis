# Changelog

All notable changes to **spec-kit-atlas** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses [Semantic
Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Reads the governed citation slots** (spec 008) — atlas now recovers `derived_from`/`cites`
  edges directly from the declared front-matter slots (vocabulary.json@0.3.0 `citation_slots`,
  ARCH-ADR-000 Amendment 2), instead of only inferring them from shared prose. A build spec that
  declares `derived_from: [docs:002-architecture]` in `spec.md` front-matter now melds with that
  source feature **even when the slug never appears in the source's prose** (previously: no edge);
  `cites: [<NS>-ADR-NNN]` in `plan.md` attaches the decision. Slot edges are graded `declared` (the
  top evidence tier) and win dedup over inferred edges. Slot key names follow each repo's
  `citation_keys`; an unresolved slot mints no edge (reported). Vendored contract re-pinned to 0.3.0
  + drift-guarded. No new dependency; gates, single-repo, and no-slot workspaces unchanged.

- **Docs-authority capability signal** (spec 007) — a `source` repo (a docs repository with a
  specs dir, an ADR dir, and narrative folders) is now ingested **structure-aware**: its specs via
  the speckit adapter (distinct feature seeds), its ADRs as decisions, and its narrative via the doc
  adapter **excluding** the specs/ADR subtrees (no double-ingest). So build specs and the source
  specs they derive from finally **meld into shared capabilities** on a docs-authority workspace.
  Clusters are classified **capability / decision / background**: cited decisions render inline in
  their capability, uncited decisions gather in a Decisions appendix, narrative becomes an
  Overview/Background section — none masquerade as capabilities. Adds a path-prefix `exclude` on an
  ingestion source. No new signal or dependency; gates + build/standalone + ungoverned unchanged.

### Changed (earlier in this cycle)

- **The multi-repo portal is now ONE melded, capability-organized story** (spec 006), replacing the
  book-of-books. `speckit.atlas.map` reasons a single document over the merged workspace corpus,
  organized by **capabilities** (deterministically clustered over the cross-repo link graph — no
  external graph dependency), each woven across tiers: a functional narrative + per-tier technical
  disclosures (backend / frontend), every claim drilling to its owning repo.
- **Built vs planned** — capabilities and tiers are graded built / partial / planned (from code
  coverage + spec lifecycle); planned work renders faded.
- **Human-titled source tables** replace raw filename citation chips; a **hierarchical source index**
  (`catalog.html`, repo › feature › artifacts) replaces the edge-list atlas; nested navigation.
- **New diagram layouts** `sequence` (cross-tier request path) and `erd` (data model).
- The single-repo storybook (PAGE layer) and the fail-closed gates are unchanged.

## [0.1.0] — 2026-06-16

First public release — packaged as a spec-kit extension (`specify extension add atlas`).

### Added

- **`speckit.atlas.storybook`** — one repo → one faithful, interactive, plain-English
  whole-system architecture storybook (a single self-contained HTML file). The in-session agent
  reasons (extract → reconcile → compose); deterministic scripts carry parse, the fail-closed
  faithfulness gate (`verify.py`), and render. Every claim drills to its real source; a claim with
  no source cannot ship.
- **`speckit.atlas.map`** — a workspace of repos → a documentation portal (a storybook per
  repo) plus a verified `docs↔specs↔code` traceability atlas. Cross-repo links are fail-closed
  (`verify_links.py`): declared, shared-identifier, or literal-prose evidence only.
- **Drill-to-source** — every citation chip opens the actual spec/ADR/code content, copied into the
  HTML (markdown-it + Mermaid), resolving across related repos.
- **Governed-workspace reading** — conforms to the architecture-governance contracts as a documented
  format (no runtime dependency): typed citations (`derived_from`/`cites`/`implements`/`references`),
  bare `ADR-NNN` qualified by repo namespace, a declared `.spec-arch-domain.yml` as source-of-truth
  topology, and evidence tiers (`declared` > `identifier` > `prose`).
- **Governed auto-scaffold (one command, no manifest)** — on a governed workspace the atlas discovers
  the authority that owns `.spec-arch-domain.yml` (following a build repo's `sources` pointer),
  derives the workspace manifest in-memory from the declared signal, and runs the unchanged pipeline.
  Ungoverned workspaces are unchanged (a hand-authored manifest is still required).

[0.1.0]: https://github.com/ashbrener/spec-kit-atlas/releases/tag/v0.1.0
