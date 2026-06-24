"""End-to-end tests for the one-command governed scaffold path (spec 005, US1 + US3).

Drives synthesize_atlas.main with NO manifest on the governed_ws fixture and asserts the derived,
declared-topology build; plus the operator-overlay and ungoverned-fallback behaviors.

Neutral examples only (CORE / API / WEB).
"""

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import synthesize_atlas as sa  # noqa: E402

WS = Path(__file__).parent / "fixtures" / "governed_ws"


def _topology(work: Path) -> dict:
    return json.loads((work / "topology.json").read_text(encoding="utf-8"))


def _link_graph(work: Path) -> dict:
    return json.loads((work / "link_graph.json").read_text(encoding="utf-8"))


# ── US1: one command, no manifest, declared topology (SC-001/002/003) ─────────

def test_no_manifest_build_derives_declared_topology(tmp_path):
    work = tmp_path / "work"
    rc = sa.main(["--from", str(WS / "api"), "--work", str(work)])
    assert rc == 0
    topo = _topology(work)
    declared = [m for m in topo["members"] if m["structure_evidence"] == "declared"]
    assert len(declared) == 3
    assert {m["origin"] for m in topo["members"]} == {"core", "api", "web"}


def test_no_manifest_build_produces_cross_repo_cites(tmp_path):
    work = tmp_path / "work"
    assert sa.main(["--from", str(WS / "core"), "--work", str(work)]) == 0
    edges = _link_graph(work)["edges"]
    cites = [(e["src"]["origin"], e["dst"]["origin"], e["evidence"]) for e in edges if e["rel"] == "cites"]
    # the build repo's plan cites CORE-ADR-001; core's bare ADR-001 qualifies to CORE-ADR-001
    assert ("api", "core", "CORE-ADR-001") in cites


def test_same_member_set_from_any_launch_dir(tmp_path):
    from_api = tmp_path / "a"
    from_web = tmp_path / "b"
    assert sa.main(["--from", str(WS / "api"), "--work", str(from_api)]) == 0
    assert sa.main(["--from", str(WS / "web"), "--work", str(from_web)]) == 0
    a = {m["origin"] for m in _topology(from_api)["members"]}
    b = {m["origin"] for m in _topology(from_web)["members"]}
    assert a == b == {"core", "api", "web"}


def test_bare_adr_stays_repo_local(tmp_path):
    # api's own bare ADR-001 (→ API-ADR-001) must NOT cross-match core's ADR-001 (→ CORE-ADR-001)
    work = tmp_path / "work"
    assert sa.main(["--from", str(WS / "core"), "--work", str(work)]) == 0
    edges = _link_graph(work)["edges"]
    # no api→core (or core→api) edge minted from a bare, unqualified shared "ADR-001"
    spurious = [e for e in edges
                if e["rel"] == "cites" and e["evidence"] == "API-ADR-001"
                and {e["src"]["origin"], e["dst"]["origin"]} == {"api", "core"}]
    assert spurious == []


# ── US3: ungoverned fallback (FR-003/015, SC-005) ────────────────────────────

def test_ungoverned_no_manifest_errors_clearly(tmp_path):
    # an ungoverned workspace (no domain manifest reachable) and no manifest → clear non-zero exit
    (tmp_path / "src").mkdir()
    rc = sa.main(["--from", str(tmp_path / "src"), "--work", str(tmp_path / "work")])
    assert rc == 2


def test_ungoverned_with_manifest_builds_without_declared_topology(tmp_path):
    # a hand-authored manifest on an ungoverned workspace behaves as before (no derivation)
    ws = tmp_path / "ws"
    (ws / "specs" / "001-x").mkdir(parents=True)
    (ws / "specs" / "001-x" / "spec.md").write_text("# X\n- **FR-001**: do a thing.\n", encoding="utf-8")
    manifest = ws / "atlas.workspace.json"
    manifest.write_text(json.dumps({
        "title": "Plain", "members": [
            {"origin": "x", "path": "specs", "adapter": "speckit", "role": "spec", "title": "X"}]}),
        encoding="utf-8")
    work = tmp_path / "work"
    rc = sa.main([str(manifest), "--from", str(ws), "--work", str(work)])
    assert rc == 0
    topo = _topology(work)
    assert topo["declared"] is False
    assert all(m["structure_evidence"] == "record" for m in topo["members"])
