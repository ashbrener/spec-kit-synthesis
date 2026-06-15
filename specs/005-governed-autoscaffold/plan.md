# Implementation Plan: Governed auto-scaffold + one-command atlas (the reader)

**Branch**: `005-governed-autoscaffold` | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-governed-autoscaffold/spec.md`

## Summary

On a governed workspace, an operator should produce the multi-repo portal with **one command and
zero hand-authored manifest**. This plan adds a deterministic, read-only **scaffold** in front of
the existing atlas pipeline: discover the authority repo that owns `.spec-arch-domain.yml` (from the
cwd, or by following a build repo's `sources` pointer to its source repo), derive an **in-memory**
`WorkspaceManifest` from the declared signal (one member per domain member, each with **merged
multi-source ingestion** — structure-aware specs + the declared ADR location), print a reviewable
scaffold report, then hand off to the unchanged adapt → reason → verify → render stages. A
hand-authored manifest, when present, overlays presentation and may add members. An ungoverned
workspace is unchanged (a manifest is still required). No engine change, no verify-gate change, no
runtime dependency on the governance extension.

## Technical Context

**Language/Version**: Python ≥3.11 (stdlib `argparse`, `pathlib`; `pyyaml` already a dependency).

**Primary Dependencies**: `pydantic` (the only runtime dep per the constitution) + `pyyaml` (already
added in 004). No new dependencies.

**Storage**: Filesystem only. Reads governance YAML + member sources; writes the build work dir and
the rendered site (both outside consumer repos). **Writes no manifest file by default** (derived
manifest is in-memory — clarification Q1).

**Testing**: `pytest` (`uv run pytest skill/tests -q`).

**Target Platform**: CLI / Claude Code plugin (the `speckit-atlas` skill drives the in-session agent).

**Project Type**: Single project (deterministic scripts under `skill/scripts/`, tests under
`skill/tests/`).

**Performance Goals**: Scaffold is deterministic graph/file reading over a handful of repos —
negligible (<<1s); it adds no measurable cost in front of the existing pipeline.

**Constraints**: Read-only on consumer repos; no runtime dependency on the governance extension
(contracts read as a documented format via the vendored copies + `gov_config`); ungoverned output
byte-identical to pre-feature; neutral examples only (CORE/API/WEB).

**Scale/Scope**: Workspaces of a few to a few-dozen member repos; one authority per workspace.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Note |
|---|---|---|
| I. Faithfulness is architectural | ✅ Pass | Scaffold is deterministic setup; it authors no claims and never touches `verify.py`/`verify_links.py`. The fail-closed gate runs unchanged after reasoning. |
| II. Organized by architecture | ✅ N/A | No narrative/prose change. |
| III. Current-state only | ✅ N/A | No narrative change. |
| IV. Fail-closed on gaps | ✅ Pass | "No invention" (FR-009): never derive a member/path the governance files don't declare; ungoverned → a clear message, not a fabricated manifest. |
| V. Stateless; generated, never authored | ✅ **Strengthens** | The derived manifest is generated each run, in-memory, never written/hand-edited — exactly the principle. Removes a hand-authored artifact that could rot. |
| Source-agnostic core | ✅ Pass | Reuses the existing adapters; merged ingestion composes them, no core rewrite. |
| Reasoning vs. determinism split | ✅ Pass | Scaffold is deterministic Python; the reasoning phases are untouched. |
| Toolchain `uv` / pydantic / ≥3.11 | ✅ Pass | No new deps; pydantic models for all new structures. |
| Quality gates | ✅ Pass | `verify_links.py` unchanged; `pytest` green before push; ungoverned baseline unchanged (SC-005). |

**No violations.** Complexity Tracking is empty (nothing to justify).

## Project Structure

### Documentation (this feature)

```text
specs/005-governed-autoscaffold/
├── plan.md              # This file
├── research.md          # Phase 0 — design decisions
├── data-model.md        # Phase 1 — new/changed entities
├── quickstart.md        # Phase 1 — the one-command UX
├── contracts/
│   └── scaffold-contract.md   # Phase 1 — the reader's scaffold guarantees
├── checklists/
│   └── requirements.md  # from /speckit-specify
└── tasks.md             # /speckit-tasks (next)
```

### Source Code (repository root)

```text
skill/scripts/
├── scaffold.py            # NEW — authority discovery + manifest derivation + overlay (deterministic, read-only)
├── synthesize_atlas.py    # CHANGED — optional manifest arg; --from/--authority; in-memory derived manifest;
│                          #            base/authority decoupled; merged multi-source build_member_corpus
├── schema.py              # CHANGED — IngestionSource model; WorkspaceMember.sources (optional)
├── gov_config.py          # CHANGED — RepoConfig.sources (RepoSource list) to follow source pointers
├── adapter_doc.py         # (reused as-is; already supports --adr-dir)
├── adapter_speckit.py     # (reused as-is)
└── adapter_code.py        # (reused as-is; code ingestion stays opt-in)

skill/tests/
├── test_scaffold.py             # NEW — discovery, derivation, overlay, ungoverned fallback
├── test_atlas_scaffold.py       # NEW — end-to-end no-manifest run on the governed fixture
├── test_merged_ingestion.py     # NEW — build_member_corpus merges multiple sources into one origin
├── test_gov_config.py           # CHANGED — RepoConfig.sources parsing
└── fixtures/governed/           # CHANGED — build repos carry `sources:`→source; specs_dir/adr_dir set

skills/speckit-atlas/SKILL.md    # CHANGED — document the one-command (no-manifest) governed path
README.md                        # CHANGED — governed one-command note (neutral examples)
```

**Structure Decision**: Single project, existing layout. The scaffold is a new deterministic module
composed in front of `synthesize_atlas.main`; everything else is additive edits. No package moves.

## Architecture (the decided design)

1. **Authority discovery** (`scaffold.discover_authority(start)`): if `start` holds
   `.spec-arch-domain.yml`, it is the authority. Otherwise read `start`'s `.spec-arch-governance.yml`
   and follow a `sources[].role == source` `locator` to the source repo; recurse with a **visited-set
   cycle guard** and a small hop bound. Exhausted → `None` (ungoverned). Pure, read-only.

2. **Manifest derivation** (`scaffold.derive_manifest(authority)`): read the validated domain
   manifest; for each `DomainMember` build one `WorkspaceMember` (origin=`name`; badge role mapped
   from domain role: source→`docs`, build→`spec`, standalone→`spec`; namespace from the manifest,
   declared) whose **`sources`** list is assembled from that repo's own `.spec-arch-governance.yml`:
   `specs_dir` → a `speckit` source; `adr_dir` → a `doc` source with `adr_dir` set (forces ADR
   classification); a source repo additionally gets a `doc` source for free-form docs. Build-repo code
   is **not** added by default (opt-in). Paths are expressed relative to the authority dir (the
   `base`), composing the domain `locator` with each repo's declared sub-dirs. Returns the manifest +
   a `ScaffoldReport`.

3. **Overlay** (`scaffold.overlay_manifest(derived, operator)`): operator presentation
   (title/description/theme) always wins; operator-declared members are added; an operator member
   matching a derived origin overrides it (incl. enabling code). Either side may be `None`.

4. **Merged multi-source ingestion** (`synthesize_atlas.build_member_corpus`): when `member.sources`
   is set, run each `IngestionSource`'s adapter and **merge** the fragments into one origin-stamped
   corpus; otherwise the legacy single `adapter`/`path` path (back-compat for hand-authored manifests).

5. **Decoupled base/authority** (`synthesize_atlas.main`): `manifest` becomes optional; add
   `--from <dir>` (default cwd) and `--authority <dir>`. When governed, `base = authority` and the
   domain manifest is read from the **authority** (not the manifest's parent), removing the base-dir
   constraint (FR-008). When ungoverned with a hand-authored manifest, behavior is exactly today's.
   When neither, a clear "manifest required" message (FR-003/FR-015).

The existing stages (stage-0 adapt, `resolve_topology`, namespace resolution, `discover_links`,
`verify_links`, render) are **unchanged** and run over the final manifest.

## Phase 0 — Research

See [research.md](./research.md): the four design decisions (in-memory carry; 1:1 merged ingestion;
discovery via `sources`; base/authority decoupling) with rationale and rejected alternatives.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md) — `IngestionSource`, `WorkspaceMember.sources`, `RepoConfig.sources`
  (`RepoSource`), `ScaffoldReport`, and the role mapping.
- [contracts/scaffold-contract.md](./contracts/scaffold-contract.md) — the reader's scaffold
  guarantees (discovery, derivation faithfulness, decoupling, overlay, ungoverned fallback,
  report transparency).
- [quickstart.md](./quickstart.md) — the one-command governed UX and what the operator sees.

## Complexity Tracking

No constitution violations — table intentionally empty.
