# Quickstart — one command on a governed workspace

A governed multi-repo workspace carries:
- a `.spec-arch-domain.yml` in the authority (source) repo — the topology registry
  (members / roles / namespaces / locators), and
- a `.spec-arch-governance.yml` in each repo — its namespace, `specs_dir`, `adr_dir`, and (for a build
  repo) a `sources:` pointer to its source repo.

## Before (today)

Hand-author a `synthesis.workspace.json`, know it must sit beside the domain manifest, then:

```
uv run python skill/scripts/synthesize_atlas.py synthesis.workspace.json --work .work --out site/
```

## After (this feature) — no manifest

From **any** repo in the workspace (the source repo *or* a build repo), with the plugin installed:

```
# launched anywhere inside the workspace
uv run python skill/scripts/synthesize_atlas.py --from . --work .work --out site/
```

or, via the skill, simply invoke `speckit-atlas` with no manifest argument.

The reader:
1. **discovers the authority** — if the current repo owns `.spec-arch-domain.yml` it is the authority;
   otherwise it follows this repo's `sources:` pointer to the source repo.
2. **derives the manifest in-memory** — one member per declared domain member; each member's specs are
   ingested structure-aware and its declared `adr_dir` as decision records; a source repo also
   contributes free-form docs. Build-repo code is left out unless you opt in.
3. **prints a scaffold report** — for example:

   ```
   scaffold: authority = <source repo> (owns .spec-arch-domain.yml)
     CORE   source  ns=CORE  locator=.          specs=specs  adr=docs/adr     → specs (speckit) · ADRs (doc) · docs (doc)
     API    build   ns=API   locator=../api     specs=specs  adr=docs/adr     → specs (speckit)
     WEB    build   ns=WEB   locator=../web     specs=specs  adr=docs/adr     → specs (speckit)
   ```

4. **hands off to the unchanged pipeline** — adapt → per-member reasoning → fail-closed
   `verify_links.py` → render. The portal, atlas, evidence tiers, and drill-to-source behave exactly
   as for a hand-authored manifest.

## Operator override (optional)

If you want to curate presentation or add a member (e.g. ingest a build repo's code), author a partial
`synthesis.workspace.json` and pass it — it overlays the derived manifest:

```
uv run python skill/scripts/synthesize_atlas.py synthesis.workspace.json --from . --work .work --out site/
```

Your titles/descriptions/theme win; your extra members are added; your overrides (including enabling
code on a build repo) apply on top of the derived base.

## Ungoverned workspace

No `.spec-arch-domain.yml` reachable and no manifest supplied → the reader tells you a manifest is
required and invents nothing. Supplying a hand-authored manifest works exactly as it does today —
this feature changes nothing for ungoverned projects.
