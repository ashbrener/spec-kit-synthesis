"""Phase-D verify gate — the deterministic, fail-closed faithfulness check.

DESIGN §6: "the Phase-D verify gate is a script that fails closed — it rejects
any composed block whose claims lack a resolvable source_ref, regardless of what
the model produced. Faithfulness is code-enforced, not model-promised."

This module is pure Python (stdlib + schema.py). It contains NO LLM call. It is
the deterministic half of the integrity bar (DESIGN §5, §11.2 #1): the in-session
agent reasons; this gate mechanically refuses to let an ungrounded sentence ship.

CLI contract (exit code IS the contract — this is a gate):

    uv run python skill/scripts/verify.py <document_model.json> \\
        <architecture_model.json> <corpus.json>

  - loads & validates all three via schema.py `model_validate_json`,
  - runs the checks below,
  - prints a structured human-readable report of every violation,
  - exits 0 iff zero violations; non-zero (1) if any violation.

Fail-closed: a missing or invalid input file is itself a non-zero exit (2) — the
gate never passes by default, only on a clean, fully-validated trio.

Checks (each failing instance is a violation that fails the gate):

  1. PROVENANCE RESOLVES   every source_ref.locator on every Claim in the
                           ArchitectureModel (claims, open_questions, and the
                           source_refs of decisions and history) must exist in
                           corpus.locators(). A claim citing a non-existent
                           source is a fabricated citation.
  2. BLOCK CLAIMS EXIST    every id in block.claim_ids must name a real Claim id
                           in the ArchitectureModel (claims + open_questions).
  3. NON-EMPTY GROUNDING   every PROSE/TABLE block at functional or technical
                           altitude must carry >=1 claim_id. Callout/diagram
                           blocks are exempt (an `unspecified` callout asserts a
                           gap without a positive claim).
  4. BLOCK SOURCE_REFS     every source_ref.locator that appears on any Block
                           must also resolve into the corpus.
  5. COVERAGE NOTE PRESENT the ArchitectureModel must carry a non-empty
                           coverage_note (DESIGN §5.8 — the doc frames its scope).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from schema import ArchitectureModel, BlockType, CalloutKind, DocumentModel, FragmentCorpus

# ──────────────────────────── violation model ──────────────────────────────

# Stable check identifiers, used in the report and assertable by tests.
CHECK_PROVENANCE_RESOLVES = "PROVENANCE_RESOLVES"
CHECK_BLOCK_CLAIMS_EXIST = "BLOCK_CLAIMS_EXIST"
CHECK_NON_EMPTY_GROUNDING = "NON_EMPTY_GROUNDING"
CHECK_BLOCK_SOURCE_REFS = "BLOCK_SOURCE_REFS_CONSISTENT"
CHECK_COVERAGE_NOTE = "COVERAGE_NOTE_PRESENT"
CHECK_CALLOUT_BODY = "CALLOUT_BODY_PRESENT"


@dataclass(frozen=True)
class Violation:
    """One failed assertion. `object_id` and `offender` localise the breach."""

    check: str
    object_id: str          # which object (claim id, block locator, model name)
    detail: str             # human-readable explanation
    offender: str = ""      # the offending locator / claim_id, if any

    def render(self) -> str:
        loc = f"  offender: {self.offender}\n" if self.offender else ""
        return (
            f"[{self.check}] object: {self.object_id}\n"
            f"  {self.detail}\n"
            f"{loc}"
        )


# ──────────────────────────── the checks ───────────────────────────────────


def verify(
    doc: DocumentModel,
    arch: ArchitectureModel,
    corpus: FragmentCorpus,
) -> list[Violation]:
    """Run every faithfulness check. Returns all violations (empty == pass)."""

    violations: list[Violation] = []
    locators = corpus.locators()

    # Claim ids the document may rest on: current claims + open_questions.
    # (decisions/history carry source_refs but are not block.claim_id targets.)
    claim_ids = {c.id for c in arch.claims} | {q.id for q in arch.open_questions}

    # ── Check 5: coverage note present ──────────────────────────────────────
    # Checked first so a scope-less model is always flagged even if otherwise clean.
    if not arch.coverage_note or not arch.coverage_note.strip():
        violations.append(
            Violation(
                check=CHECK_COVERAGE_NOTE,
                object_id=f"ArchitectureModel:{arch.project_name}",
                detail="coverage_note is missing or empty; the document must frame its own scope (DESIGN §5.8).",
            )
        )

    # ── Check 1: every claim's provenance resolves into the corpus ──────────
    # claims + open_questions ARE Claims; decisions + history carry source_refs.
    def _check_refs(owner_kind: str, owner_id: str, source_refs) -> None:
        for ref in source_refs:
            if ref.locator not in locators:
                violations.append(
                    Violation(
                        check=CHECK_PROVENANCE_RESOLVES,
                        object_id=f"{owner_kind}:{owner_id}",
                        detail=(
                            f"source_ref locator does not resolve into the corpus "
                            f"(fabricated citation, DESIGN §5.1)."
                        ),
                        offender=ref.locator,
                    )
                )

    for c in arch.claims:
        _check_refs("Claim", c.id, c.source_refs)
    for q in arch.open_questions:
        _check_refs("OpenQuestion", q.id, q.source_refs)
    for d in arch.decisions:
        _check_refs("Decision", d.id, d.source_refs)
    for h in arch.history:
        _check_refs("EvolutionNote", h.id, h.source_refs)
    for ci in arch.coverage:
        # A coverage row's spec_refs and code_refs must resolve like any other
        # provenance — a coverage claim is as grounded as any claim (DESIGN §5.8).
        _check_refs("Coverage", ci.area, list(ci.spec_refs) + list(ci.code_refs))

    # ── Walk the document blocks for checks 2, 3, 4 ─────────────────────────
    for section in doc.sections:
        for index, block in enumerate(section.blocks):
            block_id = f"{section.id}#block[{index}]({block.type.value})"

            # Check 2: every claim_id names a real claim.
            for cid in block.claim_ids:
                if cid not in claim_ids:
                    violations.append(
                        Violation(
                            check=CHECK_BLOCK_CLAIMS_EXIST,
                            object_id=block_id,
                            detail="block rests on a claim_id with no matching Claim in the ArchitectureModel.",
                            offender=cid,
                        )
                    )

            # Check 3: substantive prose/table blocks must be grounded.
            substantive = block.type in (BlockType.PROSE, BlockType.TABLE)
            grounded_altitude = block.altitude.value in ("functional", "technical")
            if substantive and grounded_altitude and not block.claim_ids:
                violations.append(
                    Violation(
                        check=CHECK_NON_EMPTY_GROUNDING,
                        object_id=block_id,
                        detail=(
                            f"{block.type.value} block at altitude '{block.altitude.value}' "
                            f"has zero claim_ids; a substantive sentence cannot rest on no claim "
                            f"(DESIGN §5.1, block granularity)."
                        ),
                    )
                )

            # Check 6: a callout must carry a non-empty body — a tag alone is an
            # empty box (Codex full-run finding: evolution/unspecified callouts
            # rendered as labels with no content). Code-enforced so it can't recur.
            if block.type is BlockType.CALLOUT:
                if not (block.prose and block.prose.strip()):
                    violations.append(
                        Violation(
                            check=CHECK_CALLOUT_BODY,
                            object_id=block_id,
                            detail=(
                                f"callout '{block.callout_tag or block.callout_kind}' has no body "
                                f"prose; a tag alone renders as an empty box."
                            ),
                        )
                    )

            # Check 4: any source_ref on the block must resolve into the corpus —
            # including the refs carried inside a coverage block's rows.
            block_refs = list(block.source_refs)
            if block.coverage:
                for ci in block.coverage:
                    block_refs += list(ci.spec_refs) + list(ci.code_refs)
            for ref in block_refs:
                if ref.locator not in locators:
                    violations.append(
                        Violation(
                            check=CHECK_BLOCK_SOURCE_REFS,
                            object_id=block_id,
                            detail="block source_ref locator does not resolve into the corpus (Layer-2 phantom citation).",
                            offender=ref.locator,
                        )
                    )

    return violations


# ──────────────────────────── reporting ────────────────────────────────────


def render_report(violations: list[Violation]) -> str:
    if not violations:
        return "verify: PASS — 0 violations. All claims resolve; every block is grounded."

    by_check: dict[str, list[Violation]] = {}
    for v in violations:
        by_check.setdefault(v.check, []).append(v)

    lines = [f"verify: FAIL — {len(violations)} violation(s) across {len(by_check)} check(s).", ""]
    for check in sorted(by_check):
        group = by_check[check]
        lines.append(f"=== {check} ({len(group)}) ===")
        for v in group:
            lines.append(v.render().rstrip())
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ──────────────────────────── CLI ──────────────────────────────────────────

EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_BAD_INPUT = 2  # missing/invalid file — fail-closed, never a silent pass.

_USAGE = (
    "usage: verify.py <document_model.json> <architecture_model.json> <corpus.json>"
)


def _load(path: str, model, label: str):
    """Load + validate one artifact. Raises on any failure (fail-closed)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        raise SystemExit(f"verify: cannot read {label} ({path!r}): {exc}") from exc
    try:
        return model.model_validate_json(raw)
    except Exception as exc:  # pydantic ValidationError or malformed JSON
        raise SystemExit(f"verify: {label} ({path!r}) failed schema validation:\n{exc}") from exc


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(_USAGE, file=sys.stderr)
        return EXIT_BAD_INPUT

    doc_path, arch_path, corpus_path = argv

    try:
        doc = _load(doc_path, DocumentModel, "document_model")
        arch = _load(arch_path, ArchitectureModel, "architecture_model")
        corpus = _load(corpus_path, FragmentCorpus, "corpus")
    except SystemExit as exc:
        # Fail-closed: any load/validation failure is a non-zero exit.
        print(str(exc.code), file=sys.stderr)
        return EXIT_BAD_INPUT

    violations = verify(doc, arch, corpus)
    print(render_report(violations))
    return EXIT_OK if not violations else EXIT_VIOLATIONS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
