# Ingestion + classification contract (docs-authority capability signal)

1. **Structure-aware source ingestion.** A `source` member is ingested as merged multi-source: its
   declared `specs_dir` via the speckit adapter (each feature a distinct seed), its declared `adr_dir`
   as ADRs, and its remaining narrative via the doc adapter. A missing `specs_dir`/`adr_dir` simply
   omits that pass.

2. **No double-ingest.** The narrative pass excludes the `specs_dir` and `adr_dir` subtrees by path
   prefix, so no file is ingested both structure-aware and as prose.

3. **Path-prefix exclude.** An ingestion source may declare `exclude` entries; an entry containing
   `/` matches a relpath prefix (exact subtree), a bare name matches a path part. Hidden/tooling dirs
   are always skipped regardless.

4. **Build/standalone unchanged.** A build or standalone member's ingestion is exactly as before.

5. **Cross-tier melding.** A build spec and the source spec it `derived_from` land in the same
   `capability` cluster; a cited ADR rides inside the capability that cites it.

6. **Classification.** Every cluster is labelled `capability` (≥1 spec/code), `decision` (only ADRs),
   or `background` (only narrative) — deterministically, from membership.

7. **Fold-in.** Capabilities are the story's sections; a cited decision renders inline in its
   capability; uncited decisions → a Decisions appendix; background → a short Overview/Background
   section. A lone decision or signal-less narrative is never promoted to a capability section.
   Strict, deterministic background: narrative is never auto-attached to a capability.

8. **Coverage-honest.** Nothing is dropped — every fragment remains reachable (capability / appendix /
   background / catalog).

9. **No new signal or dependency.** The cross-tier signal stays derived_from + cites; no graph system,
   no embeddings, no new runtime dependency. Clustering is deterministic and reproducible.

10. **Gates + scope unchanged.** `verify.py` / `verify_links.py` are untouched; an ungoverned or
    non-docs-authority workspace produces output unchanged from before. Neutral examples only
    (CORE/API/WEB).
