---
name: speckit.atlas.storybook
description: Synthesize a project's scattered spec-kit specs into ONE faithful, beautiful, interactive whole-system architecture storybook (HTML). Use when someone wants a single plain-English "here is how this whole system is built" document generated from a repo's specs/ folders — for onboarding an engineer, briefing an evaluator, or seeing the de-fragmented current-state architecture. NOT a dashboard, NOT a per-spec renderer.
---

# spec-kit-atlas — the architecture storybook generator

You (the in-session agent) **are the reasoning engine.** This skill does not
shell out to another model. Your job is to read a project's spec-kit specs and
*synthesize* — reconcile many overlapping, evolving, sometimes-contradictory
specs into one **current-state** architecture narrative — then render it as a
self-contained interactive HTML storybook.

The hard part is **reconciliation** (what is true *now*) and **faithfulness**
(never assert architecture the specs don't support). Deterministic Python
scripts under `scripts/` carry the parsing, the fail-closed faithfulness gate,
and the renderer; *you* carry the reasoning between them. Read `DESIGN.md` at the
repo root for the full rationale — especially §3 (the four phases), §5
(faithfulness), §11 (the resolved architecture). This file is the operating
algorithm.

## Non-negotiable invariants (DESIGN §11.2 — do not violate these)

1. **Faithfulness is architectural.** Every claim you assert MUST carry ≥1
   `source_ref` pointing at a real fragment. A sentence with no source cannot be
   written. The `verify.py` gate enforces this and **fails closed** — if it
   exits non-zero, the run is not done; fix the model, don't bypass the gate.
2. **Organized by architecture, not by spec history.** The narrative is "here is
   how this system is built," never "spec 001 says…". **No spec numbers, FR/SC
   codes, or filenames appear in the narrative prose.** They appear ONLY inside
   Layer-2 citation chips (the `source_refs`). This is the brief's hardest rule.
3. **Current state only.** Where specs evolved, describe only what is true now.
   A superseded behaviour is demoted to a single `EvolutionNote` (history), not
   shown as a competing description.
4. **Fail-closed on gaps.** Where the specs leave something open, emit an
   `unspecified` callout — never invent an answer. A confident wrong doc is
   worse than none.
5. **Stateless.** This is a pure function of its inputs. Do not create or
   maintain any persistent product model; the IR artifacts are a per-run build
   cache, regenerated every run, never hand-edited.

## Toolchain

All scripts run via **`uv`** (never `pip`, never system Python). First locate the
extension root (`$SYN`):

```
# installed as a spec-kit extension (the usual case):
SYN=.specify/extensions/atlas
# …or running inside the atlas repo itself (development):
SYN=.
```

Run scripts with their deps provided ephemerally — this builds a correct, throwaway
env and **ignores any stale vendored `.venv`** (a `--dev` install copies one whose
paths are broken): `uv run --with pydantic --with pyyaml python "$SYN/skill/scripts/<script>.py" …`.
(The scripts need only `pydantic` + `pyyaml`.) The examples below use `$SYN`.

## The pipeline (run these phases in order)

```
specs/ ─[adapter: code]→ corpus.json
       ─[A extract: YOU]→ digests          (map; fan out to sub-agents at scale)
       ─[B reconcile: YOU]→ architecture_model.json   (the reduce; the product)
       ─[C compose: YOU]→ document_model.json
       ─[D verify: code, FAIL-CLOSED]→ (gate)
       ─[render: code]→ architecture.html
```

Persist each phase's artifact to a working dir (e.g. `.atlas/`) so the run
is reviewable and re-runnable. These are build IR, not products.

### Phase 0 — Adapt (deterministic; you just run it)

```
uv run --with pydantic --with pyyaml python "$SYN/skill/scripts/adapter_speckit.py" <specs_dir> --project-name "<Name>" --out .atlas/corpus.json
```

Produces a `FragmentCorpus`: every spec file split into source-typed
`Fragment`s, each with a stable `locator`. The core never sees a "spec" again —
only fragments. (If a `workstate` overlay is supplied, treat its structure and
`supersedes` relations as a strong corroborating signal in Phase B; specs remain
primary — DESIGN §4. Phase 1 ships specs-only.)

### Phase A — Extract (map; YOUR reasoning)

For each fragment-group (by `feature_key`), produce a `SpecDigest`: the
fragment-group's **claims**, **decisions** (with rationale + alternatives), and
**open_questions** (`[NEEDS CLARIFICATION]`, deferred, out-of-scope items).

- **Every** extracted `Claim`/`Decision` carries `source_refs` whose `locator`
  is a real fragment id from the corpus. No invented locators — `verify.py`
  rejects them.
- Tag each claim's `altitude`: `functional` (what/why, plain-English, from
  spec.md-like fragments) vs `technical` (entities, data model, contracts,
  infra, from plan/data-model/contract fragments).
- **At scale, fan out:** if there are many feature-groups, dispatch one
  sub-agent (Task tool) per group to extract in parallel, each returning a
  `SpecDigest` JSON. This is the harness-native map. For a handful of specs, do
  it inline.

### Phase B — Reconcile (the reduce; THE PRODUCT — spend your care here)

Combine all digests into ONE `ArchitectureModel`:

- **Merge overlap** — the same fact from three specs becomes one claim with
  three `source_refs`.
- **Resolve supersession** — when a later spec supersedes an earlier claim,
  move the old to `history[]` as an `EvolutionNote` and keep the new as current.
  Evidence-gated (DESIGN §5.4): demote only on real evidence (explicit prose,
  a workstate `supersedes` relation, or unambiguous same-concern recency). If
  unsure, keep both and record the tension as an open question — do not guess.
- **Surface contradictions** — unresolved conflicts become `open_questions`,
  not a silent pick.
- **Collect gaps** — open questions + deferred items → the "Boundaries & open
  questions" material.
- **Plan sections** — fill `section_plan` with the spine (DESIGN §2): what this
  system is · how you use it · architecture at a glance · data model ·
  components · how work flows · [inferred cross-cutting slots] · decisions &
  evolution · boundaries & open questions · where this is headed. Emit a section
  only if the model has material for it.
- **Write `coverage_note`** — a mandatory one-paragraph scope frame: the doc
  describes the *specified* portion of the system; no claim of completeness
  (DESIGN §5.8). `verify.py` fails if this is empty.

Persist `.atlas/architecture_model.json`. Review it like a compiler IR —
it is the diffable record of what the run believes is true.

### Phase C — Compose (YOUR reasoning)

Turn the `ArchitectureModel` into a `DocumentModel`, section by section:

**Write for a general reader (invariant #8).** The storybook is the plain-English read for a
*non-specialist*; your prose must be **simpler than the source markdown** it is distilled from —
translate jargon, prefer short sentences, lead with the plain meaning. Simpler on the surface, but
every claim keeps its source one click away (the citation chips) and every gap stays an
`unspecified` callout: **simplification never costs faithfulness.**

- Each `Block` is `prose`/`table`/`callout`/`diagram`/`coverage`, tagged with
  `altitude`. Functional blocks form Layer 0 (always visible, stand-alone — an
  exec reads only these and understands the system). Technical blocks are
  revealed per section in an inline "Technical detail" disclosure (renderer v2 —
  there is no global depth toggle). Carry `claim_ids` on every prose/table block.
  A prose block may set `prose_style` to `lead` (an opening emphasis line) or
  `pull` (a pull-quote).
- **The narrative must stand alone at Layer 0 and contain no source identifiers**
  (invariant #2). Citations ride only in each block's/section's `source_refs`,
  rendered as inline source-typed chips and a doc-wide References appendix.
- **Masthead & framing.** Set `DocumentModel.project_name` (brand wordmark +
  colophon), `lede` (the deck), optional `title_accent` (a substring of the title
  rendered in the accent), `kicker` (≤2 eyebrow spans), and `meta` (label/value
  pairs). Give each `Section` an optional `strap` (the short eyebrow beside its
  number) and `subtitle` (its lead line).
- Callouts: `decision` (a choice + why), `evolution` (one per `EvolutionNote`),
  `unspecified` (one per open question / gap — the fail-closed surface).
- Diagrams: emit a declarative `DiagramGraph` (nodes/edges + `layout`), each
  node carrying the `source_refs` of the claim it depicts. The renderer lays it
  out to interactive SVG with a per-layout, semantically-appropriate animation
  (motion fitted to each layout's grammar — never one-size-fits-all); you
  describe *what it means*, not coordinates. Eight layouts are available:
  `pipeline` (L→R sequence), `flow` (top-down decision), `ladder` (ordered rising
  rungs), `mapping` (two columns, "X → Y"), `panel` (a grid of component/area
  cards), `hub` (a central core with radiating nodes — the first node is the
  core), `stack` (a layered architecture, built bottom-up), and `timeline` (an
  evolution, lit in chronological order).
- **Optional voice profile.** If a `atlas.voice.md` exists at the project
  root (or `--voice` is supplied), honour it here: it sets *how* prose reads —
  point of view, tone, casing, banned words, domain terminology, number
  formatting. It shapes phrasing ONLY. It must never change *which* claims
  exist, demote a citation, or soften a gap — the verify gate and invariants
  are unaffected by voice. A voice profile can change the wording, never the
  truth. Absent one, write in the clear, plain register of the north-star.

Persist `.atlas/document_model.json`.

### Phase D — Verify (deterministic gate; FAIL-CLOSED)

```
uv run --with pydantic --with pyyaml python "$SYN/skill/scripts/verify.py" .atlas/document_model.json .atlas/architecture_model.json .atlas/corpus.json
```

Exit 0 ⇒ every claim's provenance resolves, every block's claims exist and are
grounded, every citation is real, and the coverage note is present. **Non-zero ⇒
stop and fix** the offending claims/blocks (usually: an unsourced sentence, a
fabricated locator, or a missing coverage note). Never edit the gate to pass.

### Render (deterministic)

```
uv run --with pydantic --with pyyaml python "$SYN/skill/scripts/render.py" .atlas/document_model.json [--theme theme.json] --out architecture.html
```

Produces the self-contained interactive storybook in the editorial design system
(renderer v2): a warm light-only theme, per-section disclosure (inline "Technical
detail" — no global depth toggle), a sticky scrollspy TOC, hand-laid interactive
SVG diagrams that animate per-layout, source-typed citation chips, and a
References appendix. **Drill-to-source (spec 003):** every cited spec/ADR file is also rendered
as a bundled, beautified page under `sources/`, and each citation chip opens it at the exact
cited section — the source content is *copied into the HTML*, so the read surface is
self-contained. A `--theme` JSON of CSS-variable tokens reskins everything (theming is
cosmetic, downstream of atlas — it can change how a claim looks, never which
claims exist). The storybook is **generated, never hand-edited**: to fix a fact,
fix the source and regenerate.

## Quality gate (before declaring done)

Beyond `verify.py` (the automated half), do the human-in-the-loop half:
compare the output to `examples/speckit-linear-architecture.html` (the
north-star) for faithfulness and readability, ideally via a cross-model review
(Codex). The bar (DESIGN §11.4 Phase 1): the generated storybook is as faithful
and as readable as the handwritten target.

## What this is NOT

Not a dashboard, not a per-spec card view, not a renderer that prettifies one
spec. It SYNTHESIZES many specs into one whole-system book. If you ever find
yourself showing specs side by side, or putting a spec number in the narrative,
stop — that is the failure mode this skill exists to avoid.
