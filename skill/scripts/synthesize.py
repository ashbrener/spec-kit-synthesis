"""synthesize.py — the front door for the spec-kit-atlas pipeline.

One command that drives the DETERMINISTIC stages and makes the in-session
reasoning boundary explicit. This is not a button that hides an LLM — by design
(DESIGN §6, SKILL.md) the reasoning phases (extract → reconcile → compose) are
the in-session agent's work. This orchestrator runs the code stages around them:

    stage 0  adapt    specs/ → corpus.json                      [code, here]
    ----- agent reasons: corpus → architecture_model + document_model -----
    stage D  verify   fail-closed gate over the agent's output  [code, here]
    render            document_model → architecture.html        [code, here]

Usage:
    # Stage 0 only — produce the corpus and print the agent's hand-off brief:
    uv run python skill/scripts/synthesize.py <specs_dir> --work .atlas \
        --project-name "<Name>"

    # Finish — once the agent has written architecture_model.json +
    # document_model.json into the work dir, verify + render in one step:
    uv run python skill/scripts/synthesize.py <specs_dir> --work .atlas \
        --out architecture.html [--theme theme.json]

The command auto-detects which path to take from what exists in the work dir,
so the same invocation is safe to re-run: it adapts, and if the agent's two IR
files are present it verifies and renders; otherwise it stops with the brief.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import adapter_code
import adapter_doc
import adapter_speckit
import render as render_mod
import render_sources
import verify as verify_mod
from schema import DocumentModel, FragmentCorpus

HAND_OFF = """\
─────────────────────────────────────────────────────────────────────────────
 STAGE 0 COMPLETE — corpus written to {corpus}
 ({n} fragments across the project's specs)

 NEXT: the in-session agent reasons the three phases (SKILL.md), writing two
 files into the work dir — using ONLY locators that exist in the corpus:

   1. {arch}
      reconcile the corpus into ONE current-state ArchitectureModel:
      merge overlaps · demote supersessions to history[] · collect
      open_questions · plan the section spine · write coverage_note.

   2. {doc}
      compose the ArchitectureModel into a DocumentModel: altitude-tagged
      blocks (functional Layer 0 / technical Layer 1), callouts with bodies,
      declarative diagram graphs, citations carried as source_refs.{coverage_hint}

 A flat list of every valid locator (the ONLY ids you may cite) is written to:
   {locators}

 THEN re-run this same command with --out to verify (fail-closed) and render.
─────────────────────────────────────────────────────────────────────────────
"""

_COVERAGE_HINT = """

   Because a code source was merged in, ALSO add a coverage[] to the
   ArchitectureModel and a COVERAGE block: classify each area spec_backed /
   specced_only / implemented_only, citing real spec AND code locators. Do not
   omit a built area (every scanned code file should be represented)."""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Drive the spec-kit-atlas pipeline (deterministic stages).")
    p.add_argument("specs_dir", help="Path to the specs/ directory (NNN-* feature folders).")
    p.add_argument("--code", default=None, help="Optional source tree to merge as a CODE source (enables the coverage view).")
    p.add_argument("--docs", default=None, help="Optional free-form design-doc / ADR tree to merge as a DESIGN_DOC source.")
    p.add_argument("--adr-dir", default=None, help="A repo's ADR directory (e.g. docs/adr); its docs are ingested as kind='adr' (FR-008). Implies a DESIGN_DOC merge even without --docs.")
    p.add_argument("--work", default=".atlas", help="Working dir for IR artifacts (default: .atlas).")
    p.add_argument("--project-name", default=None, help="Display name for the atlas.")
    p.add_argument("--out", default=None, help="Render the storybook here. Requires the agent's IR files to exist.")
    p.add_argument("--theme", default=None, help="Optional theme-token JSON for the renderer.")
    args = p.parse_args(argv)

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    corpus = work / "corpus.json"
    arch = work / "architecture_model.json"
    doc = work / "document_model.json"
    locators_file = work / "locators.txt"

    # ── stage 0: adapt specs (always), optionally merge a code source ──────
    spec_corpus = work / "corpus-specs.json"
    rc = adapter_speckit.main([args.specs_dir, "--out", str(spec_corpus)]
                              + (["--project-name", args.project_name] if args.project_name else []))
    if rc != 0:
        print("synthesize: spec adapter failed.", file=sys.stderr)
        return rc
    merged = FragmentCorpus.model_validate_json(spec_corpus.read_text())

    def _merge_source(adapter, src_dir: str, label: str, out_name: str,
                      extra_args: list[str] | None = None) -> int:
        """Adapt an extra source and merge it into `merged`, collision-checked."""
        nonlocal merged
        out = work / out_name
        rc = adapter.main([src_dir, "--out", str(out)]
                          + (["--project-name", args.project_name] if args.project_name else [])
                          + (extra_args or []))
        if rc != 0:
            print(f"synthesize: {label} adapter failed.", file=sys.stderr)
            return rc
        extra = FragmentCorpus.model_validate_json(out.read_text())
        clash = merged.locators() & extra.locators()
        if clash:
            print(f"synthesize: locator collision merging {label} corpus: {sorted(clash)[:3]}",
                  file=sys.stderr)
            return 1
        merged = FragmentCorpus(project_name=merged.project_name,
                                fragments=[*merged.fragments, *extra.fragments])
        return 0

    if args.code:
        rc = _merge_source(adapter_code, args.code, "code", "corpus-code.json")
        if rc != 0:
            return rc
    # A DESIGN_DOC merge runs when --docs and/or --adr-dir is given. With only
    # --adr-dir, the ADR directory is itself the docs tree (its ADRs are still
    # ingested as kind='adr' — FR-008).
    if args.docs or args.adr_dir:
        docs_dir = args.docs or args.adr_dir
        extra = ["--adr-dir", args.adr_dir] if args.adr_dir else None
        rc = _merge_source(adapter_doc, docs_dir, "design-doc", "corpus-docs.json", extra)
        if rc != 0:
            return rc

    # the single corpus the agent reasons over + the gate checks against
    corpus.write_text(merged.model_dump_json(indent=2))
    # the precise, grounded input for reasoning: every citable locator, one per line
    locators_file.write_text("\n".join(f"{f.kind:12} {f.id}" for f in merged.fragments) + "\n")
    n = len(merged.fragments)

    ir_ready = arch.exists() and doc.exists()

    # ── scaffold path: agent hasn't produced the IR yet ────────────────────
    if not ir_ready:
        print(HAND_OFF.format(corpus=corpus, arch=arch, doc=doc, n=n, locators=locators_file,
                              coverage_hint=_COVERAGE_HINT if args.code else ""))
        if args.out:
            print("synthesize: --out given but the agent's IR files are not present yet; "
                  "produce them (see brief above), then re-run.", file=sys.stderr)
        return 0

    # ── finish path: verify (fail-closed) then render ──────────────────────
    print(f"synthesize: IR present — verifying {doc.name} + {arch.name} against {corpus.name} …")
    vrc = verify_mod.main([str(doc), str(arch), str(corpus)])
    if vrc != 0:
        print("synthesize: VERIFY FAILED (fail-closed) — fix the flagged claims/blocks, do not bypass.",
              file=sys.stderr)
        return vrc

    out_path = Path(args.out or "architecture.html")
    theme_dict = json.loads(Path(args.theme).read_text(encoding="utf-8")) if args.theme else {}
    doc_model = DocumentModel.model_validate_json(doc.read_text(encoding="utf-8"))
    corpus_model = FragmentCorpus.model_validate_json(corpus.read_text(encoding="utf-8"))

    # drill-to-source (spec 003): render each cited source file as a bundled, beautified page
    # under sources/, and wire the storybook's citation chips to open it at the cited section.
    n_src = render_sources.write_source_views(
        corpus_model, out_path.parent, theme_dict,
        back_href="../" + out_path.name,
        project=doc_model.title or corpus_model.project_name,
    )
    resolver = render_sources.build_source_resolver(corpus_model, base="sources/")
    out_path.write_text(render_mod.render(doc_model, theme_dict, resolve=resolver), encoding="utf-8")
    print(f"synthesize: ✓ storybook + {n_src} source page(s) written to {out_path} "
          f"(every citation drills into sources/)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
