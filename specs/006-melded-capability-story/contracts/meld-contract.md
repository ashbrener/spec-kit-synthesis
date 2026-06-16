# Meld conformance contract (what the melded SITE layer guarantees)

1. **One story, by capability.** The portal renders as a single self-contained HTML page whose
   top-level sections are capabilities (not repositories). No standalone per-repository storybooks are
   produced.

2. **Woven tiers.** Each capability opens with a functional narrative (source/docs layer, always
   visible) and offers per-tier technical disclosures (one per build tier), each sourced from and
   linking to its own repository via drill-to-source.

3. **Deterministic, reviewable clusters.** Capability membership is computed by deterministic
   clustering (union-find) over the existing typed, evidence-graded link graph — reproducible across
   runs, with the join evidence recorded. There is NO dependency on any external graph system,
   knowledge-graph tool, graph database, or embeddings linker, and no new runtime dependency. The
   agent may name/group clusters into themes but cannot fabricate or split membership.

4. **Build-status honesty.** Every capability and tier is graded built / partial / planned from BOTH
   code coverage and spec lifecycle; conflicting signals resolve to `partial` with the reason stated;
   status is never asserted beyond the evidence. Planned work renders faded with a marker.

5. **Human-titled sources.** Every citation carries a human-readable title (feature title + artifact
   kind + repo); per-section sources render as a table, never as bare machine filenames.

6. **Hierarchical index.** The reference surface is a deterministic tree (repo → feature-title →
   artifacts), replacing the edge-list graph; every leaf drills to source.

7. **Faithfulness unchanged.** The melded `DocumentModel` is validated by `verify.py` against the
   merged workspace corpus, and cross-repo edges by `verify_links.py` — both fail-closed, both
   unedited. A claim or edge with no resolving source cannot ship.

8. **Honest coverage.** Unclustered fragments are surfaced, never dropped; a capability with only one
   tier present shows only that tier — missing tiers are never fabricated.

9. **Unchanged surfaces.** The single-repo storybook (PAGE-layer) reasoning contract, the adapters,
   and the gates are untouched; the meld is purely a SITE-layer re-architecture.

Neutral examples only (CORE/API/WEB) in all source, docs, tests, and fixtures.
