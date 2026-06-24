"""Contract tests for the SpecKit extension manifest (extension.yml).

`extension.yml` is the installation contract `specify extension add` reads. These tests dogfood it
against the published protocol (spec-kit `extensions/EXTENSION-PUBLISHING-GUIDE.md`): identity and
command-name patterns, semantic version, referenced files exist, and the required root files are
present. Atlas is an INVOKED (not hook-driven) extension, so it declares no lifecycle hooks.
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]   # repo root (skill/tests → repo)
MANIFEST = ROOT / "extension.yml"

ID_RE = re.compile(r"^[a-z0-9-]+$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _manifest():
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_exists_and_schema_version():
    assert MANIFEST.is_file(), "extension.yml must exist at the repo root"
    assert _manifest()["schema_version"] == "1.0"


def test_extension_identity_is_contract_valid():
    ext = _manifest()["extension"]
    assert ID_RE.match(ext["id"]), f"id {ext['id']!r} must match ^[a-z0-9-]+$"
    assert VERSION_RE.match(ext["version"]), "version must be plain X.Y.Z"
    assert ext["license"] == "MIT"
    assert 0 < len(ext["description"]) < 100, "description must be under 100 chars (guide checklist)"


def test_command_names_and_files_resolve():
    m = _manifest()
    ext_id = m["extension"]["id"]
    name_re = re.compile(rf"^speckit\.{re.escape(ext_id)}\.[a-z0-9-]+$")
    cmds = m["provides"]["commands"]
    assert cmds, "must declare at least one command"
    for c in cmds:
        assert name_re.match(c["name"]), f"command {c['name']!r} must be speckit.{ext_id}.<sub>"
        assert (ROOT / c["file"]).is_file(), f"command file missing: {c['file']}"


def test_no_lifecycle_hooks_declared():
    # atlas is invoked, not hook-driven (unlike arch-governance) — it must register no hooks.
    assert "hooks" not in _manifest(), "atlas declares no lifecycle hooks"


def test_required_root_files_present():
    for fname in ("extension.yml", "README.md", "LICENSE", "CHANGELOG.md", ".gitignore"):
        assert (ROOT / fname).exists(), f"required root file missing: {fname}"


def test_tags_are_lowercase_and_sized():
    tags = _manifest().get("tags", [])
    assert 2 <= len(tags) <= 5, "guide: 2–5 tags"
    assert all(t == t.lower() for t in tags), "tags must be lowercase"
