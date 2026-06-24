# Phase 0 Research: Contract-Driven Capability Clustering

## Empirical basis (post-#27 assessment, real docs-authority workspace)

Measured on the live workspace after spec 009 merged: corpus = docs 695 / backend 231 / frontend 116. Result: 5 capabilities, but **three near-duplicate ~380-fragment catch-alls** (each swallowing nearly all build work) + 2 small planned. Strong edges: 18 `derived_from` + 10 `cites`; **19 are declared slots, 0 unresolved**; the rest are identifier-inferred — including **7 spurious build↔build `derived_from`** edges (e.g. `backend:002-auth-api derived_from frontend:001-frontend-scaffold` — backwards, minted from a shared token). ADRs are cross-cutting (one infra ADR cited across auth + admin + frontend). Repo-meta/archive ingested as background noise (`99_Archive/`, `CLAUDE.md`, `RESUME.md`, `BACKEND_HANDOFF.md`, `Writing_Standards.md`, `_Audits/`).

## Decision 1 — membership is conferred by evidence tier

**Decision:** capability membership is conferred only by `declared` edges + same-feature grouping; an `identifier` edge confers membership **only between a source and a build feature**; build↔build identifier edges and all `prose` edges never confer membership.

**Rationale:** the evidence ladder (`declared > identifier > prose`) is already the project's grounding contract. Letting identifier edges place fragments in capabilities is what chained the build features into catch-alls — and the worst offenders are build↔build (a shared FR-code between two build specs means nothing). Source↔build identifier is retained because it is a genuine spec→implementation signal *and* it's the only cross-tier signal an un-governed / single-repo workspace has (declared-only would leave those workspaces with every feature standing alone — an unacceptable regression for the original use case).

**Alternatives:** *declared-only* (purest, but regresses un-governed workspaces); *keep all strong edges* (status quo — the bug).

## Decision 2 — hubs are rendered faithfully and flagged, never re-shaped

**Decision:** the reader does NOT demote, re-anchor, or split a broad/hub feature. It renders the declared grain as-is and adds an additive "broad (hub)" annotation (count of distinct features that declare `derived_from` the anchor).

**Rationale:** faithfulness is the non-negotiable principle. A capability that is broad because many features genuinely declare `derived_from` one doc is *true* — re-shaping it would be the reader inventing a grain the contract doesn't state. The honest move is to render it and make the coarseness a visible, actionable governance signal. The crisp cross-tier split is achieved by governance declaring finer features, not by reader heuristics.

**Alternatives considered & rejected:**
- *Hub demotion / leaf-anchoring* — the reader chooses the grain; defensible but it re-shapes the declared structure and papers over the governance gap. Also can't distinguish a coarse hub (6 unrelated dependents) from a fine feature with 2 cross-tier dependents (backend+frontend of one capability) — degree alone conflates them. Rejected on faithfulness grounds.
- *Community detection / graph DB / embeddings* — manufactures inferred structure, trades away faithfulness and determinism. Rejected (constitution).

After Decision 1 alone, the three catch-alls stop being near-duplicates (no build↔build contamination); after Decision 2, residual breadth is faithful and flagged. The Auth/Authz/Back-office/Audit split then comes from governance refining the functional docs (handed to the writer session).

## Decision 3 — ingest only source-of-truth (Q3)

**Decision:** the doc adapter's deterministic skip-set excludes archive/audit directories (name contains `archive`/`audit`, case-insensitive) and well-known agent/process meta files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `RESUME.md`, `*HANDOFF*.md`, `WORKTREES.md`), at any depth.

**Rationale:** these are not the documented system — they're process scaffolding. Excluding them removes noise clusters at the source (faithful: don't ingest non-source). Conservative defaults (clearly-meta names + archive/audit dirs); genuine narrative/standards docs are untouched. Same mechanism as the existing hidden-dir/SKIP_DIRS skip (spec 007); additive entries only, so existing fixtures are unaffected.

**Alternatives:** per-repo configurable ignore globs (more flexible; deferred — defaults cover the measured cases and avoid config plumbing in this spec).

## Determinism

All three are deterministic, stdlib-only. Edge gating reads `LinkEvidenceKind` already on each `LinkEdge`; hub count is a deterministic in-degree over declared edges; the skip-set is a pure name test. No clock/rng/iteration-order dependence.
