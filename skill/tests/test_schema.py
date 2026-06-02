"""Schema contract tests — the faithfulness invariant must bite at the type level."""

import pytest
from pydantic import ValidationError

from schema import (
    Altitude,
    ArchitectureModel,
    Block,
    BlockType,
    CalloutKind,
    Claim,
    DiagramGraph,
    DiagramNode,
    DocumentModel,
    Fragment,
    FragmentCorpus,
    Section,
    SourceRef,
    SourceType,
)


def _ref(locator="spec-001#f1"):
    return SourceRef(type=SourceType.SPEC, name="spec-001 · spec.md", locator=locator)


def test_claim_requires_provenance():
    # DESIGN §5.1: a claim with no source_refs cannot exist.
    with pytest.raises(ValidationError):
        Claim(id="c1", text="the system does X", source_refs=[])


def test_claim_with_provenance_ok():
    c = Claim(id="c1", text="the system does X", source_refs=[_ref()], altitude=Altitude.TECHNICAL)
    assert c.source_refs[0].type is SourceType.SPEC
    assert c.altitude is Altitude.TECHNICAL


def test_block_payload_must_match_type():
    with pytest.raises(ValidationError):
        Block(type=BlockType.PROSE)  # no prose payload
    with pytest.raises(ValidationError):
        Block(type=BlockType.DIAGRAM, prose="oops")  # wrong payload for type


def test_block_payloads_ok():
    assert Block(type=BlockType.PROSE, prose="hello").prose == "hello"
    assert Block(type=BlockType.TABLE, table=[["a", "b"]]).table == [["a", "b"]]
    cal = Block(type=BlockType.CALLOUT, callout_kind=CalloutKind.UNSPECIFIED, callout_tag="Unspecified")
    assert cal.callout_kind is CalloutKind.UNSPECIFIED
    dia = Block(type=BlockType.DIAGRAM, diagram=DiagramGraph(layout="pipeline", nodes=[DiagramNode(id="n1", label="read")]))
    assert dia.diagram.nodes[0].label == "read"


def test_corpus_locators_roundtrip():
    corpus = FragmentCorpus(
        project_name="Demo",
        fragments=[Fragment(id="spec-001#f1", source=_ref(), kind="spec", text="...")],
    )
    assert corpus.locators() == {"spec-001#f1"}


def test_extra_fields_forbidden():
    # extra="forbid" — a malformed phase output is an error, not best-effort (DESIGN §6).
    with pytest.raises(ValidationError):
        ArchitectureModel(project_name="Demo", bogus_field=1)  # type: ignore[call-arg]


def test_document_model_assembles():
    doc = DocumentModel(
        title="Demo — Architecture",
        sections=[
            Section(
                id="what", number=1, title="What this system is",
                blocks=[Block(type=BlockType.PROSE, altitude=Altitude.FUNCTIONAL, prose="It does X.", claim_ids=["c1"])],
            )
        ],
    )
    assert doc.sections[0].blocks[0].altitude is Altitude.FUNCTIONAL
