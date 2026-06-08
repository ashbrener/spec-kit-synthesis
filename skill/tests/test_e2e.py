"""End-to-end integration test on a self-contained fixture project.

This is the only full-pipeline run that depends on NOTHING outside the repo: it
drives the real adapters, the real fail-closed verify gate, and the real
renderer over `skill/tests/fixtures/mini_project/`, removing the previous
dependency on an external sibling repo for full-pipeline coverage.

Pipeline exercised (DESIGN §11):

    fixture specs ──adapter_speckit──▶ spec FragmentCorpus
    fixture src   ──adapter_code────▶ code FragmentCorpus
    spec + code   ──merge──────────▶ one FragmentCorpus (no locator collisions)
    hand-authored ArchitectureModel + DocumentModel citing REAL locators
                  ──verify (fail-closed)──▶ [] (clean trio passes)
    DocumentModel ──render──────────▶ deterministic interactive HTML

The hand-authored IR stands in for the in-session agent's reasoning (Phases
A–C); the point of this test is the deterministic seam, not the reasoning.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from schema import (
    Altitude,
    ArchitectureModel,
    Block,
    BlockType,
    Claim,
    CoverageItem,
    CoverageStatus,
    DocumentModel,
    FragmentCorpus,
    Section,
    SourceRef,
    SourceType,
)
import adapter_code
import adapter_speckit
import render
import verify

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mini_project"
SPECS_DIR = FIXTURE / "specs"
SRC_DIR = FIXTURE / "src"

# Real locators emitted by the adapters (see the asserts in build/merge below).
SPEC_OVERVIEW = "001-widget/spec.md#overview"
SPEC_REQUIREMENTS = "001-widget/spec.md#requirements"
SPEC_POLISH_OVERVIEW = "002-polish/spec.md#overview"
CODE_CREATE = "widget.sh#widget_create"
CODE_NORMALIZE = "util.py#normalize_name"


# ───────────────────────────── adapter stages ──────────────────────────────


def _spec_corpus() -> FragmentCorpus:
    corpus = adapter_speckit.build_corpus(SPECS_DIR, project_name="Mini Project")
    assert isinstance(corpus, FragmentCorpus)
    # round-trips through the schema (validates as a FragmentCorpus)
    FragmentCorpus.model_validate_json(corpus.model_dump_json())
    return corpus


def _code_corpus() -> FragmentCorpus:
    corpus = adapter_code.build_corpus(SRC_DIR, "Mini Project", adapter_code.DEFAULT_EXTS)
    assert isinstance(corpus, FragmentCorpus)
    FragmentCorpus.model_validate_json(corpus.model_dump_json())
    return corpus


def test_spec_adapter_spans_both_feature_folders():
    corpus = _spec_corpus()
    feature_keys = {f.feature_key for f in corpus.fragments}
    assert feature_keys == {"001-widget", "002-polish"}, feature_keys
    ids = corpus.locators()
    # the prose-bearing fragments we cite downstream are present
    assert SPEC_OVERVIEW in ids
    assert SPEC_REQUIREMENTS in ids
    assert SPEC_POLISH_OVERVIEW in ids
    # every fragment is SPEC-typed and self-referential
    for f in corpus.fragments:
        assert f.source.type is SourceType.SPEC
        assert f.source.locator == f.id


def test_code_adapter_yields_file_and_symbol_fragments():
    corpus = _code_corpus()
    ids = corpus.locators()
    # file-level fragments
    assert "widget.sh" in ids and "util.py" in ids
    # symbol-level fragments (shell functions + python def/class)
    assert CODE_CREATE in ids
    assert "widget.sh#widget_lookup" in ids
    assert CODE_NORMALIZE in ids
    assert "util.py#WidgetStore" in ids
    kinds = {f.kind for f in corpus.fragments}
    assert "code" in kinds and "code-symbol" in kinds
    for f in corpus.fragments:
        assert f.source.type is SourceType.CODE
        assert f.source.locator == f.id


# ─────────────────────────────── merge stage ───────────────────────────────


def _merged_corpus() -> FragmentCorpus:
    spec = _spec_corpus()
    code = _code_corpus()
    spec_ids = spec.locators()
    code_ids = code.locators()
    # the architectural seam: spec and code locators are disjoint, so they can
    # share one corpus the source-agnostic core reasons over.
    assert spec_ids.isdisjoint(code_ids), spec_ids & code_ids
    return FragmentCorpus(
        project_name="Mini Project",
        fragments=[*spec.fragments, *code.fragments],
    )


def test_merge_has_no_locator_collisions():
    merged = _merged_corpus()
    ids = [f.id for f in merged.fragments]
    assert len(ids) == len(set(ids)), "duplicate locator in merged corpus"
    # merge preserves both source types
    types = {f.source.type for f in merged.fragments}
    assert types == {SourceType.SPEC, SourceType.CODE}


# ──────────────────────── hand-authored minimal IR ──────────────────────────


def _spec_ref(locator: str, name: str, anchor: str | None = None) -> SourceRef:
    return SourceRef(type=SourceType.SPEC, name=name, locator=locator, anchor=anchor)


def _code_ref(locator: str, name: str, anchor: str | None = None) -> SourceRef:
    return SourceRef(type=SourceType.CODE, name=name, locator=locator, anchor=anchor)


def _architecture() -> ArchitectureModel:
    """A minimal but valid model whose every ref cites a REAL merged locator."""
    overview_ref = _spec_ref(SPEC_OVERVIEW, "spec-001 · spec.md", "Overview")
    req_ref = _spec_ref(SPEC_REQUIREMENTS, "spec-001 · spec.md", "Requirements")
    create_ref = _code_ref(CODE_CREATE, "code · widget.sh · widget_create", "widget_create")
    normalize_ref = _code_ref(CODE_NORMALIZE, "code · util.py · normalize_name", "normalize_name")

    claims = [
        Claim(
            id="c-create",
            text="A user creates a widget by giving it a human-readable name.",
            altitude=Altitude.FUNCTIONAL,
            source_refs=[overview_ref, req_ref],
        ),
        Claim(
            id="c-store",
            text="Widget creation delegates to a shell entry point backed by a Python store.",
            altitude=Altitude.TECHNICAL,
            source_refs=[create_ref, normalize_ref],
        ),
    ]
    coverage = [
        CoverageItem(
            area="Widget creation",
            status=CoverageStatus.SPEC_BACKED,
            note="Specified in 001-widget and implemented in widget.sh / util.py.",
            spec_refs=[req_ref],
            code_refs=[create_ref],
        ),
    ]
    return ArchitectureModel(
        project_name="Mini Project",
        claims=claims,
        coverage_note="Covers the widget feature; polish refinements are specced but not yet traced to code.",
        coverage=coverage,
    )


def _document() -> DocumentModel:
    overview_ref = _spec_ref(SPEC_OVERVIEW, "spec-001 · spec.md", "Overview")
    req_ref = _spec_ref(SPEC_REQUIREMENTS, "spec-001 · spec.md", "Requirements")
    create_ref = _code_ref(CODE_CREATE, "code · widget.sh · widget_create", "widget_create")
    normalize_ref = _code_ref(CODE_NORMALIZE, "code · util.py · normalize_name", "normalize_name")

    return DocumentModel(
        title="Mini Project — Architecture",
        lede="A tiny widget system, synthesized from its specs and its code.",
        sections=[
            Section(
                id="what",
                number=1,
                title="What this is",
                blocks=[
                    Block(
                        type=BlockType.PROSE,
                        altitude=Altitude.FUNCTIONAL,
                        prose="A user creates a widget by giving it a human-readable name.",
                        claim_ids=["c-create"],
                        source_refs=[overview_ref, req_ref],
                    ),
                    Block(
                        type=BlockType.PROSE,
                        altitude=Altitude.TECHNICAL,
                        prose="Creation delegates to a shell entry point backed by a Python store.",
                        claim_ids=["c-store"],
                        source_refs=[create_ref, normalize_ref],
                    ),
                ],
            ),
            Section(
                id="coverage",
                number=2,
                title="Coverage",
                blocks=[
                    Block(
                        type=BlockType.COVERAGE,
                        altitude=Altitude.FUNCTIONAL,
                        coverage=[
                            CoverageItem(
                                area="Widget creation",
                                status=CoverageStatus.SPEC_BACKED,
                                note="Specified and implemented.",
                                spec_refs=[req_ref],
                                code_refs=[create_ref],
                            ),
                        ],
                        source_refs=[req_ref, create_ref],
                    ),
                ],
            ),
        ],
    )


# ─────────────────────────── the clean-trio gate ────────────────────────────


def test_verify_passes_on_clean_trio():
    merged = _merged_corpus()
    arch = _architecture()
    doc = _document()
    violations = verify.verify(doc, arch, merged)
    assert violations == [], verify.render_report(violations)


# ──────────────────────────── negative assertion ────────────────────────────


def test_verify_fails_on_fabricated_locator():
    """Mutating one source_ref locator to a fake value must trip the gate."""
    merged = _merged_corpus()
    doc = _document()
    arch = _architecture()
    # fabricate a citation on a current claim
    arch.claims[0].source_refs[0] = _spec_ref(
        "001-widget/spec.md#does-not-exist", "spec-001 · phantom"
    )
    violations = verify.verify(doc, arch, merged)
    assert violations, "fail-closed gate must reject a fabricated locator"
    assert any(v.check == verify.CHECK_PROVENANCE_RESOLVES for v in violations), violations
    assert any(v.offender == "001-widget/spec.md#does-not-exist" for v in violations)


# ──────────────────────────────── render stage ──────────────────────────────


class _Parses(HTMLParser):
    """A no-op parser: success is simply 'feed() did not raise'."""


def test_render_produces_deterministic_parseable_html():
    doc = _document()
    html_out = render.render(doc, render.DEFAULT_THEME)

    # parses as HTML
    _Parses().feed(html_out)
    # is a full document in the editorial design system (renderer v2)
    assert html_out.startswith("<!DOCTYPE html>")
    assert 'header class="mast"' in html_out
    # light-only: no global depth toggle / dark-mode machinery
    assert "data-depth" not in html_out and "seg depth" not in html_out
    # at least one source-typed citation chip rendered from a real source_ref
    assert 'class="srcline"' in html_out
    assert 'class="cite-t spec"' in html_out
    assert "spec-001 · spec.md" in html_out
    # deterministic: rendering twice is byte-identical
    again = render.render(doc, render.DEFAULT_THEME)
    assert html_out == again
