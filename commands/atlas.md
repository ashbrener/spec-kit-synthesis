---
name: speckit.synthesis.atlas
description: Synthesize a WORKSPACE of repositories into one interactive documentation portal — a faithful plain-English storybook per repo plus a verified docs↔specs↔code traceability atlas. Use when someone wants the whole-product story across many repos (a docs repo, the spec-kit specs that created it, and the backend/frontend repos that derive the code), drilling backward to specs and forward to code, all hostable as static HTML. NOT a single-repo renderer (that is the storybook command), NOT a dashboard.
---

# speckit-atlas — the documentation portal generator

You (the in-session agent) **are the reasoning engine** — the same as in the
`speckit-storybook` skill, applied across a *workspace* of repositories. Atlas is
the **book-of-books**: it runs the unchanged storybook engine once per member to
produce a faithful, plain-English page per repo, then connects those pages with a
**verified, fail-closed traceability atlas** (docs → specs → code).

Atlas is layered strictly ON TOP of the page engine (DESIGN PAGE-vs-SITE seam):
the SITE layer (portal index + atlas graph + cross-repo links) is purely
additive and **never touches per-page reasoning**. Every per-member page is built
exactly as `speckit-storybook` builds a single repo — same three phases, same
invariants, same `verify.py` gate. If you have not read the storybook skill, read
it first: atlas inherits all of its non-negotiable invariants verbatim.

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
SYN=.specify/extensions/synthesis
# …or running inside the synthesis repo itself (development):
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

- **`--work` (the IR dir, default `.synthesis-portal`)** — the per-member build
  cache: one subdir per member origin holding `corpus.json`, `locators.txt`, and
  the agent-written `architecture_model.json` + `document_model.json`, plus the
  workspace-wide `link_graph.json`. Reviewable, re-runnable, git-ignored.
- **`--out` (the site dir)** — the final static portal: `index.html` (the
  book-of-books), one `<origin>.html` per member, and `atlas.html` (the verified
  graph). Self-contained — no checkout, no auth, no server; host on Netlify/Vercel
  or open `index.html` directly.

The **epicenter is the manifest's directory**: every member `path` is resolved
relative to where `synthesis.workspace.json` lives (absolute paths also work). So
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
    --from . --work .synthesis-portal            # then re-run with --out site/ after reasoning
```

No manifest file is written (the derived manifest is carried in-memory); the reader stays read-only on
the consumer repos. An **operator overlay** is optional: pass a partial `synthesis.workspace.json`
alongside `--from` and it overlays presentation (title/description/theme always wins) and may add or
override members (e.g. enabling a build repo's code). An **ungoverned** workspace (no reachable
`.spec-arch-domain.yml`) still requires a hand-authored manifest — the reader invents nothing.

## The workspace manifest

For an ungoverned workspace (or to override the derived one), author a
`synthesis.workspace.{json,toml}` describing the members to federate:

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

## The pipeline (run in order)

```
manifest ─[stage 0 adapt: code]→ per-member origin-stamped corpus.json + locators.txt
         ─[reason EACH member: YOU]→ <origin>/architecture_model.json + document_model.json
         ─[discover links: code+YOU]→ link_graph.json  (declared + identifier; +prose by you)
         ─[verify_links: code, FAIL-CLOSED]→ (gate)
         ─[finish render: code]→ out/{index,<origin>…,atlas}.html
```

### Stage 0 — Adapt (deterministic; you just run it)

```
uv run --with pydantic --with pyyaml python "$SYN/skill/scripts/synthesize_atlas.py" \
    synthesis.workspace.json --work .synthesis-portal
```

This adapts every present member with its declared adapter and **origin-stamps**
its corpus (Phase A `with_origin`) so locators are globally unique across the
workspace — no cross-member collisions. It writes each member's `corpus.json` +
`locators.txt`, builds the candidate `link_graph.json` (declared + shared-identifier
edges), and prints a per-member hand-off brief. Missing optional members are
listed as skipped; a missing required member stops here.

### Reason each member (YOUR reasoning — the same three phases, per member)

For **each** member, do exactly what `speckit-storybook` does — extract →
reconcile → compose — but scoped to that member, **using ONLY that member's
locators** (`<work>/<origin>/locators.txt`). Write the two IR artifacts into the
member's work dir:

```
.synthesis-portal/<origin>/architecture_model.json   (reconcile)
.synthesis-portal/<origin>/document_model.json        (compose)
```

Write for a **general reader** (invariant #8): each page is the plain-English read
of its source, simpler than the markdown, every claim's source one click away. At
scale, fan out — one sub-agent (Task tool) per member — each returning that
member's IR. The members are orthogonal (disjoint sources, disjoint locators), so
this parallelizes cleanly.

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
  `synthesis.workspace.json` supplies presentation always and is the topology
  fallback when no manifest is present; the manifest wins on overlapping structural
  fields.
- **Evidence tiers** — every cross-repo fact is graded `declared` (manifest/config)
  > `identifier` (shared qualified id) > `prose` (text), surfaced on the atlas.

An **ungoverned** project (no `.spec-arch-domain.yml`, no per-repo config) produces
exactly the same output as before — these are purely additive reads.

### Verify + finish (deterministic gate, then render)

Re-run the same command **with `--out`**:

```
uv run --with pydantic --with pyyaml python "$SYN/skill/scripts/synthesize_atlas.py" \
    synthesis.workspace.json --work .synthesis-portal --out site/ [--theme theme.json]
```

It finishes only when every active member has a `document_model.json`; otherwise
it reprints the brief and names what's missing. On finish it runs the fail-closed
**`verify_links.py`** gate (ENDPOINTS_RESOLVE · EVIDENCE_PRESENT ·
EVIDENCE_GROUNDED) over the link graph and every member corpus. Non-zero ⇒ **stop
and fix** the flagged edges — never bypass. On pass it renders the portal: each
member's page, the coverage-honest `atlas.html`, and `index.html`. **Drill-to-source
(spec 003):** every member's cited spec/ADR files are rendered as bundled, beautified pages
under `sources/<origin>/`, and every citation chip — same-repo *or cross-repo* — drills into
the **actual source content of its owning repo** (content copied into the HTML). The atlas
remains the repo-to-repo navigation map. All pages share the single editorial design system —
there is no second visual system.

## What atlas is NOT

Not a single-repo renderer (that's `speckit-storybook` — atlas calls the same
engine per member). Not a dashboard, not a dependency graph of code, not an
inferred architecture. It federates faithful per-repo storybooks and connects them
with verified, evidence-bearing links — and stays honest about what it can't see.
