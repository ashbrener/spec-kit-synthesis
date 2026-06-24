# SEED BRIEF — spec-kit-atlas

> **Read top-to-bottom before doing anything.** You are starting cold. This
> brief is self-contained. Full backstory: `~/Code/AI/workstate-schema/PROJECT-BRIEF.md`
> (the hub), especially **§10** which corrected what this thing actually is.
>
> **STATUS: this needs a DESIGN PASS before it is a build.** Do not start
> coding a generator on day one. The hardest, most valuable part is figuring
> out *what a great output document looks like* and *how to synthesize it* —
> design that first (see §6).

---

## 0. What this is, in one plain sentence

`spec-kit-atlas` reads a project's scattered spec-kit specs and produces
**one readable, plain-English document describing the technical architecture
of the whole system** — the thing you'd hand a new developer or a commercial
team to explain "here is how this system is built." Output is HTML (nicer than
PDF/Word).

## 1. What it is NOT (these confusions already happened — avoid them)

- **NOT a dashboard / spec browser.** No "list of specs 001/002/003 with
  statuses." No per-spec cards. The spec NUMBERS are hidden — they're an
  authoring artifact, not how a reader should see the system.
- **NOT a renderer** that makes one spec pretty. It does not transform spec
  003 into nice HTML. It **SYNTHESIZES** many specs into ONE coherent whole.
- **NOT organized by spec history.** Organized by ARCHITECTURE: data model,
  how auth works, the sync engine, the API surface, etc. — the way a system
  is actually structured, as if being built from scratch today.

Think: it produces **the architecture BOOK**, not the **filing cabinet**.

## 2. Why this is genuinely valuable (and uniquely ours)

- A spec-driven project accretes many small specs over time. No single
  document ever says "here is the whole system." New engineers / commercial
  evaluators can't read 30 fragmented specs. This produces the missing
  whole-system narrative.
- **It does NOT overlap product-mem.** product-mem generates structured
  PER-FEATURE / per-entity documents (the card catalog). This produces the
  synthesized WHOLE-SYSTEM story (the book). Different output entirely. (An
  earlier worry that product-mem "already does this" was WRONG once the real
  intent — atlas, not per-spec rendering — was understood.)

## 3. The shape of the thing

```
spec files (specs/NNN-*/)  →  [LLM ATLAS]  →  architecture narrative  →  HTML
```

The middle step is the product. It is a **reasoning task, not a template**:
read N specs (which overlap, contradict, supersede each other, and are written
at different times/phases) and write the coherent current-state architecture.
A template cannot do this; an LLM can. **AI is the engine here, not a helper.**

## 4. Relationship to `workstate` (open question — decide in the design pass)

The trackers (spec-kit-linear/jira) consume STRUCTURED `workstate`
(items/states/hierarchy → issues). This tool needs CONTENT — the prose bodies,
decisions, rationale, clarification history. Two options to weigh in design:
- **(a)** Consume `workstate` (its `body`, `notes`, `links` fields) — reuses
  the same parser/contract as the trackers; keeps the ecosystem coherent.
- **(b)** Read the specs more directly — atlas may want richer raw text
  than the floor `workstate` carries.
Likely answer: consume `workstate` for STRUCTURE (what items exist, how they
relate, lifecycle) + read spec bodies for CONTENT. But this is a real design
decision — do not assume. The schema lives at `~/Code/AI/workstate-schema/`.

## 5. Dependencies / sequencing

- **Build this AFTER `spec-kit-jira` proves `workstate`.** Rationale: Jira is
  the foundation test; once two sinks consume `workstate` you KNOW the format
  and parser are sound, and you've seen real `workstate` output to design
  against. Building atlas on an unproven format risks baking in a flaw.
- It is architecturally INDEPENDENT of the trackers (no shared code beyond
  possibly the parser / workstate). So it can be its own repo, its own
  session, its own pace.

## 6. THE DESIGN PASS (do this FIRST, before any generator code)

The build is easy; knowing what to build is hard. Produce a design doc
(`DESIGN.md` here) that answers:
1. **What does a great output look like?** Find/handwrite ONE excellent
   example architecture doc (even for spec-kit-linear itself, whose specs are
   at `~/Code/AI/speckit-linear/specs/001..003`) — the target to generate
   toward. This is the single most useful artifact; everything else serves it.
2. **What's the section structure** of the synthesized doc? (Overview → data
   model → components → flows → decisions/rationale → ...?) Is it fixed, or
   inferred per-project?
3. **The atlas strategy:** one big LLM pass over all specs? Or map-reduce
   (summarize each spec → synthesize the summaries)? How to handle
   contradictions / superseded specs (use lifecycle state — merged/superseded
   — to weight)? How to keep it deterministic-enough to regenerate sanely?
4. **Input:** workstate, raw specs, or both (§4).
5. **Faithfulness guardrail:** atlas must NOT hallucinate architecture the
   specs don't support. How is the output grounded/citeable back to specs?
   (This is the integrity bar — a confident, wrong architecture doc is worse
   than none. Mirror the "fail-closed / surface uncertainty" discipline from
   the tracker engine: if the specs don't say, the doc says "unspecified," not
   a guess.)

Only after DESIGN.md is agreed should generator code start.

## 7. Naming

`spec-kit-atlas` is the working name (descriptive: it synthesizes).
Alternatives considered: `spec-kit-architecture-doc`. Avoid "portal" / "living
spec site" — both implied the wrong dashboard thing. Confirm the name when the
design firms up.

## 8. product-mem is OUT OF SCOPE. Ignore it.

## 9. Operational rules (same as the rest of the ecosystem)

- ONE mutating shell/tool call per message; serialize writes.
- Worktree-isolate code-writing subagents.
- Cross-model review (gpt-5.5 via wingman) at phase boundaries — especially
  valuable here to critique the ATLAS QUALITY (is the generated doc
  actually good / faithful?).
- Run exact CI locally before pushing. HTTPS-via-gh for pushes (SSH has no
  key). NO AI-attribution trailers in commits.

## 10. First steps when you start this session

1. Read `~/Code/AI/workstate-schema/PROJECT-BRIEF.md` §10 (what this is) + the
   schema.
2. Read `~/Code/AI/speckit-linear/specs/001..003/` as REAL sample input — and
   handwrite the target architecture doc you wish existed for that system.
   That target is your north star.
3. Write `DESIGN.md` (§6). Get it agreed.
4. THEN build the generator toward the target.

North star: **a newcomer reads ONE generated HTML doc and understands how the
whole system is built — accurately, in plain English, with no spec-numbers in
sight.**
