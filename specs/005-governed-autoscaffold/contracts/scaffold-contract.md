# Scaffold conformance contract (what the reader guarantees when auto-scaffolding)

The scaffold reads the governance contracts **as a documented format** — no runtime dependency on the
extension, read-only on consumer repos. Guarantees:

1. **Authority discovery** — From any governed repo, the reader locates the authority that owns
   `.spec-arch-domain.yml`: directly when the launch repo owns it, else by following that repo's
   `.spec-arch-governance.yml` `sources[role=source]` locator, recursing with a cycle guard. The
   discovery result is independent of *which* member the operator launched from (source or build).

2. **Ungoverned fallback** — When no authority can be found, the workspace is treated as ungoverned:
   the reader requires a hand-authored manifest and emits a clear message. It **never invents** a
   manifest. With a hand-authored manifest on an ungoverned workspace, behavior is unchanged.

3. **Derivation faithfulness** — When an authority with a valid domain manifest is found, the derived
   manifest has **exactly one member per declared domain member**. Each member's source location,
   role, and namespace come from the domain manifest (graded `declared`). What to ingest comes from
   that repo's own `.spec-arch-governance.yml` (`specs_dir`, `adr_dir`). The reader derives **no**
   member, path, or ingestion location the governance files do not declare.

4. **Merged multi-source ingestion** — A single member's corpus may merge several sources (specs
   ingested structure-aware; the declared `adr_dir` ingested as decision records even when not
   filename-detectable; free-form docs for a source repo). The 1:1 member↔domain-member mapping is
   preserved (one index card per repo).

5. **Build-repo code is opt-in** — By default a build repo contributes specifications only; code is
   ingested only when an operator manifest overlay enables it.

6. **In-memory by default** — The derived manifest is carried in-memory; the reader writes **no**
   manifest file into any consumer repo. The domain manifest is resolved from the discovered authority
   path, so the launch location is decoupled from where the domain manifest lives.

7. **Operator overlay** — A hand-authored manifest, when present, overlays presentation
   (title/description/theme) — which always wins — and may add members or override a derived member
   (including enabling code).

8. **Transparency** — Before any reasoning, the reader emits a scaffold report naming, per member, the
   `declared` role/namespace/locator and the per-repo `specs_dir`/`adr_dir` read, plus every skipped
   member. Nothing is inferred silently.

9. **Additive-only** — The scaffold runs as setup in front of the unchanged pipeline (adapt →
   per-member reasoning → fail-closed `verify_links.py` → render). It alters none of those stages, and
   the existing evidence tiers / coverage-honest atlas output are unchanged.

Conformance is read against the same vendored contract copies as 004
(`skill/scripts/vendor/{vocabulary.json,domain.schema.json}`); the domain manifest is validated via
the existing `gov_config.read_domain_manifest` before any derivation.
