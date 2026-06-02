"""Code adapter tests — the Phase-2 second source, and the seam proof.

The central architectural bet (DESIGN §11.1): code is a new ADAPTER, not a
rewrite. The source-agnostic core (verify gate) must handle a merged spec+code
corpus with zero changes.
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from schema import FragmentCorpus, SourceType  # noqa: E402
import adapter_code  # noqa: E402


def _tiny_src(root: Path) -> Path:
    s = root / "src"
    s.mkdir(parents=True)
    (s / "config.sh").write_text(
        "#!/usr/bin/env bash\n"
        "config::load() {\n  echo load\n}\n\n"
        "config::validate() {\n  echo validate\n}\n"
    )
    (s / "util.py").write_text(
        "def parse(x):\n    return x\n\n"
        "class Engine:\n    pass\n"
    )
    (s / "README.notcode").write_text("ignored")
    return s


def test_code_adapter_emits_file_and_symbol_fragments(tmp_path):
    src = _tiny_src(tmp_path)
    corpus = adapter_code.build_corpus(src, "Demo", adapter_code.DEFAULT_EXTS)
    assert isinstance(corpus, FragmentCorpus)
    ids = {f.id for f in corpus.fragments}
    # file-level fragments
    assert "config.sh" in ids and "util.py" in ids
    # symbol-level fragments
    assert "config.sh#config::load" in ids
    assert "config.sh#config::validate" in ids
    assert "util.py#parse" in ids
    assert "util.py#Engine" in ids
    # non-code file ignored
    assert not any("README" in i for i in ids)
    # every fragment is CODE-typed and self-referential
    for f in corpus.fragments:
        assert f.source.type is SourceType.CODE
        assert f.source.locator == f.id


def test_code_adapter_deterministic(tmp_path):
    src = _tiny_src(tmp_path)
    a = adapter_code.build_corpus(src, "Demo", adapter_code.DEFAULT_EXTS).model_dump_json()
    b = adapter_code.build_corpus(src, "Demo", adapter_code.DEFAULT_EXTS).model_dump_json()
    assert a == b


def test_unknown_language_degrades_to_file_level(tmp_path):
    s = tmp_path / "src"
    s.mkdir()
    (s / "main.go").write_text("package main\nfunc main() {}\n")
    corpus = adapter_code.build_corpus(s, "Demo", {".go"})
    ids = {f.id for f in corpus.fragments}
    assert "main.go" in ids  # file-level always present
    # no Go def-pattern configured → file-level only, no crash
    assert all(f.kind == "code" for f in corpus.fragments)


def test_seam_merged_corpus_resolves_with_unchanged_gate(tmp_path):
    """The bet: a spec+code merged corpus passes the existing verify gate."""
    from schema import (ArchitectureModel, Block, BlockType, Claim, DocumentModel,
                        Section, SourceRef, Altitude)
    import verify

    src = _tiny_src(tmp_path)
    code = adapter_code.build_corpus(src, "Demo", adapter_code.DEFAULT_EXTS)
    # a tiny spec-typed fragment to merge alongside
    spec_ref = SourceRef(type=SourceType.SPEC, name="spec-001 · spec.md", locator="001-demo/spec.md#overview")
    from schema import Fragment
    spec_frag = Fragment(id="001-demo/spec.md#overview", source=spec_ref, kind="spec", text="It loads config.")
    merged = FragmentCorpus(project_name="Demo", fragments=[spec_frag, *code.fragments])

    # a claim citing BOTH a spec source and a code source
    code_ref = SourceRef(type=SourceType.CODE, name="code · config.sh · config::load",
                         locator="config.sh#config::load")
    claim = Claim(id="c1", text="Configuration is loaded at startup.",
                  source_refs=[spec_ref, code_ref], altitude=Altitude.TECHNICAL)
    arch = ArchitectureModel(project_name="Demo", claims=[claim],
                             coverage_note="Covers the specified portion.")
    doc = DocumentModel(title="Demo", sections=[
        Section(id="dm", number=1, title="Data model", blocks=[
            Block(type=BlockType.PROSE, altitude=Altitude.TECHNICAL,
                  prose="Configuration is loaded at startup.", claim_ids=["c1"],
                  source_refs=[spec_ref, code_ref])])])
    violations = verify.verify(doc, arch, merged)
    assert violations == [], f"merged-corpus gate should pass unchanged, got: {violations}"
