# DESIGN — spec-kit-atlas

**Status:** design agreed; **Phase 1 built, proven faithful, and merged** (the
spec-kit→storybook engine — see `examples/generated/RESULT.md` and `README.md`).
Phase 2 (code as a second source / coverage view) is next per §11.4.

This document is written *backward from a target*. Before reading it, read the
target: [`examples/speckit-linear-architecture.html`](examples/speckit-linear-architecture.html)
— a handwritten, whole-system architecture document for the spec-kit→Linear
bridge, synthesized from that project's three feature specs. Everything below
exists to answer one question: **how do we build a generator that produces
documents like that one, faithfully, from any spec-kit project?**

It answers the five questions the seed brief's §6 design pass requires:
what a great output looks like (§1), the section structure (§2), the atlas
strategy (§3), the input (§4), and the faithfulness guardrail (§5). Then it
covers the pipeline, determinism, the engine, and open decisions.

> **If you read one section, read §11 — Recommended architecture (resolved).** It
> states the converged build target as decisions, not options: the three-layer
> shape, the invariants built in from day one, all nine decisions resolved, and a
> teardown-free build sequence. The stance is **right, not narrow** — build the
> architecture correct for the destination, sequence the work so nothing is torn
> up. §0–§10 are the reasoning that leads there.

---

## 0. The one-paragraph thesis

`spec-kit-atlas` reads all of a project's spec-kit artifacts (and, when
available, its `workstate` snapshot), and uses an LLM as a **reasoning engine**
to reconcile many overlapping, evolving, sometimes-contradictory specs into a
single *current-state* architecture narrative, rendered as a self-contained HTML
document. It is not a renderer and not a dashboard. The hard part is
**reconciliation** (what is true *now*, given specs written at different times)
and **faithfulness** (never asserting architecture the specs don't support).
The pipeline is map-reduce — extract per spec, reconcile across specs, compose
to prose, verify against sources — chosen so the tool scales as specs accrete
and so every output sentence stays traceable to a source.

**What it is a projection of: specs first, then code — never code alone.** A
spec-kit folder already holds *both* a functional spec (`spec.md`) and a
technical/architectural spec (`plan.md`, `data-model.md`, `contracts/`); there is
no separate hand-written technical spec to build, and there must not be (a third
hand-maintained document would just become another source of truth that rots).
**Specs are the Phase 1 source** and the indispensable one, because they carry
the *why*: rationale, alternatives, the plain-English functional story, evolution.
Code says *what* exists but rarely *why*; a code-only doc would be a glorified
class diagram with no functional layer — which is why specs lead. Sourced from
specs alone, the storybook describes the system **as specified/intended**, not as
running. **Code is the Phase 2 source** (§8, §11.4): reconciling intent against
code reality closes the *specced-but-unbuilt* / *built-but-unspecced* coverage
gap — most valuable for projects that adopt spec-kit part-way (§5.8). It is a
real, harder capability, deliberately *sequenced* after the engine is proven, not
omitted — and the source-typed provenance and source-agnostic core (§11.1–11.2)
are built from Phase 1 precisely so code drops in without rework.

**The storybook is the canonical READ surface — generated, never authored.**
Sharpen the "source of truth" question by splitting two senses of the term:
- **Write source of truth** = the thing you *edit*, that everything derives from.
  The storybook MUST NEVER be this. The instant it is hand-edited it competes
  with the specs and the code and rots. If a claim is wrong, you fix the
  *source* and regenerate — never the storybook.
- **Canonical read surface** = the one place you *go to understand* the system —
  the de-fragmented, reconciled view. The storybook absolutely is this. It is the
  "reverse-engineered, single coherent truth" assembled from scattered sources.
It earns that authority precisely because it is a faithful reconciliation with
citations back to real named sources (below), not because anyone blessed it by
typing into it. Naming real sources *strengthens* this discipline: every claim is
provably downstream of something, so the read surface can be trusted without ever
becoming a write surface.

**Sources: spec-kit is the v1 source; the engine is built for *all* sources.**
The de-fragmentation value grows the more scattered, contradictory, and
heterogeneous the inputs are — spec-kit folders, but also free-form design docs
("Generator FS Draft 0.8"), ADRs/RFCs, and the **code itself** (`models.py`).
Reconciling intent (specs/docs) against reality (code) is what makes the doc
trustworthy for a half-specced system and is the same need as the coverage gap
(§5.8) and the source-agnostic core (§6, §9.7). v1 sources from spec-kit only;
the architecture (the adapter/core seam, §6) is deliberately shaped so additional
source adapters — design-doc, then code — drop in without touching the core.
**Each claim's provenance is source-TYPED** so a citation can name a spec, a
draft doc, or a code symbol (§1.7 Layer 2, §5.1).

---

## 1. What a great output looks like

The target document is the specification. Studying what makes it good yields the
properties the generator must reproduce. These are the acceptance criteria for
atlas quality.

1. **Organized by architecture, not by history.** Sections are *data model*,
   *components*, *flows*, *safety model* — the way the system is actually built.
   The reader never sees "spec 001 / 002 / 003." Spec numbers are an authoring
   artifact and are absent from the output.

2. **It presents one current state, not a pile of specs.** Where the specs
   evolved, the body describes only what is true *now*. The clearest example:
   the bridge originally gated writes by git branch (only the feature's own
   worktree could write); a later spec **superseded** that with a drift-aware
   "the filesystem is the authority" model — a change significant enough that it
   carried the project constitution from v1 to v2. The target's architecture
   body describes **only** the drift-aware model; the old branch-gate appears
   **once**, as a labelled *evolution note*, not as a competing description.
   (A second, smaller evolution — install moving from UUID-first to key-only
   discovery — is handled the same way.) This collapsing of a supersession into
   current-state-plus-history is the heart of why this is atlas, not
   rendering.

3. **It reads top-down, plain English, newcomer-first.** It opens with what the
   system *is* and *how you use it* (the operator's view) before opening the
   hood. A reader with no prior context can follow it linearly.

4. **It is faithful, and visibly so.** Where the specs leave something open, the
   document says **"Unspecified"** in a callout rather than inventing an answer.
   Every such box in the target traces to a real `[NEEDS CLARIFICATION]` or
   deferred item in the source specs. A confident, wrong architecture doc is
   worse than none; the target would rather admit a gap than fill it with a
   guess.

5. **It explains decisions with their rationale and the roads not taken.** The
   "design decisions" section carries *why*, drawn from the specs' research
   notes — not just *what*.

6. **It is structurally consistent and skimmable.** Fixed visual grammar:
   numbered sections, a table of contents, interactive SVG diagrams for the
   pipeline and data model, and three callout types — *decision*, *unspecified*,
   *evolution*. These three callout types are not cosmetic; they map directly to
   the three things atlas must surface (a choice, a gap, a change over time).

7. **It serves two audiences in one document, by progressive disclosure.** The
   storybook is the shared read-layer for *both* executives/evaluators and
   developers — not two documents, one document with two reading depths. This
   is possible precisely because a spec-kit folder is already two-tiered
   (functional `spec.md` + technical `plan.md`/`data-model.md`/`contracts/`):
   - **Layer 0 — functional (always visible):** plain-English "what it does and
     why," synthesized from the functional specs. An exec reads top-to-bottom,
     stops here, and has a complete, honest understanding *at their altitude*.
   - **Layer 1 — technical (click to expand):** the substance a developer needs
     — entity/field tables, the data model, the API/contract surface, infra,
     decisions with trade-offs — synthesized from the technical specs.
   - **Layer 2 — provenance (deepest):** which sources back this claim, named and
     **typed by origin** — e.g. a spec (`spec-004 · data-model.md`), a draft
     design doc (`Generator FS Draft 0.8 · §3`), or a code symbol
     (`models.py · Account`). The reader can drill from a sentence to the exact
     source(s) it rests on, and can see *what kind* of source it is (specified
     intent vs draft vs actual code). This is the home for citations — which is
     why the **narrative body stays spec-number-free** (per the brief: the body
     reads "here's the system," not "spec 004 says…") while full traceability
     lives one drill-down deeper. A deliberate refinement of the brief: numbers
     are hidden from the *narrative*, available in the *provenance layer*.
   Two hard rules keep this from serving neither audience: **(a) the functional
   layer must stand alone** — drill-downs are strictly *additive depth*, never
   load-bearing for the top-line understanding; and **(b) the drill-down is
   still synthesized** (deduped, reconciled, superseded-removed) — the technical
   altitude of the *same* current-state model, never "click to see the raw
   spec." The moment a drill-down shows raw `data-model.md`, the tool has
   regressed from synthesizer to renderer.

> **Design rule:** the generator is "done" when its output for the bridge
> project is judged as faithful and as readable as the handwritten target —
> assessed by cross-model review (§7), not by the author alone.

---

## 2. Section structure

**A fixed spine, content-gated, with room for inferred cross-cutting sections.**
Not fully fixed (projects differ), not fully free-form (consistency and
skimmability matter). The spine below is the canonical order; a section is
*emitted only if the specs supply material for it*; two slots are *inferred*
per project.

| # | Section | Inclusion rule | Inferred? |
|---|---------|----------------|-----------|
| 1 | **What this system is** | Always | No |
| 2 | **How you use it** (operator view) | If there's a user-facing surface (CLI/API/UI) | No |
| 3 | **Architecture at a glance** (the big picture) | Always | No |
| 4 | **Data model** | If entities/schemas exist | No |
| 5 | **Components** | Always | No |
| 6 | **How work flows through it** | If meaningful flows exist | No |
| 7 | **Cross-cutting mechanism(s)** (e.g. identity/idempotency) | If present | **Yes** — title & count inferred |
| 8 | **A governing model** (e.g. authority/safety) | If present | **Yes** — title inferred |
| 9 | **Design decisions & evolution** | Always (evolution sub-part only if supersessions exist) | No |
| 10 | **Boundaries & open questions** | Always (this is the faithfulness section) | No |
| 11 | **Where this is headed** | If forward-looking material exists | No |

**Each section is two-tiered (progressive disclosure, §1.7).** Every emitted
section carries a *functional summary* block (Layer 0, always visible) plus
*expandable technical* blocks (Layer 1) and *provenance* (Layer 2). The spine is
the same for both audiences; the altitude of each block, not the section list,
is what differs. This is a property of every section, not a separate section.

Notes:
- Sections 1–6, 9, 10 are the **invariant skeleton** — nearly every software
  system has them, and 9–10 are mandatory because they carry the integrity of
  the document (rationale + honest gaps).
- Sections 7–8 are where projects genuinely differ. In the target they became
  *Identity & idempotency* and *Authority & safety model* — concepts that
  emerged from the specs, not from a fixed list. The reconcile phase (§3)
  proposes these from recurring cross-cutting themes; there may be zero, one, or
  several.
- The spine is a **default**, overridable per project later if needed. v1 ships
  the fixed spine; per-project inference is limited to slots 7–8 and to
  including/omitting gated sections. We do **not** attempt fully free-form
  outline inference in v1 — it trades determinism and reviewability for
  flexibility we don't yet need.

---

## 3. Atlas strategy

**Map-reduce in four phases**, not a single pass. Single-pass over all specs is
viable only for tiny projects and fails exactly when the tool is most needed (a
30-spec project that no longer fits a single high-quality reasoning window).
Map-reduce is the architecture; single-spec input is just its degenerate case.

```
  specs/ (+ workstate)
        │
   ┌────▼─────┐  PHASE A — EXTRACT  (map, one call per spec, parallel)
   │ extract  │  each spec → a structured "spec digest":
   └────┬─────┘  claims · entities · decisions · flows · requirements
        │        open-questions — every item carries provenance + lifecycle
        │
   ┌────▼─────┐  PHASE B — RECONCILE  (reduce, one reasoning pass)
   │reconcile │  all digests + workstate relation graph →
   └────┬─────┘  ONE current-state "architecture model":
        │        merged claims · resolved supersessions (old→history) ·
        │        flagged contradictions · gaps · proposed section plan
        │
   ┌────▼─────┐  PHASE C — COMPOSE  (per-section generation)
   │ compose  │  architecture model → section-by-section prose
   └────┬─────┘  (each call sees only its section's slice of the model)
        │
   ┌────▼─────┐  PHASE D — VERIFY  (adversarial faithfulness gate)
   │ verify   │  each output paragraph checked against its cited claims;
   └────┬─────┘  unsupported sentences flagged/removed
        │
   ┌────▼─────┐  RENDER (deterministic, no LLM)
   │ render   │  document model → self-contained styled HTML
   └──────────┘
```

### Phase A — Extract (map)
One bounded call per spec. Input: that spec's artifacts (and its workstate item,
if any). Output: a **spec digest** — a structured object listing the spec's
claims, entities, decisions (with rationale + alternatives), flows,
requirements, and open questions. **Every extracted element carries a
`source_ref` (file + anchor) and a `lifecycle` tag** (the workstate `state` for
that item when available; otherwise inferred from the spec's own status). This
is the phase that scales: N specs, N independent calls, each with small context.

### Phase B — Reconcile (reduce) — *the core reasoning task*
One pass over **all** digests plus the workstate **relation graph** (especially
`supersedes` edges and `superseded` states). It produces a single
**architecture model**: the reconciled, current-state set of claims, with:
- **Overlap merged** — the same fact stated in three specs becomes one claim
  with three source_refs.
- **Supersession resolved** — when spec B supersedes spec A's claim, A's claim
  is moved to `history[]` (it becomes an evolution note), B's becomes current.
  Resolution evidence, in priority order: (1) an explicit `supersedes`
  relation / `superseded` state in workstate; (2) explicit prose ("this
  supersedes…"); (3) recency (later spec date) **only** when the two clearly
  address the same concern. Recency alone is a weak signal and never silently
  overrides — see the fail-closed rule below.
- **Contradictions flagged** — if two current claims conflict and nothing
  resolves which wins, the conflict is recorded as an `open_question`, **not**
  silently decided.
- **Gaps collected** — `[NEEDS CLARIFICATION]`, deferred items, and
  "out of scope" notes become the *Boundaries & open questions* material.
- **Section plan proposed** — the reconcile pass assigns claims to spine
  sections and proposes the inferred cross-cutting sections (slots 7–8).

> **Why supersession can't come from workstate alone.** The target's marquee
> supersession (drift-aware authority replacing the branch-gate) lives in prose:
> a later spec explicitly supersedes an earlier requirement, and the change
> ripples into a constitution amendment. It is finer-grained than the
> feature/task items a structural `workstate` tracks, and the "this supersedes
> that" relationship is stated in sentences, not in a relation field. So
> reconcile must detect semantic supersession **from content**, using
> workstate's explicit relations as a strong corroborating signal *when
> present*, not as the only source. This is the key reason raw specs are primary
> input (§4).

### Phase C — Compose
Generate prose **section by section**, each call seeing only its slice of the
architecture model (its claims + their source_refs). Keeping generation per
section keeps every call bounded, keeps prose grounded in a specific claim set,
and makes regeneration of one section cheap. The composer writes *content*; it
does not write HTML. **Each composed block is tagged with an `altitude`** —
`functional` (Layer 0), `technical` (Layer 1), or `provenance` (Layer 2) — so
the renderer can make the deeper altitudes collapsible (§1.7). Altitude derives
from which spec a claim came from: functional claims (from `spec.md`) compose the
plain-English layer; technical claims (from `plan.md`/`data-model.md`/
`contracts/`) compose the drill-down. The functional layer is composed to stand
alone; technical blocks are additive depth, never prerequisites for it.

### Phase D — Verify (faithfulness gate)
A separate adversarial pass re-reads each generated paragraph against the
source_refs of the claims it's supposed to rest on, and flags any sentence not
supported by a cited source. Unsupported sentences are removed or downgraded to
"Unspecified." This is the automated half of the integrity bar; the cross-model
review (§7) is the human-in-the-loop half.

### Determinism / sane regeneration
LLMs aren't bit-deterministic; we engineer *structural* stability instead:
- **Low/zero temperature** on all calls.
- **Cache Phase A digests by spec content-hash** — unchanged specs are never
  re-extracted; a one-spec edit re-runs one extract + reconcile + compose.
- **Fixed section spine** → stable ordering and shape across runs.
- **The architecture model is a persisted, diffable JSON artifact.** Reviewers
  diff *the model* between runs (claims added/removed/superseded), not just the
  prose — meaningful change review even though wording varies.
Accept that exact wording drifts run-to-run; guarantee that structure, claims,
and provenance are stable.

> **What "persisted" means here — a build artifact, not a product-of-record.**
> The architecture model and the content-hash cache are a **compiler IR + speed
> cache**: written to disk so a run is reviewable and incremental, but
> **regenerated from the sources on every run, never authoritative, never
> hand-edited.** They are intermediate output of a stateless compile (§11.2 #4),
> not a persistent product model. Delete them and the next run recreates them
> identically from the specs. This is categorically distinct from product-mem's
> accumulating product graph — atlas holds no state of record, only the
> current run's derivation. If a fact is wrong, you fix the *source* and
> recompile; you never edit the model or the storybook.

---

## 4. Input: raw specs primary, workstate as a structural overlay

The brief's §4 frames this as workstate-for-structure + specs-for-content. After
studying the real inputs, this design **sharpens** that:

**Primary input: the raw spec artifacts** — `spec.md`, `plan.md`, `research.md`,
`data-model.md`, `contracts/`, `quickstart.md`, `tasks.md`. Rationale: the
target document draws its richest material — the decision rationale and
alternatives (from `research.md`), the entity tables (from `data-model.md`), the
API surface (from `contracts/`) — from artifacts whose content the current
`workstate` floor does **not** fully carry. Today's spec-kit source emits
shallow items (feature/task, `proposed`/`done`); atlas needs the prose.

**Overlay input: `workstate`, when available** — used as an **authoritative
structural corroborator**, not the content source:
- the **lifecycle state** of each item (authoritative `proposed`…`superseded`…),
- the **relation graph**, above all `supersedes` edges,
- the item **hierarchy** (what belongs to what).
When workstate is present, reconcile trusts these signals over prose inference.
When it's absent or thin, atlas **degrades gracefully**: it parses structure
and lifecycle from the specs themselves. The tool must not hard-depend on a
mature source — it should produce a good document from raw specs alone, and a
*better*, more confidently-reconciled one when workstate is also supplied.

This keeps the ecosystem coherent (we consume the shared schema/parser when it's
there) without betting the whole product on the source carrying content it
currently doesn't.

> **Consequence for sequencing:** atlas can be developed and tested now,
> against raw specs, without waiting on a richer workstate. The bridge project's
> three specs are the v1 fixture.

---

## 5. Faithfulness guardrail

The integrity bar: **a confident, wrong architecture doc is worse than none.**
Faithfulness is enforced at every phase, not bolted on at the end.

1. **Provenance carried end-to-end, and source-typed.** Every claim gets
   `source_ref`s at extract time and keeps them through reconcile and compose. A
   claim with no source cannot exist; therefore a sentence resting only on an
   unsourced claim cannot be written. Each `source_ref` carries a **type**
   (`spec` | `design-doc` | `code` | …) and a human-readable name (e.g.
   `spec-004 · data-model.md`, `Generator FS Draft 0.8 · §3`, `models.py ·
   Account`), so the Layer-2 citations (§1.7) can name and classify exactly what
   backs each claim — and so a future multi-source pipeline (§9.7) needs no new
   provenance model, only new adapters that emit typed refs.
2. **Fail-closed → "Unspecified."** When the section spine expects something the
   specs don't address, the document says so explicitly (the *unspecified*
   callout), mirroring the schema's fail-closed discipline. Silence is never
   filled with a plausible guess.
3. **Contradictions surfaced, not resolved by fiat.** Unresolvable conflicts
   become *open questions* / *evolution notes*. The doc may say "the specs
   disagree on X" — that is a faithful statement; picking a side silently is not.
4. **Supersession is evidence-gated.** Old behavior is demoted to history only
   on real evidence (workstate relation, explicit prose, or unambiguous
   same-concern recency). Otherwise both claims stand and the tension is noted.
5. **Adversarial verify pass (Phase D).** Automated check of each paragraph
   against its cited sources; unsupported text is stripped.
6. **Cross-model review of output (§7).** A second model judges the *whole*
   document for faithfulness and readability against the source specs — the
   discipline the brief calls out as especially valuable here.
7. **Auditability.** The persisted architecture model + provenance map is a
   sidecar artifact. Even though the reader-facing HTML stays clean (no inline
   citations cluttering the prose), an audit view can show, per paragraph, which
   spec lines back it. *(Resolved — see Decision §9.3 / §11.3: named,
   source-typed citations live in the Layer-2 drill-down.)*
8. **Coverage honesty — never imply more coverage than the specs support.**
   Faithfulness is about *certainty* of claims; this is about *completeness* of
   scope, and it is the most dangerous failure mode for projects that adopt
   spec-kit **part-way through** (a common case — much of the system predates the
   specs, so the spec folders cover only a fraction of it). A storybook sourced
   purely from specs would then describe that fraction *authoritatively*, and a
   reader could not tell the rest of the system exists — a partial map that looks
   complete, which is worse than no map. The rule: the storybook MUST frame its
   own scope — it describes **the specified portion of the system**, and makes no
   claim of completeness. Three levels, by effort: **(floor, v1, mandatory)**
   state the frame plainly in the document; **(better, fast-follow)** cross-check
   the spec folders against the codebase to *name* the gap (specced-but-unbuilt
   vs built-but-unspecced — the "coverage" view); **(later)** AI-assisted
   backfill of specs from unspecced code. v1 ships the floor and stays
   specs-only; mid-adoption projects are the strongest argument for pulling the
   coverage cross-check forward as the first fast-follow (§8).

---

## 6. Pipeline & engine (how it's built)

- **Delivery: a SKILL, not a program that shells out to an LLM.** The tool ships
  as an installable skill (like spec-kit / graphify), and **the in-session Claude
  Code agent IS the reasoning engine** — there is no `claude -p` subprocess, no
  API key, no provider question. A `SKILL.md` carries the orchestration algorithm
  the agent follows; deterministic `scripts/` (run via `uv`, **no LLM inside**)
  carry the parsing, the fail-closed faithfulness gate, and the renderer. This is
  the ecosystem-native shape: the agent reasons in-session, and at scale the
  extract *map* fans out to sub-agents (harness-native map-reduce) rather than a
  Python async loop. Rationale: it makes "AI is the engine" literal rather than
  bolted-on, removes the auth/provider question entirely, and matches every other
  tool in the family. The Phase descriptions in §3 are the agent's algorithm; the
  guardrails below are code the agent MUST run.
- **The split that keeps it faithful:** *reasoning* lives in the agent + SKILL.md
  (extract / reconcile / compose); *guarantees* live in deterministic scripts.
  In particular the **Phase-D verify gate is a script that fails closed** — it
  rejects any composed block whose claims lack a resolvable `source_ref`,
  regardless of what the model produced. Faithfulness is therefore code-enforced,
  not model-promised. Render is pure code (golden-tested against `examples/`).
- **Engine:** the LLM (the in-session agent) is the product, not a helper.
  Phases A–C are the agent's reasoning with structured (schema-constrained)
  outputs persisted as IR artifacts; Phase D and render are deterministic code.
- **Clean adapter / core seam (a v1 design constraint, for a future option).**
  The valuable, hard part — extract → reconcile → compose → verify, with
  faithfulness and provenance — has nothing intrinsically to do with spec-kit; it
  is "fragmented, overlapping, evolving design corpus → one faithful current-state
  read-model." spec-kit is just *one input shape*. So v1 separates an **input
  adapter** (spec-kit folders → an internal, source-neutral *fragment corpus*)
  from the **atlas core** (corpus → architecture model → document model). The
  core never imports spec-kit assumptions. This costs little now and keeps open a
  real future direction (§8 / §9.7): a standalone atlas engine that consumes
  *any* fragmented design corpus (ADRs, RFCs, design docs) — a different input
  adapter, not a rewrite. Do NOT build the general platform now; just keep the
  seam clean so it remains possible.
- **Structured outputs:** each phase emits a validated object (spec digest,
  architecture model, document model) — same fail-closed posture as the schema
  validator: a malformed phase output is an error, not a best-effort guess.
- **Composition vs markup are separate.** The LLM produces a **document model**
  (sections → typed blocks: prose, table, **declarative diagram graph**,
  callout). A deterministic renderer turns that into the self-contained,
  interactive HTML described above (reading column, scrollspy TOC, theme toggle,
  callout grammar, hand-rendered SVG diagrams). Benefits: faithful (LLM writes
  content and diagram *intent*, not tags or coordinates), restyleable, testable,
  and the visual + interaction grammar stays consistent across projects.
- **Diagrams are SVG, and the document is interactive.** The output bar is
  *beautiful and interactive*, not just readable (see the north-star example).
  **Every diagram is hand-authored, theme-aware SVG** — never ASCII, never a
  raster image: the architecture pipeline, the data-model mapping, the
  lifecycle ladder, the authority/drift decision flow, the identity recovery.
  The reader-facing document ships with: a scrollspy table of contents, a
  reading-progress indicator, a light/dark theme toggle, hover-to-explain
  diagram nodes, click-a-node-to-jump navigation, and at least one diagram with
  an interactive state toggle (the example uses a forward-write vs
  backward-drift path highlighter). All self-contained in one HTML file, no
  external assets beyond CDN fonts, and degrading gracefully under
  `prefers-reduced-motion`.
  - **How the generator produces SVG faithfully:** the LLM emits *diagram
    intent* as a typed block in the document model — a small declarative graph
    (nodes, edges, lanes, the ordered phase ladder, the decision branches) with
    each node carrying its grounding `source_ref` and its hover caption. A
    deterministic **SVG layout/render component** turns that graph into the
    styled, interactive SVG. The model writes *what the diagram means*; code
    writes the coordinates and the interaction wiring. This keeps diagrams
    faithful (a node exists only if a claim backs it), restyleable, and
    consistent across every generated document.
  - **The renderer is themeable — every host project may look different.** This
    tool is installed across many repositories, and each can have its own design
    system; a generated doc should look like it belongs to *its* project, not
    like one fixed template. So rendering takes **`document model + theme →
    HTML`**, where a *theme* is a small set of design tokens: the type system,
    the color roles (paper/ink/accent/the three callout hues/the SVG palette),
    spacing, radii, and the interaction set. The SVG diagrams are authored
    entirely against CSS-variable tokens (as in the example) precisely because
    that generalizes — re-point the tokens and every diagram re-themes for free,
    with no re-layout. The hand-authored example is therefore **one theme (the
    default reference theme)**, not *the* theme.
  - **Where a theme comes from (precedence, fail-soft):** (1) **detected** from
    the host project — existing CSS custom properties, a Tailwind/theme config,
    committed brand tokens, a logo palette; (2) **declared** in a committed
    `atlas.theme.{json,css}`; (3) a built-in named **preset**; (4) the
    **default reference theme** as the guaranteed-good fallback. The interaction
    grammar and the *set* of diagram types stay constant across themes (that's
    what keeps quality consistent); only the tokens vary.
  - **Theming is cosmetic and strictly downstream of atlas — the load-
    bearing rule.** The extract → reconcile → compose → verify pipeline and
    *every* faithfulness guarantee are theme-independent. A theme can change how
    a claim looks; it can never change which claims exist or what they say.
    "Looks like the project" therefore can never collide with "is faithful."
  - **Real host design systems teach two things** (observed from a mature
    in-house design system used as a local reference). A host project's design
    system typically ships as a token file of *semantic* CSS custom properties
    (page/surface/ink/accent/rule roles, a modular type scale, a spacing ramp,
    restrained radii, paper-like shadows, motion curves), distinctive type, and
    a written brand voice. Two lessons follow:
    1. **The token approach maps onto reality cleanly.** Such systems already
       expose exactly the role-named CSS variables our renderer consumes;
       because the SVG diagrams render off those variables, re-pointing the
       tokens re-skins every diagram with no re-layout. A host token file is
       literally a "declared theme" — and a "detectable" one (§9.6). The theme
       is read as *data* by the storybook renderer; it is **not** turned into a
       reusable, agent-invokable skill — the storybook is the theme's only
       consumer (§9.8).
    2. **A real design system carries VOICE, not only visuals** — and voice is
       not purely cosmetic, so it needs its own handling. Brand systems commonly
       dictate prose (point of view, casing, banned words, domain terminology,
       number formatting). A "theme" therefore has two parts: **(a) visual
       tokens** — cosmetic, downstream of *everything*, always safe to vary; and
       **(b) an optional voice profile** — which shapes *how* the storybook's
       compose phase phrases a claim, never *which* claims exist. Faithfulness
       survives because Phase-D verify checks every paragraph against its source
       claims regardless of voice: a voice profile can change the wording, never
       the truth. v1 ships visual tokens; the voice profile is a deferred,
       optional input (§8).
- **CLI shape (provisional, mirrors the ecosystem):**
  `spec-kit-atlas --specs-dir specs/ [--workstate workstate.json] -o architecture.html`
  — auto-detect `specs/`, optional workstate overlay, HTML output. Fail-closed
  with guidance, same conventions as the bridge tool.
- **Stack:** Python 3.11+, stdlib-first, minimal deps (HTTP client for the LLM
  API, the shared workstate validator when overlay is used). Self-contained HTML
  (no external assets) so the artifact is portable.
- **Toolchain: `uv`, not `pip`** — matches the ecosystem house standard
  (`workstate-schema`, the trackers). Dependencies, virtualenvs, and runs go
  through `uv`; never invoke `pip` directly or touch system Python. End users who
  only run the tool should not need to know `uv` is underneath (mirror the
  ecosystem's wrapper convention).

---

## 7. Quality assurance & cross-model review

Atlas quality can't be unit-tested like a parser; it needs judgment.
- **Golden target:** `examples/speckit-linear-architecture.html` is the
  reference. Generated output for the bridge project is compared against it for
  coverage, faithfulness, and readability.
- **Cross-model review at phase boundaries** (a second model via Codex — the
  cross-model review harness), per the brief — especially a final pass asking "is
  this document faithful to the specs and as clear as the target?" This is the
  primary quality gate, run before any push. *(Dogfooding note: an adversarial
  faithfulness pass over the handwritten target caught a real defect — a phase
  ladder missing two of nine phases — proving this gate's value before any
  generator exists.)*
- **Faithfulness regression checks:** seed specs with a known supersession and a
  known `[NEEDS CLARIFICATION]`, assert the output demotes the old behavior to
  an evolution note and emits an "Unspecified" callout (i.e. the two behaviors
  the target demonstrates).

---

## 8. Scope &amp; sequencing

> The build target and its phasing are stated authoritatively in **§11**. This
> section is the short version. The stance (§11) is *right, not narrow*: the
> seams and invariants are present from Phase 1; only **source adapters and
> surfaces** are sequenced, never reworked.

**Phase 1 — prove the engine (the concrete first deliverable):** spec-kit adapter
→ source-typed fragment corpus → the full extract / reconcile / compose / verify
core → document model → themed, interactive SVG renderer with the Layer&nbsp;0/1/2
drill-down and named citations. Includes from day one: faithfulness +
source-typed provenance (§5, §11.2), the fixed content-gated spine with inferred
slots, fail-closed/"Unspecified", coverage-honesty framing (§5.8), the persisted
diffable architecture model, default theme + presets + declared `atlas.theme`,
and the cross-model review gate. Fixture: the bridge project's specs, measured
against the handwritten target.

**Phase 2 — code as a second source (planned, not hypothetical):** a code adapter
emitting source-typed refs; reconcile then reconciles *intent vs reality* and
produces the coverage view (specced-but-unbuilt / built-but-unspecced). This is
why provenance is source-typed and the core source-agnostic from Phase 1 — it
drops in without core changes and is the real test that the seam holds.

**Phase 3 — reach &amp; polish:** host-theme detection; the optional voice profile;
further source adapters (design-doc / ADR / RFC); richer diagram affordances.

**Phase 4 — strategic, decide later:** standalone source-agnostic engine /
possible open-source / "fragments → read-model" spec paradigm — a packaging
exercise once the core is proven across ≥2 real source types, not a rewrite (§9.7).

**Genuinely out of scope** (not merely sequenced): workstate as a *required*
input (always an optional overlay); fully free-form outline inference;
auto-layout / animated diagram *engines* beyond the curated hand-rendered SVG set
(the fixed set of diagram types is in scope); multi-project / portfolio
atlas; "what changed since last doc" diffing; inline citations in the
*narrative* body (citations live in the Layer-2 drill-down, never the prose).

---

## 9. Decision log

> **All nine decisions are now resolved — the resolutions are tabulated in
> §11.3.** This section preserves the *reasoning* behind each (why the position
> was reached, alternatives weighed). Read §11.3 for the verdicts; read here for
> the argument. Where a decision still says "confirm," it means the resolution in
> §11.3 is my recommendation and a one-word "agreed" locks it.

1. **Workstate dependency.** Resolution (§11.3): *optional overlay*. Build from
   raw specs alone; trust workstate's structure/relations when present. (Keeping
   it optional is what lets the build start now.)
2. **Outline flexibility.** Resolution (§11.3): *fixed spine + inferred slots
   7–8*; no free-form per-project outline inference.
3. **Provenance visibility — RESOLVED: named, typed citations in Layer 2.** The
   two-tier reading model gives provenance a natural home: it is **Layer 2**, the
   deepest drill-down, reached only after expanding the technical layer. There it
   shows **named, source-typed citations** — `spec-004 · data-model.md`,
   `Generator FS Draft 0.8 · §3`, `models.py · Account` — so a reader can trace
   any sentence to the exact source(s) it rests on and see what *kind* of source
   it is. The narrative body stays spec-number-free (brief §1); the numbers live
   in the drill-down. No conflict between "readable" and "traceable." (The full
   provenance map also persists as an audit sidecar for tooling.)
4. **Determinism investment.** Resolution (§11.3): the *"stable structure,
   diffable model, prose may vary"* contract, with extract cached by
   content-hash. Stronger run-to-run prose stability (caching composed sections)
   is available later if a need appears, but is not worth the cost now.
5. **Name.** Resolution (§11.3): keep `spec-kit-atlas` (descriptive,
   honest). Revisit only if the standalone engine (#7) is pursued, when a
   source-neutral name might fit better.
6. **Theming reach.** Resolution (§11.3): ship the default reference theme +
   presets + a declared `atlas.theme.{json,css}` in Phase 1; sequence
   host-theme **detection** (from the project's CSS/Tailwind/brand files) into
   Phase 3. Rationale: always-correct beats subtly-wrong — a detected theme with
   the right hue but wrong type scale reads worse than an honest default;
   detection earns its way in once real host repos are in hand. Theming is
   cosmetic and strictly downstream of atlas (§6).

7. **Standalone atlas engine / open-source (a strategic option to KEEP, not
   build).** The atlas core is source-agnostic (§6 adapter/core seam), so it
   could stand alone as a general "fragments → faithful read-model" engine — and
   the underlying idea is a *new paradigm for spec writing*: author small
   fragments as you go, and let the synthesizer continuously regenerate the
   coherent whole as the always-current read-model (specs as source, the readable
   doc as generated output — never hand-maintained). The faithfulness machinery
   is the moat, and it is source-independent, which makes the *engine* the
   interesting thing to potentially open-source — more so than a spec-kit-specific
   tool. **Resolution (§11.3): keep the option, build it later (Phase 4).** Prove
   the engine across ≥2 real source types first; the option is preserved for free
   by the adapter/core seam (§6, §11.1), so this becomes a packaging exercise, not
   a rewrite. Flagged so the decision is deliberate, not foreclosed by accident —
   and not pulled forward, since building the general platform before the concrete
   thing works is the surest way to never ship.

8. **Multi-source input & "canonical read surface" positioning.** The storybook
   is positioned as the *generated, never-authored* canonical READ surface — the
   reverse-engineered, de-fragmented coherent view — not a hand-editable write
   source of truth (§0). Two confirmations wanted: **(a) positioning** — agree
   the storybook is "the place you go to understand the system," authoritative
   *because* it cites real sources, fixed only by editing sources and
   regenerating (never edited directly)? **(b) source roadmap** — v1 sources from
   spec-kit only, but provenance is source-typed and the core is source-agnostic
   so design-doc and then **code** adapters can be added without core changes
   (code being what closes the mid-adoption coverage gap, §5.8). Resolution
   (§11.3): **multi-source is the architecture, not a deferral** — the seam and
   source-typed provenance are present from Phase 1; sources are *sequenced*
   (spec-kit Phase 1, code Phase 2). The code adapter is planned, not
   hypothetical, because it is the highest-value next source and the real proof
   the seam holds.

9. **Theme delivery — RESOLVED: theme is data, scoped to the storybook only.**
   The theme exists *only* to brand this tool's architecture storybook; no other
   artifact or service consumes it. A general per-project "template skill"
   invokable by any agent for any branded output was considered and **rejected
   as over-engineering** — its sole justification was sharing the look across
   many artifacts (slides, READMEs, …), which does not apply when the storybook
   is the only consumer. So the theme is delivered as **data the storybook
   renderer reads** — `atlas.theme.{json,css}` (declared) or a built-in
   preset / the default reference theme — never as a separately installable,
   agent-invokable skill. The two-part separation still holds internally (the
   reasoning engine produces a theme-agnostic document model; the storybook
   renderer applies a theme), but it is one tool, not a project-wide
   branded-output toolkit. Faithfulness rule unchanged: the renderer/theme owns
   *how it looks* (+ optional voice), never *what is true*.

---

## 10. Why this isn't a renderer (the one-line test)

If you deleted the reconcile phase, you'd get a prettier pile of three specs —
including *both* the branch-gate authority model and the drift-aware model that
superseded it, side by side, contradicting each other. The reconcile phase is
what makes the output a single, current, true architecture. That phase is the
product. Everything else serves it.

---

## 11. Recommended architecture (resolved)

The design pass has converged. This section states the build target as
decisions, not options. Guiding stance: **build the architecture that is correct
for the destination, and sequence the work so no step is ever torn up.** Not
narrow for its own sake — *right*. The way "right" stays affordable is that all
the load-bearing **seams and invariants are built in from the start**, while the
parts that genuinely are independent (the *source adapters*) are *sequenced* —
adding an adapter to a clean core is additive, never a teardown.

### 11.1 The shape — three layers, one rule

```
  SOURCES            ADAPTERS                 CORE (knows no source type)            RENDER
  spec-kit  ─┐                          ┌─ extract ─ reconcile ─ compose ─ verify ─┐
  design-doc ┼─▶  fragment corpus  ─────┤    (map)    (reduce)   (per-      (faith- ├─▶ document model
  code       ─┘   (source-TYPED refs)   └─         architecture model       ness)  ─┘   ──(+ theme)──▶
                                                    (persisted, diffable)                  interactive
                                                                                           SVG HTML
```

**The one rule everything depends on: the core never knows what a "spec" is.**
Sources become a uniform, source-typed *fragment corpus* at the adapter boundary;
the core reasons only over that corpus. This single discipline is what makes
multi-source, code reconciliation, the standalone-engine option, and OSS all
*additive later* rather than *rewrites later*. If only one thing is gotten right,
it is this seam.

### 11.2 The invariants (built in from day one — never sequenced away)

1. **Faithfulness is architectural, not a feature.** Provenance is born at
   extract, survives every phase, and Phase-D mechanically removes any sentence
   without a live source. A claim with no source cannot exist. (§5)
2. **Provenance is source-typed from the first commit** — `{type, name, anchor}`,
   e.g. `spec-004 · data-model.md`, `Generator FS Draft 0.8 · §3`,
   `models.py · Account`. Even while only the spec-kit adapter exists, refs carry
   a type, so adding the code adapter needs *no* provenance redesign. (§5.1, §1.7)
3. **Generated, never authored.** The storybook is the canonical *read* surface,
   never a hand-editable write source of truth. Wrong claim → fix the source,
   regenerate. (§0)
4. **Stateless by construction.** Every run is a pure function of its inputs
   (specs [+ optional workstate overlay] + theme) → HTML. The tool never
   maintains a persistent, authoritative product model — that is product-mem's
   territory, reached only via the `workstate` format. This is the boundary that
   keeps atlas from disturbing a peer product graph: atlas *renders*, it
   does not *accumulate state*. (See the build-artifact clarification in §3 —
   the architecture model and cache are per-run, never a product-of-record.)
5. **Reconcile is the product.** Engineering care, eval budget, and cross-model
   review concentrate on the reduce phase — current-state correctness,
   supersessions collapsed, contradictions surfaced. (§3, §10)
6. **Coverage honesty.** The doc always frames its own scope; it never implies
   more coverage than its sources support. (§5.8)
7. **Composition ≠ markup ≠ theme.** LLM emits a document model (incl. declarative
   diagram graphs); a deterministic renderer makes interactive SVG HTML; a theme
   is cosmetic data applied at render. Three clean stages. (§6)
8. **Written for a general reader.** The storybook is the plain-English read of the spec
   portal for non-specialists; its prose is *deliberately simpler* than the source markdown it
   is distilled from. Simplification is the product, not a side effect — and it is safe only
   because every simplified claim keeps its source one click away (the citation chips, §5.1) and
   every gap surfaces as an `unspecified` callout rather than being smoothed over. Simpler on the
   surface, traceable underneath; **simplification never costs faithfulness.** (§1.7)

### 11.3 Resolved decisions (the flag is planted on all ten)

| # | Decision | Resolution |
|---|----------|------------|
| 1 | Workstate | **Optional overlay.** Build from raw specs; trust workstate's structure/relations when present. |
| 2 | Outline | **Fixed spine + 2 inferred cross-cutting slots.** No free-form outline inference. |
| 3 | Provenance | **Named, source-typed citations in the Layer-2 drill-down.** Body stays number-free. |
| 4 | Determinism | **Stable structure + diffable architecture model; prose may vary.** Cache extract by content-hash. |
| 5 | Name | **`spec-kit-atlas`** (revisit only if the standalone engine, #7, is pursued). |
| 6 | Theme sourcing | **Default + presets + declared `atlas.theme` now; host-theme detection sequenced next.** |
| 7 | Standalone engine / OSS | **Option preserved by the seam (11.1); not built until the engine is proven on real sources.** |
| 8 | Multi-source | **Multi-source is the architecture; sources are sequenced (11.4). Spec-kit first, code next.** |
| 9 | Theme delivery | **Theme is data the renderer reads; storybook is its only consumer.** No agent-invokable skill. |
| 10 | Renderer surface | **The editorial design system is the single default renderer output** (spec `specs/001-renderer-v2/`): vanilla self-contained HTML, no SPA; light-only; per-section disclosure (no global depth toggle); diagrams semantic + animated per-layout; fonts via CDN. Theme stays a retint layer. |

### 11.4 Build sequence (each phase ships value; none requires a teardown)

The seams and invariants (11.1–11.2) are present from Phase 1; later phases add
*adapters and surfaces*, not rework.

- **Phase 1 — Prove the engine. ✅ SHIPPED.** spec-kit adapter → fragment corpus
  → the full extract/reconcile/compose/verify core → document model → themed
  interactive SVG renderer with the Layer 0/1/2 drill-down and named citations.
  Acceptance met: the generated bridge storybook was judged faithful (0/0/0) by
  cross-model review after a 10→0 convergence (`examples/generated/RESULT.md`).
  *This is the proof the whole architecture rests on.*
- **Phase 2 — Code as a second source. ✅ SHIPPED.** A code adapter emitting
  source-typed refs; the coverage view (specced-but-unbuilt / built-but-
  unspecced). The seam held: a merged spec+code corpus passed the *unchanged*
  Phase-1 gate. Coverage run judged faithful (0/0/0) after a 3→0 convergence.
- **Phase 3 — Reach & polish. 🟡 IN PROGRESS.** Done: the push-button one-command
  UX (specs and specs+code), CI, an in-repo e2e fixture, the design-doc/ADR
  adapter, host-theme detection, and **renderer v2 — the editorial design system
  as the default output, with per-section disclosure and per-layout diagram
  motion** (spec `specs/001-renderer-v2/`). Later: the optional voice profile;
  richer diagram affordances.
- **Phase 4 — (Strategic, decide later) Standalone engine / OSS.** The
  precondition is now met (the core has earned it across ≥2 real source types —
  spec-kit and code). The seam makes this a packaging exercise, not a rewrite.

### 11.5 The discipline that keeps "right, not narrow" honest

The risk in a rich architecture is building the general platform before the
concrete thing works. The protection is *not* shrinking the architecture — it is
**phase discipline**: every seam and invariant is real from Phase 1, but a later
phase's *surface* (code adapter, detection, OSS) is not allowed to block the
phase before it from shipping. Right architecture, sequenced delivery, no
teardowns. That is the best-practice arc for this system.
