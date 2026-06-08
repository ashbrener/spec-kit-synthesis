# Implementation Plan: Documentation Portal (north-star)

**Branch**: `002-portal-north-star` · **Spec**: `specs/002-portal-north-star/spec.md` · **Date**: 2026-06-08

## Summary

A static, self-contained, cross-repo documentation portal. **PAGE** = the unchanged renderer-v2
storybook; **SITE** = an additive outer layer that federates per-repo corpora, overlays a verified
`LinkGraph`, and renders an atlas + per-repo pages + `search.json` + bundled source-views. One small,
backward-compatible schema change (`SourceRef.origin`) unlocks the whole thing. Derived from the
`portal-north-star` design exploration (provenance-graph · delivery-UX · ingestion-pipeline lenses,
which converged independently) plus the renderer-v2 engine.

## Architecture

```
  workspace manifest (docs repo; members pinned to commits)
        │
        ▼  per member: run its adapter, STAMPED with origin
  adapters (speckit · code · doc)  ──▶  origin-stamped FragmentCorpus per scope
        │
        ▼  UNCHANGED per scope
  extract ─ reconcile ─ compose ─ verify(.py) ─ render(.py)  ──▶  one self-contained PAGE per repo
        │
        ├──▶  LinkGraph discovery (declared · identifier · prose-in-declared-pairs)
        │            │
        │            ▼ fail-closed
        │      verify_links.py (ENDPOINTS_RESOLVE · EVIDENCE_PRESENT · EVIDENCE_GROUNDED)
        │            │
        ▼            ▼
  SITE build: atlas page (DiagramGraph hub/stack over verified LinkGraph)
            + per-repo pages + search.json + bundled source-views (cited fragments only)
            = a static directory; pure fn(manifest + pinned repos + theme)
```

The citation chip becomes the navigation primitive: when a verified link exists it resolves to a
sibling page+anchor (docs→spec) or a bundled source-view (claim→code); otherwise it falls back to the
References appendix (today's behaviour).

## Constitution Check (DESIGN §11.2)

- **Determinism — PASS.** Site = pure `fn(manifest + pinned members + theme) → bytes`. M page renders +
  one atlas render + one `search.json`, each already byte-deterministic; members pinned to commits.
- **Faithfulness is architectural — PASS.** Per-page `verify.py` unchanged; cross-repo links gated by a
  fail-closed `verify_links.py` (the cross-repo analogue of "a claim with no source cannot exist").
- **Source-agnostic seam — PASS.** The portal is the adapter-federation layer; the core never learns
  what a repo is. `SourceType` already enumerates `spec|design_doc|code` — no new source type needed.
- **Stateless — PASS.** `LinkGraph`/`atlas.json` are per-run, diffable build IR, regenerated each run,
  never authoritative.
- **Composition ≠ markup ≠ theme — PASS.** The atlas reuses `DiagramGraph` + the theme tokens; no
  second visual system.

## Reuse from renderer v2 (verbatim unless noted)

- **`render.py`** — the PAGE renderer, unchanged. Only additive: `_cite_chip` carries a resolved
  `href` when a verified link exists (graceful `#refs` fallback otherwise).
- **The full extract→reconcile→compose→verify pipeline + `SKILL.md` algorithm** — run once per scope,
  unchanged.
- **`schema.py` `SourceRef`/`Fragment`/`FragmentCorpus`** — `SourceRef` gains one optional field
  (`origin`, default `project_name`); everything else as-is.
- **`verify.py`** — unchanged for per-page faithfulness (its `corpus.locators()` flat-set test keeps
  working once locators are origin-namespaced); the literal template for `verify_links.py`.
- **`synthesize.py` multi-corpus merge + collision check** — already the multi-source seam; the atlas
  orchestrator generalizes it from "merge sources of one repo" to "federate corpora of many repos."
- **The three adapters** — reused as-is; the workspace layer calls each per member and stamps origin.
- **`DiagramGraph` + SVG `hub`/`stack` layouts + theme tokens** — render the atlas/cross-repo graph,
  inheriting the same hand-laid-SVG quality bar (no second visual system).
- **`ArchitectureModel.coverage` / `CoverageItem`** — the in-repo intent-vs-reality precedent and
  conceptual seed for cross-repo edges; the §5.8 coverage-honesty invariant lifts to the atlas.
- **The `.synthesis/` build-IR convention** — reused for `link_graph.json` / `atlas.json`.

## Phases (each ships value; none requires a teardown)

- **Phase A — Origin axis.** Add optional `SourceRef.origin` (default `project_name`), stamp it at the
  three adapter boundaries, key `corpus.locators()` on `(origin, locator)`. `verify.py` untouched;
  goldens/single-repo runs unaffected. *Ships:* `synthesize.py` can merge corpora from multiple repos
  without the locator collision aborting the build.
- **Phase B — Live chips.** Generalize `_cite_chip` from hardcoded `#refs` to a resolved `href` when a
  target is known (fallback `#refs`). One function; the keystone delivery change. *Ships:* chips point
  at the right place even before cross-repo work.
- **Phase C — Workspace manifest + per-repo fan-out.** Add `synthesis.workspace.{json,toml}` (members,
  roles, adapters, origin, pin, optional base_url) and a `synthesize_atlas.py` orchestrator modeled on
  `synthesize.py`: run each member's adapters (origin-stamped), then the unchanged engine per scope.
  *Ships:* a folder of self-contained per-repo storybooks + a plain index — a usable book-of-books with
  zero new reasoning.
- **Phase D — LinkGraph IR + discovery.** Add the `LinkGraph` schema (sibling to `ArchitectureModel`)
  and the tiered discovery pass: deterministic declared + shared-qualified-identifier edges first, then
  agent prose-reference discovery scoped to declared repo pairs. *Ships:* docs→specs→code edges as a
  diffable artifact; cross-page chips become real.
- **Phase E — `verify_links` gate + atlas render + bundled source-views.** Add `verify_links.py`
  (copies `verify.py`'s fail-closed discipline) and render the atlas from the verified graph using the
  existing `hub`/`stack` layouts + `search.json`; emit bundled source-views for cited fragments.
  *Ships:* the full navigable, fail-closed, self-contained portal — a fabricated cross-repo link
  cannot ship, exactly as a fabricated citation cannot today.
- **Phase F (strategic, later).** Optional intent origin (Linear/issues adapter); incremental
  per-repo content-hash caching; rebuild-on-member-change CI. Each additive; none a teardown.

## Risks & mitigations

- **Shared-identifier false positives / link explosion.** → Evidence must be a *qualified* identifier
  (`FR-NNN`, contract name, slug), never a common word; ambiguous → open-question.
- **Cross-repo link rot** (a moved symbol/renamed anchor between builds). → Site regenerated
  statelessly; `verify_links` fails the build loudly; freshness == last full build (CI cadence in F).
- **Reproducibility lost at the repo boundary.** → Manifest pins each member to a commit.
- **Scope creep toward portfolio synthesis (§8).** → Default many-corpora + LinkGraph (per-repo
  faithful pages); atlas renders verified links; cross-repo reconciliation is an explicit later call.
- **Atlas over-claiming completeness.** → Lift the §5.8 coverage-honesty invariant to the atlas.
- **Origin migration touching every adapter/IR/golden.** → Ship `origin` optional-with-default so
  today's runs pass the unchanged gate.

## Verification

- Hosted build (Netlify/Vercel) supports docs→spec→source drill-down with no checkout/auth (SC-001).
- Render twice from the pinned manifest → byte-identical site (SC-002).
- A deliberately-broken cross-repo link fails `verify_links` (SC-003).
- `uv run pytest skill/tests -q` (the v2 suite) stays green — origin defaults (SC-004).
- Atlas frames partial chains honestly on the real examples (SC-005).

## Execution order

A (origin axis) → B (live chips) → C (manifest + fan-out) → D (LinkGraph + discovery) →
E (verify_links + atlas + source-views) → F (intent/CI, later).
