# HANDOFF — spec-kit-atlas (resume after compaction)

> Written at ~99% context. If you're resuming cold: read this top-to-bottom.
> Decisions are made and recorded — don't re-litigate. Full rationale is in
> `DESIGN.md` (esp. §11). This repo IS the memory.

## What this is

`spec-kit-atlas` — a Claude Code **skill** that synthesizes a project's
scattered spec-kit specs into ONE faithful, interactive, whole-system
architecture **storybook** (HTML). The in-session agent IS the reasoning engine
(no API key, no subprocess); deterministic `uv` scripts hold the parsing, the
fail-closed faithfulness gate, and the renderer. NOT a dashboard, NOT a per-spec
renderer — a atlas. Organized by architecture, not spec history; spec
numbers never appear in narrative prose (only in Layer-2 citation chips).

## STATUS: v1 COMPLETE. All work merged to `main`. Repo is clean.

- Remote: https://github.com/ashbrener/spec-kit-atlas — default branch
  `main` (was wrongly pointing at a dead design branch — fixed). Only `main`
  exists remotely; all feature branches pruned. About-description + topics set.
- **Phases 1–3 shipped & merged** (PRs #1–#7): the engine, code-as-source +
  coverage view, push-button UX, CI, design-doc/ADR adapter, theme detection,
  mapping/panel diagram layouts, voice-profile convention, comprehensive README
  with Mermaid diagrams. **93 tests green** (`uv run pytest skill/tests -q`).
- Each phase was proven **faithful (0/0/0)** by adversarial Codex cross-model
  review. Generated proof artifacts in `examples/generated/`.

## THE ONE OPEN THREAD

**project-arc dogfood — PR #51 is OPEN, awaiting the operator's merge.**
- https://github.com/ashbrener/project-arc/pull/51 — branch
  `docs/architecture-storybook`, adds `docs/architecture.html` (a generated,
  faithful 0/0/0 architecture storybook for project-arc).
- This was the first dogfood on a project OUTSIDE the fixture. It succeeded.
  Notable: the Codex gate caught me mis-marking two fully-built subsystems
  (pack-bump lifecycle, decisions ledger) as "not in source" — exactly the
  cold-territory error the gate exists to catch. Corrected to 0/0/0.
- **Next action there:** operator reviews/merges PR #51. Nothing blocking on
  our side. The generated file is also at
  `spec-kit-atlas/.atlas-arc/project-arc-architecture.html`.

## How to run it (the recipe, proven on 2 projects)

```bash
cd ~/Code/AI/spec-kit-atlas
# 1. adapt (specs only, or + code for coverage, or + docs):
uv run python skill/scripts/synthesize.py <repo>/specs --code <repo>/src \
    --work .atlas-<name> --project-name "<name>"
# → writes corpus.json + locators.txt + a hand-off brief.
# 2. the in-session agent reasons extract→reconcile→compose, writing
#    .atlas-<name>/architecture_model.json + document_model.json,
#    citing ONLY locators from locators.txt. At many specs, FAN OUT one
#    extract sub-agent per feature folder (proven: 10 agents for project-arc).
#    Then reconcile (merge overlaps, demote supersessions to history[]) yourself.
# 3. verify (fail-closed) + render:
uv run python skill/scripts/synthesize.py <repo>/specs --code <repo>/src \
    --work .atlas-<name> --out architecture.html
# 4. Codex faithfulness gate (the acceptance bar), iterate to 0/0/0:
codex exec --skip-git-repo-check --add-dir <repo> -o /tmp/rev.txt "<adversarial review prompt>"
```

Reconcile is done via a build script in the work dir (e.g.
`.atlas-arc/build_arc.py`) that loads the digests and pulls `source_refs`
by claim id — so authored structure stays grounded in real citations. This is
the honest shape today: pipeline + gates are proven; reconcile is agent-authored
per run (a fully push-button reconcile UX is not built).

## Architecture (DESIGN §11)

`adapters → source-agnostic core → render`. The core never knows what a "spec"
is — sources become a uniform source-typed `FragmentCorpus`. Three source types
proven: spec / code / design-doc. Faithfulness is code-enforced: `verify.py`
rejects unresolved provenance, ungrounded blocks, empty callouts, missing
coverage note (fail-closed). Stateless: every run is a pure function of inputs;
no persistent product model (that's product-mem's territory — see workstate
PROJECT-BRIEF §10/§13/§15).

Files: `skills/speckit-storybook/SKILL.md` (orchestration algorithm), `skill/scripts/`
(schema, adapter_speckit, adapter_code, adapter_doc, verify, render,
theme_detect, synthesize), `skill/tests/` (93 tests), `examples/`,
`DESIGN.md` (§11 = resolved architecture).

## What's NOT done (deferred, deliberate — not gaps)

- **Phase 4** (DESIGN §11.4): extract the source-agnostic core as a standalone
  "fragments → faithful read-model" engine / possible OSS. Precondition met
  (≥2 proven sources + clean UX) — but it's a STRATEGIC product-identity call;
  needs explicit operator yes before starting.
- A fully push-button reconcile (today reconcile is agent-authored per run).
- Richer diagram polish; the voice profile is a documented convention, not
  machinery.

## Operational rules (obey)

- ONE mutating shell/tool call per message; serialize writes; read result first.
- Worktree-isolate code-writing subagents. Tests are the gate, not self-report.
- Run `uv run pytest skill/tests -q` locally before any push (exact CI command).
- Push HTTPS-via-gh (project-arc remote is SSH, no key):
  `git -c credential.helper='!gh auth git-credential' push https://github.com/ashbrener/<repo>.git <branch>`
- NO AI-attribution / Co-Authored-By trailers in commits.
- Toolchain is `uv`, never pip.
- `.atlas*/` work dirs are scratch (`.atlas/` is gitignored;
  `.atlas-arc/` is untracked scratch — don't commit it).
- Cross-model review = Codex (`codex exec`, ChatGPT-authed, no key). "wingman"
  IS Codex.

## Ecosystem context

Part of the `workstate` family (hub: `~/Code/AI/workstate-schema/`
RESUME-INDEX.md + PROJECT-BRIEF.md). Siblings: spec-kit-linear (shipped),
spec-kit-jira, project-arc (the dogfood target), spec-kit-red-team. atlas
is deliberately NOT in the `workstate-*` family (it reads specs directly, not a
tracker sink) — name stays `spec-kit-atlas`.
