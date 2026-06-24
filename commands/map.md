---
name: speckit.atlas.map
description: Synthesize a WORKSPACE of repositories into one interactive documentation portal — a faithful plain-English storybook per repo plus a verified docs↔specs↔code traceability atlas. Use when someone wants the whole-product story across many repos (a docs repo, the spec-kit specs that created it, and the backend/frontend repos that derive the code), drilling backward to specs and forward to code, all hostable as static HTML. NOT a single-repo renderer (that is the storybook command), NOT a dashboard.
---

# speckit-atlas — the documentation portal generator

You (the in-session agent) **are the reasoning engine** — the same as in the
`speckit-storybook` skill, applied across a *workspace* of repositories. Atlas produces **ONE melded,
capability-organized story** (spec 006) — not a book-of-books. Sections are capabilities (e.g.
"Authentication"), each woven across the tiers: a plain-English functional narrative from the source
layer, then per-tier technical detail (backend, frontend) each linking to its own repo; built work
renders solid, planned faded. The deterministic capability clustering (over the verified cross-repo
link graph) is the spine; a hierarchical source index replaces the old graph.

Atlas is the SITE layer over the page engine (DESIGN PAGE-vs-SITE seam): it reuses the same
`DocumentModel` renderer and the same fail-closed gates (`verify.py` over the merged corpus +
`verify_links.py` over the cross-repo edges), applied to ONE melded document. If you have not read the
storybook skill, read it first: atlas inherits all of its non-negotiable invariants verbatim.

## Inherited invariants (do not violate)

All five `speckit-storybook` invariants hold **per page**: faithfulness is
architectural (every claim carries a resolving `source_ref`); organized by
architecture not spec history; current-state only; fail-closed on gaps; stateless
(the IR is a per-run build cache). Atlas adds three of its own:

6. **The page is primary; the atlas is subordinate.** Each member's storybook is
   the plain-English read of its source — simpler than the markdown, every claim's
   source one click away (invariant #8, general reader). The atlas/graph serves
   navigation between pages; it never overrides or summarizes away a page.
7. **Cross-repo links are fail-closed too.** A cross-repo edge ships only with
   real evidence — declared in the manifest, a shared *qualified* identifier
   (FR-NNN / feature slug), or a literal prose quote. `verify_links.py` is the
   gate; a fabricated link cannot ship. Never edit the gate to pass.
8. **Coverage-honest.** Never imply a complete intent→docs→specs→code chain when
   the workspace only has part of it. The atlas states which roles are present and
   shows links only where evidence exists — never inferred.

## Toolchain

All scripts run via **`uv`** (never `pip`, never system Python). First locate the
extension root (`$SYN`), then run every script from there:

```
# installed as a spec-kit extension (the usual case):
SYN=.specify/extensions/atlas
# …or running inside the atlas repo itself (development):
SYN=.
```

Run scripts with their two deps provided ephemerally — this builds a correct,
throwaway env and **ignores any stale vendored `.venv`** (a `--dev` install copies
one whose paths are broken):

```
uv run --with pydantic --with pyyaml python "$SYN/skill/scripts/synthesize_atlas.py" …
```

(The scripts need only `pydantic` + `pyyaml`.) The examples below use `$SYN`.

## Two directories, one workspace

Atlas has exactly two filesystem roles, kept distinct:

- **`--work` (the IR dir, default `.atlas-portal`)** — the per-member build
  cache: one subdir per member origin holding `corpus.json`, `locators.txt`, and
  the agent-written `architecture_model.json` + `document_model.json`, plus the
  workspace-wide `link_graph.json`. Reviewable, re-runnable, git-ignored.
- **`--out` (the site dir)** — the final static portal: `index.html` (the
  book-of-books), one `<origin>.html` per member, and `atlas.html` (the verified
  graph). Self-contained — no checkout, no auth, no server; host on Netlify/Vercel
  or open `index.html` directly.

The **epicenter is the manifest's directory**: every member `path` is resolved
relative to where `atlas.workspace.json` lives (absolute paths also work). So
the manifest sits at the workspace root and points outward at sibling repos.

## One command on a governed workspace (auto-scaffold — spec 005)

On a **governed** workspace you do not author a manifest at all. Invoke with **no manifest** and a
`--from` pointing anywhere inside the workspace (the source repo *or* a build repo); the reader:

1. **discovers the authority** that owns `.spec-arch-domain.yml` — directly if the launch repo owns
   it, else by following that repo's `.spec-arch-governance.yml` `sources[role=source]` pointer;
2. **derives an in-memory manifest** from the declared signal — one member per declared domain
   member; each member's specs ingested structure-aware and its declared `adr_dir` as decision
   records (a `source` repo is read in a single `doc` pass: docs + specs + ADRs). Build-repo code is
   left out unless an operator manifest opts in;
3. **prints a scaffold report** (authority + per-member role/namespace/locator + the `specs_dir`/
   `adr_dir` read + skipped repos) — reviewable before any reasoning;
4. **proceeds through the UNCHANGED pipeline** (stage-0 adapt → per-member reasoning → fail-closed
   `verify_links.py` → render).

```
uv run --with pydantic --with pyyaml python "$SYN/skill/scripts/synthesize_atlas.py" \
    --from . --work .atlas-portal            # then re-run with --out site/ after reasoning
```

No manifest file is written (the derived manifest is carried in-memory); the reader stays read-only on
the consumer repos. An **operator overlay** is optional: pass a partial `atlas.workspace.json`
alongside `--from` and it overlays presentation (title/description/theme always wins) and may add or
override members (e.g. enabling a build repo's code). An **ungoverned** workspace (no reachable
`.spec-arch-domain.yml`) still requires a hand-authored manifest — the reader invents nothing.

## The workspace manifest

For an ungoverned workspace (or to override the derived one), author a
`atlas.workspace.{json,toml}` describing the members to federate:

```json
{
  "title": "Acme — Product Documentation Portal",
  "project_name": "Acme",
  "members": [
    { "origin": "docs",     "path": "../acme-docs",     "adapter": "doc",
      "role": "docs",  "title": "Product Docs",   "description": "The human-facing guide." },
    { "origin": "specs",    "path": "../acme-docs/specs","adapter": "speckit",
      "role": "spec",  "title": "Specifications",  "description": "The spec-kit specs behind the docs." },
    { "origin": "backend",  "path": "../acme-backend", "adapter": "code",
      "role": "code",  "title": "Backend",        "description": "The service that implements the specs.",
      "optional": true, "url": "https://github.com/acme/acme-backend.git", "pin": "<commit>" }
  ],
  "links": [
    { "src_origin": "docs", "src_locator": "<frag-id>", "dst_origin": "specs",
      "dst_locator": "<frag-id>", "rel": "references" }
  ]
}
```

Per-member fields (schema `WorkspaceMember`): `origin` (stable id; namespaces this
member's locators and names its page), `path`, `adapter` (`speckit`/`code`/`doc`),
`role` (`docs`/`spec`/`code`/`intent`), `title`/`description` (index card),
`pin`/`url` (reproducible / fetchable source), `optional`, `base_url` (published
"view source" host). Manifest-level: `title`, `project_name`, `theme`
(token overrides for the whole portal), and `links` (operator-declared edges).

**Optional members (multi-repo access).** Not every repo is always checked out. Set
`"optional": true` on a member and the build **skips it with a warning** when its
`path` is missing, instead of failing — so a contributor with only the docs repo
still gets a (coverage-honest) portal. A **required** member that is missing is
fail-closed (the build stops). Record a `url` + `pin` so the source *can* be
fetched for a complete build; checking it out is the operator's job (Phase F will
automate the fetch).

## The pipeline (run in order) — ONE melded story (spec 006)

The portal is **one capability-organized story**, NOT a book-of-books. You reason a single melded
pair over the MERGED workspace corpus; the spine is the deterministic capability clustering.

```
manifest ─[stage 0 adapt: code]→ per-member origin-stamped corpus.json + locators.txt
         ─[merge + cluster: code]→ merged_corpus.json + clusters.json + build_status.json + title_map.json
         ─[reason ONE MELD: YOU]→ architecture_model.json + document_model.json  (capabilities)
         ─[verify_links + verify: code, FAIL-CLOSED]→ (gates)
         ─[finish render: code]→ out/{index.html, catalog.html, sources/…}
```

### Stage 0 — Adapt + cluster (deterministic; you just run it)

```
uv run --with pydantic --with pyyaml python "$SYN/skill/scripts/synthesize_atlas.py" \
    --from . --work .atlas-portal
```

This adapts every present member (build-repo **code** included, for build-status), origin-stamps each
corpus, builds `link_graph.json`, **merges** the corpora, and clusters them into **capabilities**
(`clusters.json`) with a per-capability build status (`build_status.json`) and human source titles
(`title_map.json`). It prints the cluster spine + a hand-off brief.

### Reason ONE melded story (YOUR reasoning — across repos, by capability)

Write a SINGLE melded pair over the **merged** corpus (not one per repo):

```
.atlas-portal/architecture_model.json   (reconcile, across all repos)
.atlas-portal/document_model.json        (compose: one Section per capability)
```

Use `clusters.json` as the **section spine**. Each cluster carries a `kind` (spec 007):

- **`capability`** (has a spec/code) → a story **Section** (name it; you may group adjacent capability
  clusters into a theme like "Identity & Access", but never invent or split membership). A **cited**
  decision is already inside its capability cluster — render it **inline** within that capability.
- **`decision`** (an uncited ADR) → do NOT make it a capability section; gather all of these into a
  single **Decisions appendix** section near the end.
- **`background`** (only free-form narrative) → do NOT make it a capability section; fold it into a
  short **Overview / Background** section. Never auto-attach background to a capability.

For each capability `Section`:

- open with a plain-English **functional narrative** from the source layer — `Block`s with **no
  `tier`** (always visible, an exec reads only these);
- then **per-tier technical** `Block`s tagged `tier` (e.g. `"backend"`, `"frontend"`) — endpoints,
  data model, services for backend; the cross-tier integration (client → API → store) for frontend.
  The renderer groups these into per-tier disclosures;
- set `build_status` (built / partial / planned) on the section and on tier blocks from
  `build_status.json` — planned work renders faded;
- be **diagram-forward**: give each capability the diagrams that fit — an architecture-at-a-glance, a
  `sequence` (cross-tier request path), an `erd` (data model);
- cite the **merged corpus** (every claim resolves there; `verify.py` gates it) — each chip drills to
  its owning repo's source.

Write for a **general reader** (invariant #8): simpler than the markdown, every claim a click from
its source. At scale, fan out — one sub-agent (Task tool) per capability cluster — each returning its
`Section`(s); then assemble the one `document_model.json`. (An `architecture_model.json` over the
merged corpus carries the reconciled claims the doc's `claim_ids` resolve against.)

### Discover cross-repo links (deterministic + YOUR reasoning)

`synthesize_atlas.py` already emitted the **declared** edges (from the manifest,
trusted), the **shared-qualified-identifier** edges (deterministic — the same
`FR-NNN` / feature slug appearing in two members), and **`cites`** edges (a
spec/plan fragment and an ADR fragment sharing a qualified `<NS>-ADR-NNN`) into
`link_graph.json`. You may add **prose** edges: a literal cross-reference found in
one member's fragment naming another (the §5.4 evidence ladder's agent seam). Each
prose edge needs a typed `rel` — the relation set is the shared governance
vocabulary: `derived_from` (spec→spec) · `cites` (spec/plan→adr) · `implements`
(code→spec) · `supersedes` (adr→adr) · `references` (untyped fallback, incl.
docs↔spec) — both endpoints as origin-namespaced locators, `evidence_kind:
"prose"`, and the literal quote as `evidence`. Add only what the text actually
supports — the gate checks grounding, and an unsupported link is worse than a
missing one.

### Reading a governed project (an enhancement; ungoverned is unchanged)

When a project adopts the architecture-governance convention, atlas reads its
published contracts **as a documented format** — no runtime dependency on the
extension, read-only on the consumer repos:

- **Typed citations** — a plan that cites a decision renders as a typed `cites`
  edge; code→spec as `implements`; spec→spec as `derived_from` (the shared
  vocabulary, vendored + drift-guarded under `skill/scripts/vendor/`).
- **Bare `ADR-NNN`** — an unprefixed decision id is read under its repo's
  configured namespace (from `.spec-arch-governance.yml`) as `<namespace>-ADR-NNN`,
  with **no file renames**. A bare id stays repo-local; only the fully-qualified
  form resolves across a repo boundary.
- **Declared topology** — when the workspace root publishes a `.spec-arch-domain.yml`
  (validated against the vendored schema), it is the **source of truth** for
  structural topology (members/roles/namespaces/locators), graded `declared`. The
  `atlas.workspace.json` supplies presentation always and is the topology
  fallback when no manifest is present; the manifest wins on overlapping structural
  fields.
- **Evidence tiers** — every cross-repo fact is graded `declared` (manifest/config)
  > `identifier` (shared qualified id) > `prose` (text), surfaced on the atlas.

An **ungoverned** project (no `.spec-arch-domain.yml`, no per-repo config) produces
exactly the same output as before — these are purely additive reads.

### Verify + finish (deterministic gates, then render)

Once the melded `architecture_model.json` + `document_model.json` are in the work dir, re-run **with
`--out`**:

```
uv run --with pydantic --with pyyaml python "$SYN/skill/scripts/synthesize_atlas.py" \
    --from . --work .atlas-portal --out site/ [--theme theme.json]
```

It finishes only when the melded pair exists; otherwise it reprints the brief. On finish it runs BOTH
fail-closed gates — **`verify_links.py`** over the link graph + corpora, and **`verify.py`** over the
melded `document_model` against the **merged corpus** (every claim resolves, or it doesn't ship).
Non-zero ⇒ **stop and fix the model** — never bypass. On pass it renders:

- **`index.html`** — the single melded capability story (per-tier disclosures, build-status fading,
  human-titled source tables, nested nav);
- **`catalog.html`** — the hierarchical source index (repo › feature › artifacts), replacing the old
  edge-list atlas;
- **`sources/<origin>/…`** — drill-to-source pages; every citation chip drills into the **actual
  source content of its owning repo** (content copied into the HTML), across repos.

All pages share the one editorial design system — there is no second visual system, and there are no
per-repository storybooks.

## What atlas is NOT

Not a single-repo renderer (that's `speckit-storybook` — atlas calls the same
engine per member). Not a dashboard, not a dependency graph of code, not an
inferred architecture. It federates faithful per-repo storybooks and connects them
with verified, evidence-bearing links — and stays honest about what it can't see.
