"""Render test for the Phase-2 COVERAGE block (intent-vs-reality matrix)."""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from schema import (Altitude, Block, BlockType, CoverageItem, CoverageStatus,  # noqa: E402
                    DocumentModel, Section, SourceRef, SourceType)
import render as render_mod  # noqa: E402


def _spec(loc, name): return SourceRef(type=SourceType.SPEC, name=name, locator=loc)
def _code(loc, name): return SourceRef(type=SourceType.CODE, name=name, locator=loc)


def test_coverage_block_renders_pills_and_typed_chips():
    rows = [
        CoverageItem(area="Reconcile engine", status=CoverageStatus.SPEC_BACKED,
                     spec_refs=[_spec("001/spec.md#overview", "spec-001 · spec.md")],
                     code_refs=[_code("reconcile.sh#reconcile::run", "code · reconcile.sh")]),
        CoverageItem(area="Webhook layer", status=CoverageStatus.SPECCED_ONLY,
                     spec_refs=[_spec("001/plan.md#summary", "spec-001 · plan.md")]),
        CoverageItem(area="status.sh helper", status=CoverageStatus.IMPLEMENTED_ONLY,
                     code_refs=[_code("status.sh#status::main", "code · status.sh")],
                     note="present in code; no spec fragment describes it"),
    ]
    block = Block(type=BlockType.COVERAGE, altitude=Altitude.FUNCTIONAL, coverage=rows)
    doc = DocumentModel(title="Demo — Architecture", sections=[
        Section(id="coverage", number=1, title="Coverage", blocks=[block])])
    html = render_mod.render(doc, render_mod.DEFAULT_THEME)

    # one pill per status, with status-specific classes
    assert "cov-spec_backed" in html
    assert "cov-specced_only" in html
    assert "cov-implemented_only" in html
    # typed citation chips inside the matrix
    assert 'data-t="spec"' in html and 'data-t="code"' in html
    # the implemented-only note surfaces
    assert "no spec fragment describes it" in html
    # area names present
    assert "Reconcile engine" in html and "Webhook layer" in html


def test_coverage_block_requires_rows():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Block(type=BlockType.COVERAGE)  # no coverage payload
