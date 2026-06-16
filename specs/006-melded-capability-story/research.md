# Research — Melded capability story

Decisions behind the plan. The three forks from the spec's Clarifications (granularity, single-page,
build-status level) are settled there; this records the engineering rationale + the remaining choices.

## D1 — Reuse `DocumentModel`, don't invent a meld IR

**Decision**: The melded story is a single `DocumentModel` (sections = capabilities) rendered by the
existing `render.py`. Add only `Block.tier` + `Block.build_status` + `Section.build_status` and two
diagram layouts.

**Rationale**: The page engine already does sections → blocks → altitude-tiered disclosure, citations,
diagrams, and the verify gate already validates a `DocumentModel` against a corpus. The meld's corpus
is simply the **merged** workspace corpus (all members' origin-stamped fragments). So the meld needs
no new reasoning IR, no new gate, and no new renderer — just a few optional fields + grouping logic.
Smallest change that delivers the whole vision; keeps faithfulness mechanics identical.

**Rejected**: a bespoke "MeldModel" with capability/tier as first-class nesting — more schema, a second
renderer, a second gate. Unjustified when `Section`+tagged `Block` expresses the same thing.

## D2 — Deterministic clustering by union-find, no external graph

**Decision**: Cluster capabilities with stdlib union-find over the existing typed, evidence-graded
link graph. Seed one cluster per source-repo feature; attach a build feature to the source feature it
`derived_from` (or shares a qualified `cites`) with; fall back to shared `FR-NNN` / feature-slug;
orphans stand alone. No library, no service.

**Rationale**: The graph is tiny (hundreds of edges) and already typed/graded — the hard part
(deciding which fragments relate) is done. Union-find is ~30 lines, deterministic, reproducible
(SC-006), and reviewable ("backend/007 joined CORE/auth because derived_from"). An external
knowledge-graph tool or graph DB would add a non-deterministic, ungated inference layer + a runtime
dependency — exactly what the faithfulness contract forbids (a fabricated edge must stay impossible).
graphify and friends remain useful for ad-hoc exploration, never as a dependency.

**Over-merge guard**: seed from **source features** and attach build features to their *strongest*
source link (declared/`derived_from` first), rather than raw connected components — so a shared
utility cited by many features does not fuse everything into one mega-cluster. Membership is
deterministic; the agent then groups/﻿names clusters into theme sections (FR-004a) but cannot
fabricate membership.

## D3 — Build status from BOTH coverage and lifecycle

**Decision**: Grade `built / partial / planned` per capability and per tier from two signals:
- **coverage** — build-repo `code` fragments implementing the tier's specs (reusing the existing
  coverage notion: spec_backed → built, specced_only → planned);
- **lifecycle** — artifact presence + `tasks.md` checkbox ratio (all done → built-leaning; none →
  planned; mixed → partial).
Conflicting signals → `partial`, with the tension recorded (never a silent pick — Principle IV).
Absent code → lifecycle-only, confidence noted.

**Rationale**: "What has been built" literally means code exists (coverage), but tasks completion adds
resolution where code is thin or a feature is mid-build. Fusing both is more honest than either alone.
This is why the meld **ingests build-repo code** (the 005 opt-in becomes on for the meld).

## D4 — Two new diagram layouts: `sequence` and `erd`

**Decision**: Add `_layout_sequence` (a cross-tier request path: client → API → store, as ordered
lifelines/steps) and `_layout_erd` (entity/data-model: entities + relationships). Register in
`_LAYOUTS`; emit the motion-hook classes so they animate and settle like the existing eight
(reduced-motion / print safe).

**Rationale**: The two diagram shapes the meld needs most — cross-tier flow and data model — are not
cleanly expressible by the current eight (flow is single-path; panel/stack aren't relational). Adding
two keeps the renderer's "semantic, animated, per-layout" contract intact. `ladder`/`flow` remain for
simpler cases; the agent picks per capability.

## D5 — Single self-contained page; hierarchical index replaces the graph

**Decision**: One HTML page (`index.html`) is the melded story; `atlas.html` (edge-list graph) is
replaced by a deterministic hierarchical **tree** (repo → feature-with-human-title → artifacts) as the
reference surface; drill-to-source pages are kept. Per-member storybook pages are removed.

**Rationale**: A single page is truest to "one story", consistent with the storybook engine, and stays
self-contained/offline. The tree is what the user actually wants for navigation/reference and is fully
deterministic from corpus structure (no reasoning, no fabrication). Human titles come from each
feature's spec H1 / frontmatter, with the feature id as a marked fallback.

## Cross-cutting

- **No new dependencies** (pydantic + pyyaml only).
- **Gates unchanged**: `verify.py` validates the melded doc vs the merged corpus; `verify_links.py`
  still gates the cross-repo edges that clustering consumes.
- **Fixtures**: `governed_ws` gains build-repo **code** (so coverage/build-status is exercised) and a
  hand-authored **melded `document_model`** (so the render + end-to-end tests run without invoking the
  agent — the deterministic machinery is what we test).
- **Reasoning contract** (`commands/atlas.md`): rewritten so the agent consumes per-cluster briefs and
  writes one woven, tier-tagged, build-status-tagged, diagram-forward `DocumentModel`.
