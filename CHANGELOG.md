# Changelog

All notable changes to **spec-kit-synthesis** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses [Semantic
Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-06-16

First public release — packaged as a spec-kit extension (`specify extension add synthesis`).

### Added

- **`speckit.synthesis.storybook`** — one repo → one faithful, interactive, plain-English
  whole-system architecture storybook (a single self-contained HTML file). The in-session agent
  reasons (extract → reconcile → compose); deterministic scripts carry parse, the fail-closed
  faithfulness gate (`verify.py`), and render. Every claim drills to its real source; a claim with
  no source cannot ship.
- **`speckit.synthesis.atlas`** — a workspace of repos → a documentation portal (a storybook per
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

[0.1.0]: https://github.com/ashbrener/spec-kit-synthesis/releases/tag/v0.1.0
