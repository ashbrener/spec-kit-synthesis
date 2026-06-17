# Research — Read the governed citation slots

## D1 — Read the declared slots; don't only infer from prose

**Decision**: Add a deterministic `discover_slot_edges` pass that parses the `derived_from`/`cites`
front-matter slots and emits typed edges directly.

**Rationale**: Governance produces the cross-tier signal as explicit slots; synthesis was recovering
edges only from identifiers that coincidentally appear in two repos' prose, so a correctly-declared
`derived_from: [docs:002-architecture]` produced no edge (the source body never repeats the slug —
verified: 0 edges). Reading the slot is the direct, faithful path and the whole point of the gov
contract. The existing identifier/prose discovery stays as additive fallbacks.

## D2 — Grade slot edges `declared` (clarified)

**Decision**: Slot edges carry the `declared` evidence tier (top of declared > identifier > prose),
broadening `declared` from "manifest topology" to "explicitly declared (manifest OR citation slot)".

**Rationale**: An author explicitly declaring a citation in a governed slot is strictly more
trustworthy than an inferred shared id or a prose mention; dedup should prefer it. Reusing the
existing enum avoids a governance contract change. (Recorded in the spec's Clarifications.)

## D3 — Slot-first merge + feature-pair dedup, NOT a coarser `_key`

**Decision**: Merge slot edges first; keep the locator-precise `_key`; add a feature-pair-aware
suppression that drops a lower-tier inferred edge already covered by a declared slot edge.

**Rationale**: The link graph feeds BOTH the atlas and the clusterer. Clustering union-finds on edge
endpoints, so it needs **per-feature** edges — coarsening `_key` to `(src.origin, dst.origin, rel)`
would collapse distinct feature pairs and under-merge capabilities. But a slot edge and an incidental
identifier edge for the *same* feature pair can have different representative locators, so exact-key
dedup won't collapse them. The fix: a targeted suppression keyed on `(src-feature, dst-feature, rel)`
that only removes *lower-tier* duplicates of a declared edge — preserving distinct same-tier edges
(two different FR identifier edges survive) while satisfying "collapse slot-vs-inferred to one,
declared wins" (FR-009 / SC-003). Endpoints use a deterministic **feature representative** (min
fragment id of the feature) so they're stable.

## D4 — Front-matter location + parsing

**Decision**: Parse YAML front-matter (the `--- … ---` preamble) of the feature's `spec.md`
(derived_from) and `plan.md` (cites) fragments, using `pyyaml` (already a dependency). The speckit
adapter emits the pre-heading preamble as its own fragment, so the front-matter is the text of that
fragment.

**Rationale**: Matches the contract's `slots` (`derived_from`→spec.md front-matter, `cites`→plan.md
front-matter). Honors the per-repo `citation_keys` for the actual key names; falls back to the
documented defaults (`source_specs→derived_from`, `adrs→cites`).

## D5 — Unresolved slots mint nothing (fail-closed on gaps)

**Decision**: A slot whose target (source member/feature, or decision) isn't in the workspace mints
no edge and is collected into a returned unresolved-notes list; the fail-closed `verify_links` gate is
unchanged.

**Rationale**: Principle IV — an honest gap beats a fabricated edge. (An optional repo not checked out
is the common case; its citations simply don't resolve, and that's reported, not invented.)

## Cross-cutting

- **No new dependency** (pydantic + pyyaml). **No external graph.** Deterministic + reproducible.
- **No-slot parity (SC-005)**: `discover_slot_edges` returns nothing when no slots are present, so the
  merged graph is byte-identical to before for ungoverned / non-slotted workspaces.
- **Fixture**: `fixtures/slots/` — a source repo with feature `002-architecture` whose spec body does
  NOT contain that slug; a build repo whose `spec.md` front-matter declares
  `derived_from: [<source>:002-architecture]` and whose `plan.md` front-matter declares
  `cites: [<NS>-ADR-001]`. Proves the meld lights up from the declared slot, not prose coincidence.
