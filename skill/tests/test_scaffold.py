"""Tests for the governed auto-scaffold (scaffold.py — spec 005).

Neutral examples only (CORE / API / WEB) — no real consumer names.
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import gov_config as gc  # noqa: E402
import scaffold  # noqa: E402

WS = Path(__file__).parent / "fixtures" / "governed_ws"


# ── authority discovery (T008 / FR-001/002/003) ──────────────────────────────

def test_discovers_authority_directly_from_source_repo():
    auth = scaffold.discover_authority(WS / "core")
    assert auth == (WS / "core").resolve()


def test_discovers_authority_from_build_repo_via_sources():
    # api/.spec-arch-governance.yml points sources → ../core (the authority)
    auth = scaffold.discover_authority(WS / "api")
    assert auth == (WS / "core").resolve()


def test_discovers_same_authority_from_any_member():
    assert scaffold.discover_authority(WS / "api") == scaffold.discover_authority(WS / "web")
    assert scaffold.discover_authority(WS / "core") == scaffold.discover_authority(WS / "web")


def test_ungoverned_start_returns_none(tmp_path):
    assert scaffold.discover_authority(tmp_path) is None


def test_discovery_cycle_guard_terminates(tmp_path):
    # two repos pointing at each other as "source", neither owning a domain manifest
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    (a / gc.GOV_CONFIG_FILENAME).write_text(
        "namespace: A\nsources:\n  - locator: ../b\n    role: source\n", encoding="utf-8")
    (b / gc.GOV_CONFIG_FILENAME).write_text(
        "namespace: B\nsources:\n  - locator: ../a\n    role: source\n", encoding="utf-8")
    assert scaffold.discover_authority(a) is None  # terminates, no infinite loop


# ── manifest derivation (T010 / FR-004/005/006/007) ──────────────────────────

def _derive():
    auth = scaffold.discover_authority(WS / "core")
    domain = gc.read_domain_manifest(auth)
    assert not isinstance(domain, gc.ManifestError) and domain is not None
    return scaffold.derive_manifest(auth, domain)


def test_derived_member_set_equals_domain_members():
    manifest, report = _derive()
    origins = [m.origin for m in manifest.members]
    assert origins == ["core", "api", "web"]  # exactly the declared members, no more/fewer
    assert report.governed is True


def test_derived_members_carry_declared_namespace_and_locator():
    _, report = _derive()
    by = {m.origin: m for m in report.members}
    assert by["core"].namespace == "CORE" and by["core"].domain_role == "source"
    assert by["api"].namespace == "API" and by["api"].locator == "../api"
    assert by["web"].namespace == "WEB" and by["web"].domain_role == "standalone"


def test_source_member_structure_aware_ingestion():
    # spec 007: a source repo is read structure-aware — speckit(specs) + doc(adr) + doc(narrative,
    # excluding the specs/adr subtrees) — not one doc-lumped pass.
    manifest, _ = _derive()
    by = {m.origin: m for m in manifest.members}
    core = by["core"].sources
    assert [s.adapter for s in core] == ["speckit", "doc", "doc"]
    # the narrative (final) doc pass excludes the specs + adr subtrees → no double-ingest
    narrative = core[-1]
    assert narrative.adapter == "doc" and set(narrative.exclude) == {"specs", "docs/adr"}
    # build (api) → structure-aware specs + an ADR doc pass (unchanged)
    assert [s.adapter for s in by["api"].sources] == ["speckit", "doc"]
    # standalone (web) → specs only (no adr_dir declared)
    assert [s.adapter for s in by["web"].sources] == ["speckit"]


def test_build_repo_code_is_not_ingested_by_default():
    manifest, _ = _derive()
    by = {m.origin: m for m in manifest.members}
    for origin in ("api", "web"):
        assert all(s.adapter != "code" for s in by[origin].sources)


# ── faithfulness / report (T016 / FR-009/011, edge cases) ────────────────────

def test_report_lists_per_repo_locations_read():
    _, report = _derive()
    by = {m.origin: m for m in report.members}
    assert by["core"].specs_dir == "specs" and by["core"].adr_dir == "docs/adr"
    assert by["web"].adr_dir is None  # web declares no adr_dir → derive only what's declared
    text = scaffold.format_report(report)
    assert "authority" in text and "CORE" in text and "API" in text


def test_missing_member_repo_is_skipped_not_invented(tmp_path):
    # an authority whose domain manifest names a member whose repo is absent on disk
    auth = tmp_path / "src"
    auth.mkdir()
    (auth / gc.GOV_CONFIG_FILENAME).write_text("namespace: CORE\nspecs_dir: specs\n", encoding="utf-8")
    (auth / gc.DOMAIN_MANIFEST_FILENAME).write_text(
        "version: v1\nmembers:\n"
        "  - name: Core\n    role: source\n    namespace: CORE\n    locator: .\n"
        "  - name: Gone\n    role: build\n    namespace: GONE\n    locator: ../gone\n",
        encoding="utf-8")
    domain = gc.read_domain_manifest(auth)
    manifest, report = scaffold.derive_manifest(auth, domain)
    assert "gone" in report.skipped
    gone = next(m for m in manifest.members if m.origin == "gone")
    assert gone.optional is True  # absent repo → optional, build skips it (no invention)


# ── overlay (T019 / FR-010) ──────────────────────────────────────────────────

def test_overlay_operator_presentation_wins_and_adds_members():
    derived, _ = _derive()
    from schema import WorkspaceManifest, WorkspaceMember
    operator = WorkspaceManifest(
        title="My Portal", project_name="Acme",
        members=[WorkspaceMember(origin="core", path="core", title="Renamed Core"),
                 WorkspaceMember(origin="extra", path="extra", adapter="code", role="code")],
        theme={"ink": "#111"})
    merged = scaffold.overlay_manifest(derived, operator)
    assert merged.title == "My Portal" and merged.project_name == "Acme"
    by = {m.origin: m for m in merged.members}
    assert by["core"].title == "Renamed Core"      # operator overrides the derived member
    assert "extra" in by                           # operator-only member added
    assert merged.theme.get("ink") == "#111"


def test_overlay_none_sides():
    derived, _ = _derive()
    assert scaffold.overlay_manifest(derived, None) is derived
    assert scaffold.overlay_manifest(None, None) is None
