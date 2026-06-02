"""Phase-D verify gate tests.

The gate's contract is its exit code, so the core tests drive the *real CLI*
via subprocess on written JSON files (clean trio -> 0; each violation -> 1;
bad input -> 2). A handful of unit tests exercise the internal `verify()`
function directly for precise check attribution.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from schema import (
    Altitude,
    ArchitectureModel,
    Block,
    BlockType,
    CalloutKind,
    Claim,
    Decision,
    DiagramGraph,
    DiagramNode,
    DocumentModel,
    Fragment,
    FragmentCorpus,
    Section,
    SourceRef,
    SourceType,
)
from verify import (
    CHECK_BLOCK_CLAIMS_EXIST,
    CHECK_BLOCK_SOURCE_REFS,
    CHECK_CALLOUT_BODY,
    CHECK_COVERAGE_NOTE,
    CHECK_NON_EMPTY_GROUNDING,
    CHECK_PROVENANCE_RESOLVES,
    EXIT_BAD_INPUT,
    EXIT_OK,
    EXIT_VIOLATIONS,
    verify,
)

VERIFY_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify.py"

GOOD_LOC = "spec-001#f1"


# ──────────────────────────── fixture builders ──────────────────────────────


def _ref(locator=GOOD_LOC):
    return SourceRef(type=SourceType.SPEC, name="spec-001 · spec.md", locator=locator)


def _corpus():
    return FragmentCorpus(
        project_name="Demo",
        fragments=[Fragment(id=GOOD_LOC, source=_ref(), kind="spec", text="raw text")],
    )


def _arch(**overrides):
    base = dict(
        project_name="Demo",
        claims=[Claim(id="c1", text="The system does X.", source_refs=[_ref()])],
        decisions=[Decision(id="d1", decision="Use X", source_refs=[_ref()])],
        open_questions=[
            Claim(id="q1", text="How does Y behave?", source_refs=[_ref()])
        ],
        coverage_note="Covers the spec-kit specs present at build time.",
    )
    base.update(overrides)
    return ArchitectureModel(**base)


def _doc(blocks=None):
    if blocks is None:
        blocks = [
            Block(
                type=BlockType.PROSE,
                altitude=Altitude.FUNCTIONAL,
                prose="It does X.",
                claim_ids=["c1"],
                source_refs=[_ref()],
            )
        ]
    return DocumentModel(
        title="Demo — Architecture",
        sections=[Section(id="what", number=1, title="What this is", blocks=blocks)],
    )


def _write_trio(tmp_path, doc, arch, corpus):
    dp = tmp_path / "document_model.json"
    ap = tmp_path / "architecture_model.json"
    cp = tmp_path / "corpus.json"
    dp.write_text(doc.model_dump_json())
    ap.write_text(arch.model_dump_json())
    cp.write_text(corpus.model_dump_json())
    return dp, ap, cp


def _run(*paths):
    return subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), *[str(p) for p in paths]],
        capture_output=True,
        text=True,
    )


# ──────────────────────────── CLI / exit-code tests ─────────────────────────


def test_clean_trio_passes(tmp_path):
    paths = _write_trio(tmp_path, _doc(), _arch(), _corpus())
    res = _run(*paths)
    assert res.returncode == EXIT_OK, res.stdout + res.stderr
    assert "PASS" in res.stdout


def test_fabricated_source_ref_fails_check_1(tmp_path):
    arch = _arch(
        claims=[Claim(id="c1", text="X", source_refs=[_ref("ghost-999#f9")])]
    )
    paths = _write_trio(tmp_path, _doc(), arch, _corpus())
    res = _run(*paths)
    assert res.returncode == EXIT_VIOLATIONS
    assert CHECK_PROVENANCE_RESOLVES in res.stdout
    assert "ghost-999#f9" in res.stdout


def test_block_claim_pointing_at_nothing_fails_check_2(tmp_path):
    block = Block(
        type=BlockType.PROSE,
        altitude=Altitude.FUNCTIONAL,
        prose="It does X.",
        claim_ids=["does-not-exist"],
    )
    paths = _write_trio(tmp_path, _doc([block]), _arch(), _corpus())
    res = _run(*paths)
    assert res.returncode == EXIT_VIOLATIONS
    assert CHECK_BLOCK_CLAIMS_EXIST in res.stdout
    assert "does-not-exist" in res.stdout


def test_functional_prose_with_empty_claims_fails_check_3(tmp_path):
    block = Block(
        type=BlockType.PROSE,
        altitude=Altitude.FUNCTIONAL,
        prose="A confident, ungrounded sentence.",
        claim_ids=[],
    )
    paths = _write_trio(tmp_path, _doc([block]), _arch(), _corpus())
    res = _run(*paths)
    assert res.returncode == EXIT_VIOLATIONS
    assert CHECK_NON_EMPTY_GROUNDING in res.stdout


def test_missing_coverage_note_fails_check_5(tmp_path):
    arch = _arch(coverage_note=None)
    paths = _write_trio(tmp_path, _doc(), arch, _corpus())
    res = _run(*paths)
    assert res.returncode == EXIT_VIOLATIONS
    assert CHECK_COVERAGE_NOTE in res.stdout


def test_missing_input_file_fails_closed(tmp_path):
    dp, ap, cp = _write_trio(tmp_path, _doc(), _arch(), _corpus())
    res = _run(dp, ap, tmp_path / "nonexistent.json")
    assert res.returncode == EXIT_BAD_INPUT


def test_invalid_json_fails_closed(tmp_path):
    dp, ap, cp = _write_trio(tmp_path, _doc(), _arch(), _corpus())
    bad = tmp_path / "bad.json"
    bad.write_text("{ this is not valid json")
    res = _run(dp, ap, bad)
    assert res.returncode == EXIT_BAD_INPUT


def test_wrong_arg_count_fails_closed(tmp_path):
    res = _run(tmp_path / "only-one.json")
    assert res.returncode == EXIT_BAD_INPUT


# ──────────────────────────── unit tests on verify() ────────────────────────


def test_verify_clean_returns_no_violations():
    assert verify(_doc(), _arch(), _corpus()) == []


def test_verify_block_source_ref_phantom_fails_check_4():
    block = Block(
        type=BlockType.PROSE,
        altitude=Altitude.FUNCTIONAL,
        prose="It does X.",
        claim_ids=["c1"],
        source_refs=[_ref("phantom-chip#z")],
    )
    vs = verify(_doc([block]), _arch(), _corpus())
    assert any(v.check == CHECK_BLOCK_SOURCE_REFS for v in vs)
    assert any(v.offender == "phantom-chip#z" for v in vs)


def test_verify_decision_and_history_provenance_checked():
    arch = _arch(
        decisions=[Decision(id="d1", decision="X", source_refs=[_ref("ghost#d")])],
    )
    vs = verify(_doc(), arch, _corpus())
    offenders = {(v.check, v.object_id, v.offender) for v in vs}
    assert (CHECK_PROVENANCE_RESOLVES, "Decision:d1", "ghost#d") in offenders


def test_verify_callout_and_diagram_exempt_from_grounding():
    # Callout (unspecified) and diagram blocks may carry zero claim_ids.
    callout = Block(
        type=BlockType.CALLOUT,
        altitude=Altitude.FUNCTIONAL,
        callout_kind=CalloutKind.UNSPECIFIED,
        callout_tag="Unspecified",
        prose="This area is left open by the specs.",
        claim_ids=[],
    )
    diagram = Block(
        type=BlockType.DIAGRAM,
        altitude=Altitude.TECHNICAL,
        diagram=DiagramGraph(nodes=[DiagramNode(id="n1", label="read")]),
        claim_ids=[],
    )
    grounded = Block(
        type=BlockType.PROSE,
        altitude=Altitude.FUNCTIONAL,
        prose="It does X.",
        claim_ids=["c1"],
    )
    vs = verify(_doc([callout, diagram, grounded]), _arch(), _corpus())
    assert not any(v.check == CHECK_NON_EMPTY_GROUNDING for v in vs)


def test_verify_empty_callout_body_fails_check_6():
    # A callout with a tag but no body renders as an empty box — must be caught.
    empty = Block(
        type=BlockType.CALLOUT,
        altitude=Altitude.FUNCTIONAL,
        callout_kind=CalloutKind.EVOLUTION,
        callout_tag="Evolution — something changed",
        claim_ids=[],
    )
    vs = verify(_doc([empty]), _arch(), _corpus())
    assert any(v.check == CHECK_CALLOUT_BODY for v in vs)
    # and a callout WITH a body does not trip it
    full = Block(
        type=BlockType.CALLOUT,
        altitude=Altitude.FUNCTIONAL,
        callout_kind=CalloutKind.EVOLUTION,
        callout_tag="Evolution — something changed",
        prose="It used to do A; now it does B.",
        claim_ids=[],
    )
    vs2 = verify(_doc([full]), _arch(), _corpus())
    assert not any(v.check == CHECK_CALLOUT_BODY for v in vs2)


def test_verify_open_question_claim_id_resolves():
    # A block may rest on an open_question Claim id, not just a current claim.
    block = Block(
        type=BlockType.PROSE,
        altitude=Altitude.FUNCTIONAL,
        prose="This area is unspecified.",
        claim_ids=["q1"],
    )
    vs = verify(_doc([block]), _arch(), _corpus())
    assert not any(v.check == CHECK_BLOCK_CLAIMS_EXIST for v in vs)


def test_verify_provenance_altitude_block_not_required_to_ground():
    # Only functional/technical prose/table blocks must be grounded.
    block = Block(
        type=BlockType.PROSE,
        altitude=Altitude.PROVENANCE,
        prose="spec-001 · spec.md",
        claim_ids=[],
    )
    vs = verify(_doc([block]), _arch(), _corpus())
    assert not any(v.check == CHECK_NON_EMPTY_GROUNDING for v in vs)
