"""Schema deltas for the melded SITE layer (spec 006, Foundational).

Neutral examples only (CORE / API / WEB).
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from schema import Block, BlockType, DiagramGraph, DiagramNode, Section  # noqa: E402


def test_block_tier_and_build_status_default_none():
    b = Block(type=BlockType.PROSE, prose="hi")
    assert b.tier is None and b.build_status is None


def test_block_accepts_tier_and_build_status():
    b = Block(type=BlockType.PROSE, prose="API detail", tier="backend", build_status="planned")
    assert b.tier == "backend" and b.build_status == "planned"
    # round-trips
    assert Block.model_validate_json(b.model_dump_json()).build_status == "planned"


def test_section_build_status_optional():
    s = Section(id="auth", number=2, title="Authentication", build_status="partial")
    assert s.build_status == "partial"
    assert Section(id="x", number=1, title="X").build_status is None


def test_diagram_layout_accepts_sequence_and_erd():
    for layout in ("sequence", "erd"):
        g = DiagramGraph(layout=layout, nodes=[DiagramNode(id="n", label="N")])
        assert g.layout == layout
    # existing layouts still valid
    assert DiagramGraph(layout="flow").layout == "flow"
    assert DiagramGraph().layout == "pipeline"
