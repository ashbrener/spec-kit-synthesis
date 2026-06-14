# Feature Specification: Documentation Portal — cross-repo traceability atlas

**Feature Branch**: `002-portal-north-star`

**Created**: 2026-06-08

**Status**: Draft (north-star)

**Input**: User vision — "synthesis builds documentation (authored with spec-kit) that becomes the
source context for building the codebase; synthesis should be an interactive documentation portal
over a `docs/` repo that drills across to the upstream specs that created it and the downstream
specs/code derived from it." Grounded by the `portal-north-star` design exploration (three
independent architecture perspectives + a synthesis) and the renderer-v2 engine (`specs/001-renderer-v2/`).

## Overview

The **portal** is the **SITE** layer over the existing storybook **PAGE**. It compiles many per-repo
storybooks and overlays a *verified* cross-repo **traceability graph** — intent → docs → specs →
code — navigable in both directions. It is a **static, self-contained, deterministic** artifact,
**additive** over renderer v2: the per-page reasoning engine (adapters, reconcile, compose,
`verify.py`, `render.py`) is untouched.

Two layers, cleanly separated:
- **PAGE** *(exists — spec 001):* a deterministic storybook, one self-contained HTML per scope,
  rendered by `render.py` as a pure `model + theme → bytes` function.
- **SITE** *(this spec):* a workspace of per-repo pages + an **atlas** page + a `search.json` + a
  verified `LinkGraph`, all static. The whole site is a pure function of
  `(workspace manifest + pinned member repos + theme) → a directory of files`.

The provenance citation chip — today a dead `#refs` link — **becomes the cross-repo navigation
primitive**: it resolves to a sibling page+anchor (docs→spec) or a bundled source-view (claim→code).

## Clarifications

### Session 2026-06-08 (decisions locked)

- **Audience — the readable storybook is the product.** The portal exists to serve the
  plain-English storybook for *normal people*; its prose is deliberately simpler than the source
  markdown, with every claim's source always one click away (citation chip → spec page → bundled
  source-view). The atlas / graph / `verify_links` machinery is **subordinate**: it exists so the
  simple read stays trustworthy and traceable, and the reader never sees it. (DESIGN §11.2 #8.)
- **Delivery — STATIC, not an SPA.** A directory of self-contained storybook pages + an atlas page +
  `search.json`. Navigation, search, and click-through drill-down come from plain `<a>` links + the
  inline vanilla JS already in `render.py`. This preserves byte-determinism, `file://` portability,
  and the fail-closed gate that an SPA would sacrifice for navigation polish.
- **v1 scope — one workspace first.** Build the docs repo + its own specs + code as the first
  workspace; prove page + atlas + drill-down; then fan out to more repos. (Target architecture is
  per-repo pages + graph either way.)
- **Drill-down / hosting — the deployed site is SELF-CONTAINED.** Every drill target lives inside
  the built artifact, so it works on Netlify/Vercel, offline, and `file://`, with no sibling
  checkout and no external auth:
  - *docs → spec* resolves to the spec's rendered page+anchor **inside the portal**.
  - *claim → source* resolves to a **bundled source-view** generated from the cited corpus
    fragment (the adapters already capture each fragment's text). Only **cited** fragments are
    bundled, never whole repos.
  - An optional per-repo **host base-URL** in the manifest MAY add a secondary "view source on
    host" link for *public* repos — off by default (private-safe).
- **Provenance — `SourceRef.origin`.** `SourceRef` gains one optional field, `origin` (the
  workspace-member id); the resolution key becomes `(origin, locator)`. `origin` defaults to
  `project_name`, so every existing single-repo run and golden file is unaffected (backward-compatible).
- **Traceability graph — a verified `LinkGraph` IR, fail-closed.** A new `verify_links.py` copies
  `verify.py`'s discipline: a cross-repo edge ships only if **both endpoints resolve** in the
  workspace union **and** it carries **grounded evidence** — a manifest declaration, a shared
  *qualified* identifier (e.g. `FR-025`, a contract name, a feature slug), or a literal prose quote
  found in the source fragment. Never an inferred "these feel related."
- **Discovery — tiered (the §5.4 evidence ladder).** Declared edges trusted always; shared-qualified-
  identifier edges emitted deterministically (no LLM); prose-reference discovery (LLM) only **within
  manifest-declared repo pairs** (no all-pairs blow-up). Ambiguous matches demote to open-questions,
  not edges.
- **Atlas — renders the verified graph, coverage-honest.** The atlas is a deterministic page driven
  by the verified `LinkGraph`, drawn with the existing `DiagramGraph` `hub`/`stack` layouts. It lifts
  the §5.8 coverage-honesty invariant: it never implies a complete intent→docs→specs→code chain when
  the real repos populate only part of it (e.g. one repo with docs+code but no specs; another with specs, no
  docs). A *synthesized meta-narrative* atlas is deferred.
- **Intent + workspace root.** `intent` is an **optional** origin — rendered honestly-absent rather
  than invented; a Linear/issues adapter is added later only if real intent artifacts exist. The
  **workspace manifest lives in the docs repo** (the source-context hub); each member is **pinned to
  a commit** so the site is reproducible (determinism otherwise dies at the repo boundary).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Drill from a doc to its spec to its code (Priority: P1)

A reader opens the docs portal, reads a claim, and clicks its citation chip → jumps to the spec
page+anchor that specifies it (an internal sibling page), then clicks again → sees the bundled
source-view of the implementing code symbol. All within the deployed site.

**Acceptance**: every chip with a verified link resolves inside the artifact; no chip depends on a
sibling checkout or external host to render its target.

### User Story 2 — Hosted, no checkout, no auth (Priority: P1)

An operator deploys the static site to Netlify/Vercel. Drill-down works for a viewer with no access
to the source repos and no local checkout.

**Acceptance**: a hosted build supports full docs→spec→source drill-down offline-equivalently
(self-contained); optional host links appear only for repos that declared a public base-URL.

### User Story 3 — Verified, fail-closed links (Priority: P1)

A reviewer trusts that every cross-repo link is real. A fabricated or unresolved link fails the build.

**Acceptance**: `verify_links.py` exits non-zero on any edge whose endpoint doesn't resolve or whose
evidence isn't grounded; no such edge appears in the rendered atlas.

### User Story 4 — Honest atlas on partial chains (Priority: P2)

An exec views the atlas graph (intent→docs→specs→code). Where a chain is incomplete (no specs yet,
no docs yet), the atlas says so rather than implying full traceability.

**Acceptance**: the atlas frames its own coverage and renders partial chains honestly-incomplete.

### Edge Cases

- A member repo with no specs (docs+code only) or no docs (specs only) → the chain renders partial,
  not fabricated.
- A generic token (`config`) shared across repos → MUST NOT mint an edge (only qualified identifiers).
- A drill target that moved/renamed between builds → fails the build loudly (no silent 404).
- A single-repo run (today's usage) → unchanged: `origin` defaults to `project_name`, gate untouched.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** The portal MUST be a static, deterministic, self-contained artifact — a pure function of
  `(workspace manifest + pinned member repos + theme)`.
- **FR-002** The PAGE renderer (`render.py`) and the extract→reconcile→compose→verify pipeline MUST be
  reused **unchanged**; one storybook per scope.
- **FR-003** `SourceRef` MUST gain an optional `origin`; the resolution key becomes `(origin, locator)`;
  `origin` defaults to `project_name` (existing tests/goldens pass).
- **FR-004** Every drill target MUST resolve **inside** the deployed artifact: docs→spec = internal
  page+anchor; claim→source = a bundled source-view built from the cited fragment. No dependency on
  sibling checkouts or external hosts at view time.
- **FR-005** The build MAY add a secondary "view source on host" link per repo when that repo declares
  a public base-URL in the manifest; this is off by default.
- **FR-006** Cross-repo links MUST be a verified `LinkGraph` IR; `verify_links.py` MUST be fail-closed
  (`ENDPOINTS_RESOLVE`, `EVIDENCE_PRESENT`, `EVIDENCE_GROUNDED`). No inferred links ship.
- **FR-007** Link discovery MUST be tiered: declared (trusted) + shared-qualified-identifier
  (deterministic, no LLM) + prose-reference (LLM, only within declared repo pairs). Ambiguous →
  open-question, not edge.
- **FR-008** The atlas MUST render the verified `LinkGraph` via existing `DiagramGraph` layouts and MUST
  be coverage-honest (frame its own scope; render partial chains honestly).
- **FR-009** The workspace manifest MUST pin each member to a commit and MUST live in the docs repo.
- **FR-010** The faithfulness engine (adapters, reconcile, `verify.py`) MUST remain unchanged; only
  bundling cited fragments into source-views is added at the SITE layer.

### Key Entities

- **WorkspaceManifest** — `members: [{ origin, repo, role ∈ docs|spec|code|intent, adapter, pin
  (commit), base_url? }]`, `theme`. Lives in the docs repo.
- **SourceRef** *(extended)* — adds `origin`; key `(origin, locator)`.
- **LinkGraph** — `edges: [{ src(origin,locator), dst(origin,locator), rel ∈ derives_from |
  specified_by | implements | supersedes | references, evidence{ kind ∈ declared|identifier|prose,
  detail } }]`. A per-run, diffable build IR (sibling to `architecture_model.json`).
- **Site** — per-repo storybook pages, an atlas page, `search.json`, and bundled source-views.

## Success Criteria *(mandatory)*

- **SC-001** A hosted (Netlify/Vercel) build supports full docs→spec→source drill-down with no sibling
  checkout and no auth.
- **SC-002** Same inputs (pinned manifest + repos + theme) → byte-identical site.
- **SC-003** A fabricated or unresolved cross-repo link fails the build (`verify_links` non-zero).
- **SC-004** Existing single-repo runs and golden tests are unaffected (origin defaults).
- **SC-005** The atlas never over-claims completeness on partial chains.

## Assumptions

- The user controls the member repos; bundling their own *cited* spec/code fragments into their own
  portal is acceptable.
- Out of scope (deferred, adjacent to DESIGN §8): cross-repo reconciliation into one unified
  narrative ("portfolio synthesis"); a synthesized meta-narrative atlas; the intent adapter (until
  real intent artifacts exist).
