"""synthesize.py — the front door for the spec-kit-synthesis pipeline.

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
    uv run python skill/scripts/synthesize.py <specs_dir> --work .synthesis \
        --project-name "<Name>"

    # Finish — once the agent has written architecture_model.json +
    # document_model.json into the work dir, verify + render in one step:
    uv run python skill/scripts/synthesize.py <specs_dir> --work .synthesis \
        --out architecture.html [--theme theme.json]

The command auto-detects which path to take from what exists in the work dir,
so the same invocation is safe to re-run: it adapts, and if the agent's two IR
files are present it verifies and renders; otherwise it stops with the brief.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import adapter_speckit
import render as render_mod
import verify as verify_mod

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
      declarative diagram graphs, citations carried as source_refs.

 THEN re-run this same command with --out to verify (fail-closed) and render.
─────────────────────────────────────────────────────────────────────────────
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Drive the spec-kit-synthesis pipeline (deterministic stages).")
    p.add_argument("specs_dir", help="Path to the specs/ directory (NNN-* feature folders).")
    p.add_argument("--work", default=".synthesis", help="Working dir for IR artifacts (default: .synthesis).")
    p.add_argument("--project-name", default=None, help="Display name for the synthesis.")
    p.add_argument("--out", default=None, help="Render the storybook here. Requires the agent's IR files to exist.")
    p.add_argument("--theme", default=None, help="Optional theme-token JSON for the renderer.")
    args = p.parse_args(argv)

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    corpus = work / "corpus.json"
    arch = work / "architecture_model.json"
    doc = work / "document_model.json"

    # ── stage 0: adapt (always) ────────────────────────────────────────────
    rc = adapter_speckit.main([args.specs_dir, "--out", str(corpus)]
                              + (["--project-name", args.project_name] if args.project_name else []))
    if rc != 0:
        print("synthesize: adapter failed.", file=sys.stderr)
        return rc
    n = len(corpus.read_text().split('"id"')) - 1  # cheap fragment count for the brief

    ir_ready = arch.exists() and doc.exists()

    # ── scaffold path: agent hasn't produced the IR yet ────────────────────
    if not ir_ready:
        print(HAND_OFF.format(corpus=corpus, arch=arch, doc=doc, n=n))
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

    out = args.out or "architecture.html"
    render_argv = [str(doc), "--out", out] + (["--theme", args.theme] if args.theme else [])
    rrc = render_mod.main(render_argv)
    if rrc != 0:
        print("synthesize: render failed.", file=sys.stderr)
        return rrc
    print(f"synthesize: ✓ storybook written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
