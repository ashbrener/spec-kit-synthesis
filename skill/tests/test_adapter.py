"""Adapter contract tests — the spec-kit input adapter must be deterministic,
source-typed, and produce a corpus that validates against the frozen schema."""

import os
from pathlib import Path

import pytest

from adapter_speckit import build_corpus, main
from schema import FragmentCorpus, SourceType

REAL_SPECS = Path(os.path.expanduser("~/Code/AI/speckit-linear/specs"))


# ── tiny synthetic specs tree ───────────────────────────────────────────────

SPEC_MD = """# Feature Specification: Demo

**Status**: Draft

## Overview

The demo system does a thing.

## Requirements *(mandatory)*

It must do the thing well.
"""

PLAN_MD = """# Implementation Plan: Demo

## Summary

We will build it.

## Technical Context

Python, stdlib only.
"""

CONTRACT_MD = """# Push Contract

## push

Pushes stuff.
"""


@pytest.fixture()
def specs_tree(tmp_path: Path) -> Path:
    specs = tmp_path / "specs"
    feat = specs / "001-demo"
    (feat / "contracts").mkdir(parents=True)
    (feat / "spec.md").write_text(SPEC_MD, encoding="utf-8")
    (feat / "plan.md").write_text(PLAN_MD, encoding="utf-8")
    (feat / "contracts" / "push.md").write_text(CONTRACT_MD, encoding="utf-8")
    # tasks.md is a workstate artifact and must be SKIPPED (not in the kind set).
    (feat / "tasks.md").write_text("# Tasks\n\n## T1\n\nDo it.\n", encoding="utf-8")
    return specs


def test_corpus_validates(specs_tree: Path):
    corpus = build_corpus(specs_tree, project_name="Demo System")
    assert isinstance(corpus, FragmentCorpus)
    # round-trip through the frozen schema validator
    FragmentCorpus.model_validate_json(corpus.model_dump_json())
    assert corpus.project_name == "Demo System"
    assert corpus.fragments, "corpus must be non-empty"


def test_ids_stable_unique_deterministic(specs_tree: Path):
    a = build_corpus(specs_tree, project_name="Demo")
    b = build_corpus(specs_tree, project_name="Demo")
    # deterministic: identical JSON across two runs
    assert a.model_dump_json() == b.model_dump_json()
    ids = [f.id for f in a.fragments]
    assert len(ids) == len(set(ids)), "fragment ids must be unique"
    # stable scheme: folder/file#slug
    assert "001-demo/spec.md#overview" in ids
    assert "001-demo/plan.md#summary" in ids


def test_source_is_spec_typed_and_locator_equals_id(specs_tree: Path):
    corpus = build_corpus(specs_tree, project_name="Demo")
    for f in corpus.fragments:
        assert f.source.type is SourceType.SPEC, "provenance is source-typed (DESIGN §11.2 #2)"
        assert f.source.locator == f.id, "SourceRef.locator must equal the Fragment id"
        assert f.source.name.startswith("spec-001 · "), "chip label is spec-number-bearing"


def test_kinds_derived_from_filename(specs_tree: Path):
    corpus = build_corpus(specs_tree, project_name="Demo")
    kinds = {f.id: f.kind for f in corpus.fragments}
    assert all(k == "spec" for fid, k in kinds.items() if "/spec.md" in fid)
    assert all(k == "plan" for fid, k in kinds.items() if "/plan.md" in fid)
    assert all(k == "contract" for fid, k in kinds.items() if "/contracts/" in fid)
    # tasks.md is skipped entirely (workstate, not part of the spec corpus)
    assert not any("/tasks.md" in fid for fid in kinds), "tasks.md must be skipped"


def test_feature_key_is_folder(specs_tree: Path):
    corpus = build_corpus(specs_tree, project_name="Demo")
    assert {f.feature_key for f in corpus.fragments} == {"001-demo"}


def test_status_captured_as_lifecycle(specs_tree: Path):
    corpus = build_corpus(specs_tree, project_name="Demo")
    spec_frags = [f for f in corpus.fragments if f.kind == "spec"]
    assert spec_frags and all(f.lifecycle == "Draft" for f in spec_frags)
    # non-spec kinds carry no lifecycle in phase 1
    assert all(f.lifecycle is None for f in corpus.fragments if f.kind != "spec")


def test_cli_writes_out_file(specs_tree: Path, tmp_path: Path):
    out = tmp_path / "corpus.json"
    rc = main([str(specs_tree), "--project-name", "Demo", "--out", str(out)])
    assert rc == 0
    corpus = FragmentCorpus.model_validate_json(out.read_text())
    assert corpus.project_name == "Demo"
    assert corpus.fragments


def test_default_project_name_when_omitted(specs_tree: Path):
    corpus = build_corpus(specs_tree)  # parent of specs/ is the tmp dir
    assert corpus.project_name  # some non-empty sensible default


# ── real fixture (skips if absent) ──────────────────────────────────────────

@pytest.mark.skipif(not REAL_SPECS.is_dir(), reason="speckit-linear fixture not present")
def test_real_speckit_linear_corpus():
    corpus = build_corpus(REAL_SPECS)
    FragmentCorpus.model_validate_json(corpus.model_dump_json())
    assert len(corpus.fragments) > 0
    features = {f.feature_key for f in corpus.fragments}
    # subset, not equality: this reads the live external speckit-linear repo, which may
    # gain feature folders over time. The adapter must surface the original three.
    assert {
        "001-spec-kit-linear-bridge",
        "002-install-ergonomics",
        "003-drift-aware-authority",
    } <= features
    # every fragment is SPEC-typed with a self-referential locator
    for f in corpus.fragments:
        assert f.source.type is SourceType.SPEC
        assert f.source.locator == f.id
    # ids are unique
    ids = [f.id for f in corpus.fragments]
    assert len(ids) == len(set(ids))
    # all expected kinds are present
    kinds = {f.kind for f in corpus.fragments}
    assert {"spec", "plan", "data-model", "research", "quickstart", "contract"} <= kinds
