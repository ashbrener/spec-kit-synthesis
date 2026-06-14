# Feature Specification: Source views (drill-to-source)

**Feature Branch**: `003-source-views`
**Created**: 2026-06-14
**Status**: Draft
**Input**: "The specs and ADRs are not accessible in the docs, in HTML beautified format." A
citation chip names its source but a reader cannot open and read that source. Close the gap so
every claim's source is genuinely one click away — rendered, not just named.

## Overview

The storybook asserts claims and cites their sources as Layer-2 chips. Today a chip links to a
text entry in the References appendix; the **actual source document is nowhere in the output.**
This feature renders each cited source document as a beautified, in-design-system HTML page and
wires the chips to open it at the exact cited section. It is a pure *read* surface over the
corpus the run already reasoned over — it changes nothing about extraction, reconciliation, or
the fail-closed verify gate.

## User scenarios

- **An evaluator** reading the storybook clicks a citation chip and lands on the cited spec
  section, rendered legibly (headings, tables, code, Mermaid) — without leaving the portal or
  opening a raw `.md` file.
- **An engineer** in a multi-repo portal opens the `docs` page, clicks a chip on an architecture
  claim, and reads the underlying ADR/spec section that backs it.

## Functional requirements

- **FR-001**: For every source file referenced by the document model's citations, the build
  MUST emit a self-contained source-view HTML page reconstructed from that file's corpus
  fragments (in source order).
- **FR-002**: Each source-view page MUST render the source markdown beautifully — headings,
  lists, tables, code blocks, and **Mermaid diagrams** — in the editorial design system
  (same palette/fonts as the storybook).
- **FR-003**: Each source section MUST carry an HTML anchor matching its fragment locator's
  section part, so a `file#section` citation deep-links to the exact section.
- **FR-004**: Citation chips (and the References appendix entries) MUST link to the rendered
  source-view section (`sources/<file>.html#<section>`) instead of a dead in-page label.
- **FR-005**: A citation MUST drill to the **actual source content of its owning repo**, across
  the whole workspace. In the multi-repo portal a **global** source resolver maps every
  citation (same-repo or cross-repo) to that repo's bundled source view
  (`sources/<origin>/<file>.html#<section>`) — so from any page you can read the real spec/ADR
  of *any* related repo. (The atlas map remains for repo-to-repo navigation.)
- **FR-006**: The cited spec/ADR **content MUST be copied INTO the HTML** (embedded per page), so
  a reader needs no access to the original repos or files — the site is self-contained. Only the
  CDN renderer (markdown-it + Mermaid) that prettifies the embedded content is external, with a
  readable raw-text fallback when offline. Output MUST stay deterministic (byte-identical for
  identical inputs).
- **FR-007**: The source-view layer MUST be additive — when disabled or unsupported, the
  storybook renders exactly as before (chips fall back to the References appendix).
- **FR-008**: **ADRs are first-class.** The build MUST ingest ADR documents (a repo's `adr_dir` /
  governed `<NS>-ADR-NNN` records) into the corpus and render them as source views exactly like
  specs, so claims and cross-repo references can drill into actual ADR content — not just specs.

## Success criteria

- **SC-001**: From a generated storybook, clicking a citation chip opens the cited source
  section rendered as HTML — verified on a real docs portal (its ADRs + specs reachable).
- **SC-002**: No source content is lost: every fragment's text appears on its file's page.
- **SC-003**: `verify.py` behaviour is unchanged (0/0 on a faithful model); the engine and IR
  contracts are untouched.
- **SC-004**: Re-rendering twice yields byte-identical output.

## Out of scope

- Editing or round-tripping source docs (read-only, generated-never-authored — invariant V).
- Rendering sources NOT present in the corpus (only what was reasoned over is shown).
- Any change to extraction / reconciliation / compose / the verify gate.
- Governance/`ARCH-ADR-000` conformance (a separate, parked effort).
