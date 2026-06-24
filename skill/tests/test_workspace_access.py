"""Tests for optional multi-repo access in the portal workspace (spec 002)."""

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import pytest  # noqa: E402

import synthesize_atlas as atlas  # noqa: E402
from schema import WorkspaceMember  # noqa: E402

FIXWS = Path(__file__).parent / "fixtures" / "workspace"


def _manifest(tmp, members):
    p = tmp / "atlas.workspace.json"
    p.write_text(json.dumps({"title": "T", "project_name": "t", "members": members}), encoding="utf-8")
    return p


def test_member_accepts_url_and_optional_fields():
    m = WorkspaceMember(origin="be", path="../be", adapter="code", role="code",
                        url="https://example.com/be.git", pin="abc123", optional=True)
    assert m.url == "https://example.com/be.git" and m.optional is True and m.pin == "abc123"


def test_optional_missing_member_is_skipped(tmp_path):
    man = _manifest(tmp_path, [
        {"origin": "guide", "path": str(FIXWS / "guide"), "adapter": "doc", "role": "docs"},
        {"origin": "ghost", "path": "does/not/exist", "adapter": "code", "role": "code", "optional": True},
    ])
    rc = atlas.main([str(man), "--work", str(tmp_path / "work")])
    assert rc == 0                                              # build doesn't fail
    assert (tmp_path / "work" / "guide" / "corpus.json").exists()   # present member adapted
    assert not (tmp_path / "work" / "ghost").exists()          # missing optional member skipped


def test_non_optional_missing_member_fails(tmp_path):
    man = _manifest(tmp_path, [{"origin": "ghost", "path": "nope", "adapter": "code", "role": "code"}])
    with pytest.raises(SystemExit):                            # a required missing repo is fail-closed
        atlas.main([str(man), "--work", str(tmp_path / "work")])
