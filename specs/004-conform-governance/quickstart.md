# Quickstart — reading a governed project

A governed multi-repo workspace carries:
- a `.spec-arch-domain.yml` in the authority repo (the topology registry: members/roles/namespaces/locators), and
- a `.spec-arch-governance.yml` in each repo (its namespace + adr/spec dirs).

Build the portal as usual:

```
uv run python skill/scripts/synthesize_atlas.py synthesis.workspace.json --work .work --out site/
```

What changes when those files are present:
- **Topology** comes from `.spec-arch-domain.yml` (declared) — members, roles, namespaces, locators —
  with `synthesis.workspace.json` supplying titles/descriptions/theme (and serving as fallback if no
  manifest exists).
- **Decisions** written as bare `ADR-NNN` are read under each repo's configured namespace (no renames).
- **Citations** (spec/plan→decision) render as typed `cites` edges; code→spec as `implements`;
  spec→spec as `derived_from`; docs↔spec as `references`.
- **Every cross-repo edge** shows its evidence tier — `declared` (from the manifest/config) ranks
  above `identifier` (shared id) above `prose`.

On an **ungoverned** project (no manifest, no per-repo config), output is exactly as before — the
governed reading is a pure enhancement.
