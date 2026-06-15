"""Tests for the governed-config reader (gov_config.py — spec 004, Foundational).

Neutral examples only (CORE / API / WEB) — no real consumer names.
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import gov_config as gc  # noqa: E402

GOVERNED = Path(__file__).parent / "fixtures" / "governed"


# ── per-repo config (.spec-arch-governance.yml) ──────────────────────────────

def test_reads_namespace_from_repo_config():
    cfg = gc.read_repo_config(GOVERNED / "core")
    assert cfg is not None
    assert cfg.namespace == "CORE"
    assert cfg.adr_dir == "docs/adr"
    assert cfg.specs_dir == "specs"
    assert gc.namespace_for(GOVERNED / "api") == "API"


def test_repo_config_absent_returns_none(tmp_path):
    assert gc.read_repo_config(tmp_path) is None
    assert gc.namespace_for(tmp_path) is None


# ── domain manifest (.spec-arch-domain.yml) ──────────────────────────────────

def test_loads_and_validates_domain_manifest():
    man = gc.read_domain_manifest(GOVERNED)
    assert isinstance(man, gc.DomainManifest)
    names = {m.name for m in man.members}
    namespaces = {m.namespace for m in man.members}
    roles = {m.role for m in man.members}
    assert names == {"Core", "Api", "Web"}
    assert namespaces == {"CORE", "API", "WEB"}
    assert roles == {"source", "build", "standalone"}


def test_manifest_absent_returns_none(tmp_path):
    assert gc.read_domain_manifest(tmp_path) is None


def test_rejects_malformed_manifest_bad_role(tmp_path):
    (tmp_path / gc.DOMAIN_MANIFEST_FILENAME).write_text(
        "version: v1\nmembers:\n  - name: Core\n    role: bogus\n    namespace: CORE\n    locator: ./core\n",
        encoding="utf-8",
    )
    res = gc.read_domain_manifest(tmp_path)
    assert isinstance(res, gc.ManifestError)
    assert "role" in res.message


def test_rejects_manifest_missing_required_field(tmp_path):
    (tmp_path / gc.DOMAIN_MANIFEST_FILENAME).write_text(
        "version: v1\nmembers:\n  - name: Core\n    role: source\n    namespace: CORE\n",
        encoding="utf-8",
    )
    res = gc.read_domain_manifest(tmp_path)
    assert isinstance(res, gc.ManifestError)
    assert "locator" in res.message


def test_rejects_manifest_with_extra_member_key(tmp_path):
    (tmp_path / gc.DOMAIN_MANIFEST_FILENAME).write_text(
        "version: v1\nmembers:\n  - name: Core\n    role: source\n    namespace: CORE\n    locator: ./core\n    extra: nope\n",
        encoding="utf-8",
    )
    res = gc.read_domain_manifest(tmp_path)
    assert isinstance(res, gc.ManifestError)
    assert "extra" in res.message


def test_rejects_manifest_missing_members(tmp_path):
    (tmp_path / gc.DOMAIN_MANIFEST_FILENAME).write_text("version: v1\n", encoding="utf-8")
    res = gc.read_domain_manifest(tmp_path)
    assert isinstance(res, gc.ManifestError)
    assert "members" in res.message
