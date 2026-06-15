# Implementation Plan: Conform to arch-governance contracts (the reader)

**Branch**: `004-conform-governance` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-conform-governance/spec.md`

## Summary

Make synthesis a faithful **reader** of the governance contracts: reconcile its cross-repo
relation vocabulary to the contract's (`derived_from/cites/implements/supersedes/references`, with
the docs↔spec edge → `references`), read bare `ADR-NNN` under a repo's configured namespace,
consume a declared `.spec-arch-domain.yml` as the source-of-truth topology (with the existing
workspace record as presentation overlay + fallback), grade every cross-repo fact by evidence tier,
and vendor the contracts with a CI drift guard. All in `discover_links.py` / `synthesize_atlas.py` /
`schema.py` plus a small config-reader and a vendored-contract test — the faithfulness engine and
`verify`/`verify_links` gates are untouched.

## Technical Context

**Language/Version**: Python ≥3.11

**Primary Dependencies**: `pydantic` (existing) + **`pyyaml`** (new — the governed configs
`.spec-arch-governance.yml` / `.spec-arch-domain.yml` are YAML; reading them needs a YAML parser).
`pyyaml` is a generic library, **not** a dependency on the governance extension — conformance stays
"in code, as a format."

**Storage**: Files only (corpora, IR, vendored contract copies). N/A otherwise.

**Testing**: `uv run pytest skill/tests -q` — new governed + ungoverned fixtures; a contract-drift test.

**Target Platform**: Local CLI / Claude-Code skill (deterministic, offline-capable except CDN fonts).

**Project Type**: Single project (library + CLI scripts under `skill/scripts/`).

**Performance Goals**: Deterministic, byte-identical output for identical inputs (no clock/rng).

**Constraints**: Read-only on consumer repos; **no runtime/import dependency** on the governance
extension; an ungoverned project's output is **unchanged** from the pre-feature baseline.

**Scale/Scope**: Five additive changes across ~4 existing scripts + 1 new reader module + vendored
contracts; no schema-breaking changes to existing IR.

## Constitution Check

*GATE: must pass before Phase 0; re-checked after Phase 1.*

- **I. Faithfulness is architectural** — ✅ untouched. This feature enriches what the reader
  *extracts/renders*; `verify.py`/`verify_links.py` unchanged. Declared facts are graded highest;
  guessed facts stay graded `identifier`/`prose` — more honest, not less.
- **V. Generated, never authored** — ✅ vendored contract copies are pinned data the reader conforms
  to; nothing in the output is hand-authored. Manifest/config are *read*, never written.
- **General-reader / source-agnostic core** — ✅ governed signal enters via the existing
  adapter/discovery seam; the core still reasons over fragments + a LinkGraph.
- **Conform-as-format** — ✅ no runtime dep on the extension; vendored copies + a drift test.
- **No consumer names** — ✅ neutral examples only (`CORE`/`API`/`WEB`).

One new third-party dependency (`pyyaml`) → recorded in Complexity Tracking. No constitution
violations.

## Project Structure

### Documentation (this feature)

```text
specs/004-conform-governance/
├── plan.md          # this file
├── research.md      # Phase 0 — decisions (incl. the resolved docs↔spec → references)
├── data-model.md    # Phase 1 — relation set, manifest member, topology resolution, evidence tiers
├── quickstart.md    # Phase 1 — how a governed project is read
├── contracts/       # Phase 1 — the reader-conformance contract + vendored-file references
└── tasks.md         # Phase 2 — /speckit-tasks (not created here)
```

### Source Code (repository root)

```text
skill/scripts/
├── schema.py            # LinkRel → contract relations (add `cites`; rename `derives_from`→`derived_from`; drop `specified_by`)
├── discover_links.py    # _typed_edge → contract relations; bare ADR-NNN recognised + namespace-qualified; evidence tiers tagged
├── synthesize_atlas.py  # load .spec-arch-domain.yml (validated) as topology source of truth; workspace.json = overlay + fallback
├── gov_config.py        # NEW — read .spec-arch-governance.yml (repo namespace) + .spec-arch-domain.yml (topology); pyyaml
└── vendor/
    ├── vocabulary.json     # NEW — pinned copy @0.2.0 (the conformance target)
    └── domain.schema.json  # NEW — pinned copy (manifest shape)

skill/tests/
├── test_contract_conformance.py  # NEW — LinkRel/roles/kinds/evidence == vendored vocabulary.json (drift guard)
├── test_gov_config.py            # NEW — governed-config + domain-manifest reading, precedence, fallback
├── test_discover_links.py        # UPDATE — relation names + bare-ADR qualification + evidence tiers
└── fixtures/governed/            # NEW — a neutral governed multi-repo fixture (CORE/API/WEB)
```

**Structure Decision**: Single project; all changes live in the existing `skill/scripts/` +
`skill/tests/` trees, plus a `vendor/` dir for the pinned contracts. No new top-level layout.

## Complexity Tracking

| Addition | Why needed | Simpler alternative rejected because |
|---|---|---|
| New dep `pyyaml` | The governed configs/manifest are YAML; the reader must parse them to consume declared topology | Hand-rolling a YAML subset parser is fragile; `tomllib` (stdlib) can't read YAML; the manifest format is fixed as YAML by the contract |
| Vendored copies of `vocabulary.json` + `domain.schema.json` | Drift guard (ARCH-ADR-000 §8) — conform in code without a runtime dependency | Importing from the extension would create the runtime coupling the whole design forbids |
