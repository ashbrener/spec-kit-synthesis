"""Human-readable source titles + hierarchical index (source_index.py — spec 006, US1/US3).

Neutral examples only (CORE / API / WEB).
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import source_index as si  # noqa: E402
from schema import Fragment, FragmentCorpus, SourceRef, SourceType


def _frag(origin, locator, feature, kind, text):
    fid = f"{origin}::{locator}"
    return Fragment(id=fid, kind=kind, feature_key=feature, text=text,
                    source=SourceRef(type=SourceType.SPEC, origin=origin, name=locator, locator=fid))


def test_title_extracted_from_heading_and_applied_to_feature():
    corpora = {"api": FragmentCorpus(project_name="api", fragments=[
        _frag("api", "007-auth/spec.md", "007-auth", "spec", "# Authentication System\n\nbody"),
        _frag("api", "007-auth/plan.md", "007-auth", "plan", "no heading here, just prose"),
    ])}
    tm = si.build_title_map(corpora)
    spec = tm["api::007-auth/spec.md"]
    plan = tm["api::007-auth/plan.md"]
    assert spec.title == "Authentication System" and spec.artifact_kind == "spec" and spec.repo == "api"
    # the feature title carries to its other artifacts; kind reflects each artifact
    assert plan.title == "Authentication System" and plan.artifact_kind == "plan"
    assert not spec.is_fallback


def test_humanized_fallback_when_no_heading():
    corpora = {"web": FragmentCorpus(project_name="web", fragments=[
        _frag("web", "003-back-office/spec.md", "003-back-office", "spec", "prose, no markdown heading"),
    ])}
    tm = si.build_title_map(corpora)
    t = tm["web::003-back-office/spec.md"]
    assert t.title == "Back Office" and t.is_fallback is True


# ── hierarchical index tree (US3) ────────────────────────────────────────────

def test_build_tree_repo_feature_artifact_with_titles_and_links():
    corpora = {"backend": FragmentCorpus(project_name="backend", fragments=[
        _frag("backend", "007-auth/spec.md", "007-auth", "spec", "# Authentication System\n"),
        _frag("backend", "007-auth/plan.md", "007-auth", "plan", "plan"),
    ])}
    tree = si.build_tree(corpora)
    repo = tree.children[0]
    assert repo.kind == "repo" and repo.label == "backend"
    feat = repo.children[0]
    assert feat.kind == "feature" and feat.label == "Authentication System"
    kinds = {a.label for a in feat.children}
    assert {"spec", "plan"} <= kinds
    assert all(a.href and a.href.startswith("sources/backend/") for a in feat.children)


def test_render_index_tree_is_a_tree_not_a_graph():
    corpora = {"backend": FragmentCorpus(project_name="backend", fragments=[
        _frag("backend", "007-auth/spec.md", "007-auth", "spec", "# Authentication System\n")])}
    html = si.render_index_tree(si.build_tree(corpora))
    assert 'class="ixtree"' in html and "Authentication System" in html
    assert "back to the story" in html
