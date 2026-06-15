"""Topology precedence (spec 004 US2): declared manifest = structural source of truth;
workspace record = presentation overlay always + topology fallback when no manifest.

Neutral examples only (CORE / API / WEB).
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import gov_config as gc  # noqa: E402
import synthesize_atlas as atlas  # noqa: E402
from schema import WorkspaceManifest, WorkspaceMember  # noqa: E402

GOVERNED = Path(__file__).parent / "fixtures" / "governed"


def _workspace():
    return WorkspaceManifest(title="Governed Portal", project_name="governed", members=[
        WorkspaceMember(origin="core", path="core/specs", adapter="speckit", role="spec",
                        title="Core", description="The authoritative core specs."),
        WorkspaceMember(origin="api", path="api/specs", adapter="speckit", role="spec",
                        title="Api", description="The API build-specs."),
        WorkspaceMember(origin="web", path="web/src", adapter="code", role="code",
                        title="Web", description="The standalone web service."),
    ])


def test_manifest_present_topology_from_manifest_presentation_from_workspace():
    domain = gc.read_domain_manifest(GOVERNED)
    assert isinstance(domain, gc.DomainManifest)
    topo = atlas.resolve_topology(_workspace(), domain)
    assert topo.declared is True
    by = {rm.origin: rm for rm in topo.members}
    # structural fields come from the manifest, graded `declared`
    assert by["core"].domain_role == "source" and by["core"].namespace == "CORE"
    assert by["api"].domain_role == "build" and by["api"].namespace == "API"
    assert by["web"].domain_role == "standalone" and by["web"].namespace == "WEB"
    assert all(rm.structure_evidence == "declared" for rm in topo.members)
    # presentation comes from the workspace record
    assert by["core"].title == "Core" and by["core"].description == "The authoritative core specs."
    assert by["core"].role == "spec" and by["web"].role == "code"


def test_manifest_absent_falls_back_to_workspace_record():
    topo = atlas.resolve_topology(_workspace(), None)
    assert topo.declared is False
    by = {rm.origin: rm for rm in topo.members}
    # no structural declaration → record fallback, no namespace/role from a manifest
    assert all(rm.structure_evidence == "record" for rm in topo.members)
    assert by["core"].namespace is None and by["core"].domain_role is None
    # presentation still present + a complete topology (every member resolved)
    assert {rm.origin for rm in topo.members} == {"core", "api", "web"}
    assert by["web"].title == "Web"


def test_manifest_wins_on_overlapping_structural_field():
    # workspace order is preserved (presentation owns ordering); manifest supplies the structure
    domain = gc.read_domain_manifest(GOVERNED)
    topo = atlas.resolve_topology(_workspace(), domain)
    assert [rm.origin for rm in topo.members] == ["core", "api", "web"]  # workspace order kept
    # the manifest's structural namespace is authoritative (no workspace structural field overrides it)
    assert next(rm for rm in topo.members if rm.origin == "api").namespace == "API"
