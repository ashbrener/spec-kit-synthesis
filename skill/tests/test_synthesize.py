"""Orchestrator smoke tests — both pipeline paths, on a tiny synthetic specs tree."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _tiny_specs(root: Path) -> Path:
    d = root / "specs" / "001-demo"
    d.mkdir(parents=True)
    (d / "spec.md").write_text("# Feature: Demo\n\n## Overview\n\nThe demo does a thing.\n")
    (d / "plan.md").write_text("# Plan\n\n## Summary\n\nBuilt in Python.\n")
    return root / "specs"


def _run(args):
    return subprocess.run([sys.executable, str(SCRIPTS / "synthesize.py"), *args],
                          capture_output=True, text=True)


def test_scaffold_path_adapts_and_briefs(tmp_path):
    specs = _tiny_specs(tmp_path)
    work = tmp_path / "work"
    r = _run([str(specs), "--work", str(work), "--project-name", "Demo"])
    assert r.returncode == 0, r.stderr
    assert (work / "corpus.json").exists()
    assert "STAGE 0 COMPLETE" in r.stdout
    assert "the in-session agent reasons" in r.stdout
    # corpus validates against the schema
    sys.path.insert(0, str(SCRIPTS))
    from schema import FragmentCorpus
    FragmentCorpus.model_validate_json((work / "corpus.json").read_text())


def test_out_without_ir_stops_with_message(tmp_path):
    specs = _tiny_specs(tmp_path)
    work = tmp_path / "work"
    r = _run([str(specs), "--work", str(work), "--out", str(tmp_path / "out.html")])
    assert r.returncode == 0
    assert not (tmp_path / "out.html").exists()  # did not render without IR
    assert "not present yet" in r.stderr


def test_finish_path_verifies_and_renders(tmp_path):
    """With a hand-authored minimal valid IR present, the finish path renders."""
    sys.path.insert(0, str(SCRIPTS))
    from schema import (ArchitectureModel, Block, BlockType, Claim, DocumentModel,
                        Section, SourceRef, SourceType, Altitude)
    specs = _tiny_specs(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    # adapt first to get a real corpus + a real locator
    _run([str(specs), "--work", str(work)])
    corpus = json.loads((work / "corpus.json").read_text())
    loc = corpus["fragments"][0]["id"]
    ref = SourceRef(type=SourceType.SPEC, name="spec-001 · spec.md", locator=loc)
    arch = ArchitectureModel(project_name="Demo",
                             claims=[Claim(id="c1", text="It does a thing.", source_refs=[ref])],
                             coverage_note="Covers the specified portion only.")
    doc = DocumentModel(title="Demo — Architecture",
                        sections=[Section(id="what", number=1, title="What this is",
                                          blocks=[Block(type=BlockType.PROSE, altitude=Altitude.FUNCTIONAL,
                                                        prose="It does a thing.", claim_ids=["c1"],
                                                        source_refs=[ref])])])
    (work / "architecture_model.json").write_text(arch.model_dump_json())
    (work / "document_model.json").write_text(doc.model_dump_json())
    out = tmp_path / "out.html"
    r = _run([str(specs), "--work", str(work), "--out", str(out)])
    assert r.returncode == 0, r.stderr
    assert "verify: PASS" in r.stdout
    assert out.exists() and out.read_text().startswith("<!DOCTYPE html>")


def _tiny_src(root: Path) -> Path:
    s = root / "src"
    s.mkdir(parents=True)
    (s / "engine.sh").write_text("#!/usr/bin/env bash\nrun() {\n  echo go\n}\n")
    return s


def test_code_flag_merges_corpus_and_briefs_coverage(tmp_path):
    specs = _tiny_specs(tmp_path)
    src = _tiny_src(tmp_path)
    work = tmp_path / "work"
    r = _run([str(specs), "--code", str(src), "--work", str(work), "--project-name", "Demo"])
    assert r.returncode == 0, r.stderr
    # merged corpus carries BOTH spec and code fragments
    corpus = json.loads((work / "corpus.json").read_text())
    types = {f["source"]["type"] for f in corpus["fragments"]}
    assert types == {"spec", "code"}, types
    # the brief tells the agent to produce the coverage view
    assert "coverage[]" in r.stdout
    # the grounded locator list is written
    assert (work / "locators.txt").exists()
    locs = (work / "locators.txt").read_text()
    assert "engine.sh" in locs and "001-demo" in locs


def _tiny_docs(root: Path) -> Path:
    d = root / "docs"
    d.mkdir(parents=True)
    (d / "architecture.md").write_text("# Architecture\n\n## Why bash\n\nZero runtime.\n")
    return d


def test_docs_flag_merges_design_doc_source(tmp_path):
    specs = _tiny_specs(tmp_path)
    docs = _tiny_docs(tmp_path)
    work = tmp_path / "work"
    r = _run([str(specs), "--docs", str(docs), "--work", str(work), "--project-name", "Demo"])
    assert r.returncode == 0, r.stderr
    corpus = json.loads((work / "corpus.json").read_text())
    types = {f["source"]["type"] for f in corpus["fragments"]}
    assert types == {"spec", "design_doc"}, types
    locs = (work / "locators.txt").read_text()
    assert "architecture.md" in locs
