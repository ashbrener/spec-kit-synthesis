"""verify_links.py — the fail-closed gate for the cross-repo LinkGraph (spec 002, Phase E).

The cross-repo analogue of verify.py's "a claim with no source cannot exist": a cross-repo
edge ships only if it is grounded. It copies verify.py's discipline verbatim — same Violation
dataclass + report, exit code IS the contract — so a fabricated traceability link can no more
ship than a fabricated citation.

Checks (each failing edge is a violation that fails the gate):

  1. ENDPOINTS_RESOLVE   both endpoints' locators must exist in the workspace locator union
                         (the union of every member corpus). A dangling endpoint is a broken link.
  2. EVIDENCE_PRESENT    every edge must carry non-empty evidence.
  3. EVIDENCE_GROUNDED   the evidence must actually hold:
                           - identifier: the token appears in BOTH endpoints' source text,
                           - prose:      the quote appears literally in the SRC source text,
                           - declared:   trusted (operator-asserted) — endpoints must resolve.

CLI (exit code is the contract):

    uv run python skill/scripts/verify_links.py <link_graph.json> <corpus1.json> [<corpus2.json> ...]

  exits 0 iff zero violations; 1 if any; 2 on missing/invalid input (fail-closed).
"""

from __future__ import annotations

import re
import sys

from schema import FragmentCorpus, LinkEvidenceKind, LinkGraph
from verify import EXIT_BAD_INPUT, EXIT_OK, EXIT_VIOLATIONS, Violation, render_report

CHECK_ENDPOINTS_RESOLVE = "ENDPOINTS_RESOLVE"
CHECK_EVIDENCE_PRESENT = "EVIDENCE_PRESENT"
CHECK_EVIDENCE_GROUNDED = "EVIDENCE_GROUNDED"

_ADR_TOKEN = re.compile(r"ADR-\d{3,}")


def _identifier_present(token: str, text: str) -> bool:
    """The shared identifier grounds an endpoint if it appears literally — or, for a qualified ADR
    id (`<NS>-ADR-NNN`), if its bare `ADR-NNN` form does. Discovery qualifies bare ids per-namespace,
    so the stored evidence is the qualified id while the source text often holds only the bare form;
    the two denote the same decision (B1). Non-ADR identifiers (FR-/slug) stay strict."""
    if token in text:
        return True
    m = _ADR_TOKEN.search(token)
    return bool(m and m.group(0) in text)


def verify_links(graph: LinkGraph, frag_text: dict[str, str]) -> list[Violation]:
    """Run every cross-repo edge check. `frag_text` maps every workspace locator → its source
    text (built from the member corpora). Returns all violations (empty == pass)."""
    locators = set(frag_text)
    violations: list[Violation] = []

    for i, e in enumerate(graph.edges):
        eid = f"edge[{i}] {e.src.origin}:{e.src.locator} -{e.rel.value}-> {e.dst.origin}:{e.dst.locator}"

        # ── Check 1: both endpoints resolve in the workspace ────────────────
        resolved = True
        for end in (e.src, e.dst):
            if end.locator not in locators:
                resolved = False
                violations.append(Violation(
                    check=CHECK_ENDPOINTS_RESOLVE, object_id=eid,
                    detail="edge endpoint locator does not resolve in any workspace member (broken link).",
                    offender=end.locator,
                ))

        # ── Check 2: evidence present ───────────────────────────────────────
        if not (e.evidence and e.evidence.strip()):
            violations.append(Violation(
                check=CHECK_EVIDENCE_PRESENT, object_id=eid,
                detail="edge carries no evidence; a link must say why it exists (DESIGN §5.4).",
            ))
            continue  # nothing to ground

        # ── Check 3: evidence grounded (only if endpoints resolve) ──────────
        if not resolved:
            continue
        st = frag_text.get(e.src.locator, "")
        dt = frag_text.get(e.dst.locator, "")
        if e.evidence_kind is LinkEvidenceKind.IDENTIFIER:
            if not (_identifier_present(e.evidence, st) and _identifier_present(e.evidence, dt)):
                violations.append(Violation(
                    check=CHECK_EVIDENCE_GROUNDED, object_id=eid,
                    detail="shared-identifier edge: the identifier is not present in BOTH endpoints' source.",
                    offender=e.evidence,
                ))
        elif e.evidence_kind is LinkEvidenceKind.PROSE:
            if e.evidence not in st:
                violations.append(Violation(
                    check=CHECK_EVIDENCE_GROUNDED, object_id=eid,
                    detail="prose edge: the quoted evidence is not found literally in the src source (no inference).",
                    offender=e.evidence[:60],
                ))
        # DECLARED: trusted (operator-asserted); endpoint resolution above is enough.

    return violations


# ──────────────────────────────── CLI ──────────────────────────────────────


def _load(path: str, model, label: str):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        raise SystemExit(f"verify_links: cannot read {label} ({path!r}): {exc}") from exc
    try:
        return model.model_validate_json(raw)
    except Exception as exc:
        raise SystemExit(f"verify_links: {label} ({path!r}) failed schema validation:\n{exc}") from exc


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: verify_links.py <link_graph.json> <corpus1.json> [<corpus2.json> ...]", file=sys.stderr)
        return EXIT_BAD_INPUT
    graph_path, *corpus_paths = argv
    try:
        graph = _load(graph_path, LinkGraph, "link_graph")
        frag_text: dict[str, str] = {}
        for cp in corpus_paths:
            corpus = _load(cp, FragmentCorpus, "corpus")
            for f in corpus.fragments:
                frag_text[f.id] = f.text or ""
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_BAD_INPUT

    violations = verify_links(graph, frag_text)
    print(render_report(violations))
    return EXIT_OK if not violations else EXIT_VIOLATIONS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
