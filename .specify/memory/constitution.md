<!--
SYNC IMPACT REPORT
==================
Version: 1.0.0 (initial ratification)
Ratified: 2026-06-13 | Last amended: 2026-06-13
Origin: encodes the non-negotiable invariants already governing this project
  (DESIGN.md §11.2). No principle is new — this constitution makes them the
  formal, citable rulebook now that the repo self-hosts spec-kit.
Templates reviewed: plan/spec/tasks/checklist templates consistent (generic spec-kit).
-->

# spec-kit-atlas Constitution

The non-negotiable rules that govern this project. Atlas turns a project's scattered
spec-kit specs (and optionally code + design docs) into ONE faithful, plain-English,
interactive architecture storybook. These principles protect the only thing that makes
such a document worth trusting: **faithfulness**.

## Core Principles

### I. Faithfulness is architectural (NON-NEGOTIABLE)
Every asserted claim MUST carry ≥1 `source_ref` resolving to a real source fragment. A
sentence resting on no source cannot be written. The `verify.py` gate enforces this and
**fails closed** — a non-zero exit means the run is not done; fix the model, never the gate.
*Rationale: a confident, wrong architecture document is worse than none.*

### II. Organized by architecture, not by spec history
The narrative reads "here is how this system is built," never "spec 001 says…". **No spec
numbers, FR/SC codes, or filenames appear in the narrative prose** — they ride only in
Layer-2 citation chips (`source_refs`). *Rationale: a reader wants the system, not its
filing cabinet.*

### III. Current-state only
Where specs evolved, describe only what is true now. A superseded behaviour is demoted to a
single `EvolutionNote` (history) — evidence-gated — never shown as a competing description.
*Rationale: the document is a current map, not a changelog.*

### IV. Fail-closed on gaps
Where the specs leave something open, emit an `unspecified` callout — never invent an answer.
Where they contradict, surface the tension as an open question rather than silently pick.
*Rationale: an honest gap beats a confident fabrication.*

### V. Stateless; generated, never authored
This is a pure function of its inputs. The IR artifacts are a per-run build cache —
regenerated every run, never hand-edited — and the output storybook is a *read* surface, not
a source of truth. To fix a claim, fix the source and regenerate. *Rationale: a hand-edited
output rots into a competing, untrustworthy source.*

### VI. Written for a general reader
The storybook is the plain-English read for a non-specialist; the prose MUST be simpler than
the source markdown it distils. But **simplification never costs faithfulness** — every claim
keeps its source one click away, every gap stays an `unspecified` callout. *Rationale: simpler
on the surface, exactly as true underneath.*

## Architectural Constraints

- **Source-agnostic core.** Inputs reach the core only through adapters that emit a
  source-typed `FragmentCorpus`; the core never knows what a "spec" is. New source kinds drop
  in without a core rewrite.
- **Reasoning vs. determinism split.** The in-session agent performs the reasoning phases
  (extract → reconcile → compose); deterministic Python scripts carry parse, the fail-closed
  verify gate, and render. No phase hides an LLM behind a button.
- **Toolchain is `uv`** (never pip), Python ≥3.11, pydantic the only runtime dependency.

## Quality Gates

- `verify.py` (and, for portals, `verify_links.py`) is the automated, fail-closed half — it
  is never edited to pass.
- The human/cross-model half: the generated storybook must be as faithful and as readable as
  the hand-written north-star (`examples/speckit-linear-architecture.html`).
- `uv run pytest skill/tests -q` is green before any push.

## Governance

This constitution supersedes ad-hoc practice. Amendments are versioned (semver: MAJOR =
remove/redefine a principle; MINOR = add a principle or materially expand one; PATCH =
clarification). The faithfulness invariant (I) and the generated-never-authored rule (V) are
load-bearing; weakening either is a MAJOR change requiring explicit justification recorded
here. DESIGN.md carries the full rationale; on any conflict, this document governs intent and
`verify.py` governs enforcement.

**Version**: 1.0.0 | **Ratified**: 2026-06-13 | **Last Amended**: 2026-06-13
