# Slot-reading conformance contract (what the reader guarantees)

1. **Conformance.** Synthesis vendors the published contract at the pinned version (`vocabulary.json
   @0.3.0`) and reads its `citation_slots` as a documented format — no runtime dependency on the
   extension; the drift guard fails the build if the vendored copy diverges.

2. **Slot location + keys.** `derived_from` is read from a feature's `spec.md` front-matter and
   `cites` from its `plan.md` front-matter; the front-matter key names honor the repo's configured
   `citation_keys`, else the documented defaults (`source_specs→derived_from`, `adrs→cites`).

3. **derived_from resolution.** `<source-member-id>:<spec-feature-id>` → a `derived_from` edge from the
   citing spec to the named source feature (cross-repo). A bare `<spec-feature-id>` → intra-repo.

4. **cites resolution.** A qualified `<NS>-ADR-NNN` → a `cites` edge to that decision (cross-repo); a
   bare `ADR-NNN` → qualified under the citing repo's namespace (intra-repo), as in spec 004.

5. **Trust.** Slot edges are graded `declared` — the highest evidence tier; on a duplicate feature
   pair+relation they win over inferred (identifier/prose) edges.

6. **No fabrication.** A slot value that doesn't resolve in the workspace mints no edge and is
   reported; the fail-closed `verify_links` gate is unchanged.

7. **Additive + non-regressive.** Slot edges merge with the existing declared/identifier/prose
   discovery; clustering still receives per-feature edges; with no slots present the graph is
   byte-identical to before, and the single-repo storybook is unchanged.

8. **Deterministic, no new dependency.** Parsing + resolution are deterministic, reproducible, and add
   no runtime dependency. Neutral examples only (CORE/API/WEB).
