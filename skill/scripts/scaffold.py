"""scaffold.py — derive a workspace manifest from governance contracts (spec 005).

Deterministic, read-only. Given any governed repo in a workspace, discover the authority repo that
owns `.spec-arch-domain.yml` (directly, or by following a build repo's `sources` pointer), then
derive an in-memory `WorkspaceManifest` from the declared signal — one member per declared domain
member, each with merged multi-source ingestion. No file is written; the derived manifest is carried
straight into the atlas pipeline (synthesize_atlas).

No runtime dependency on the governance extension: the contracts are read as a documented format via
`gov_config` (the per-repo `.spec-arch-governance.yml` and the validated `.spec-arch-domain.yml`).

Ingestion shape, by declared role (FR-006/FR-007):
  * source     → one `doc` pass over the repo (docs + specs-as-prose + ADRs, `adr_dir` forced) —
                 a single pass avoids double-ingesting specs as both prose and structure.
  * build      → structure-aware `speckit` over `specs_dir` + a `doc` pass over `adr_dir`.
  * standalone → same as build.
Only locations the governance config DECLARES are ingested — never an invented path (FR-009).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# scripts dir importable as module and as script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gov_config  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from schema import IngestionSource, WorkspaceManifest, WorkspaceMember  # noqa: E402

# Declared domain role → the atlas index badge role (docs|spec|code|intent).
_BADGE_ROLE = {"source": "docs", "build": "spec", "standalone": "spec"}


class ScaffoldMember(BaseModel):
    """The reviewable account of one derived member (FR-011)."""

    model_config = {"extra": "forbid"}

    origin: str
    domain_role: str
    namespace: str
    locator: str
    specs_dir: Optional[str] = None
    adr_dir: Optional[str] = None
    present: bool = True
    ingested: list[str] = []


class ScaffoldReport(BaseModel):
    """The transparent, coverage-honest summary printed before any reasoning (FR-011)."""

    model_config = {"extra": "forbid"}

    authority: str
    members: list[ScaffoldMember] = []
    skipped: list[str] = []
    governed: bool = True


def discover_authority(start, max_hops: int = 8) -> Optional[Path]:
    """From any governed repo, locate the authority dir that owns `.spec-arch-domain.yml`.

    Direct when `start` owns the domain manifest; else follow `start`'s `.spec-arch-governance.yml`
    `sources[role==source]` locator to the source repo, recursing with a visited-set cycle guard and
    a hop bound. Returns None when no authority is reachable (ungoverned). Pure, read-only."""
    visited: set[Path] = set()
    cur = Path(start).resolve()
    for _ in range(max_hops):
        if cur in visited:
            return None
        visited.add(cur)
        if (cur / gov_config.DOMAIN_MANIFEST_FILENAME).is_file():
            return cur
        cfg = gov_config.read_repo_config(cur)
        if cfg is None:
            return None
        nxt: Optional[Path] = None
        for s in cfg.sources:
            if (s.role or "").lower() == "source" and s.locator:
                nxt = (cur / s.locator).resolve()
                break
        if nxt is None:
            return None
        cur = nxt
    return None


def derive_manifest(authority, domain) -> tuple[WorkspaceManifest, ScaffoldReport]:
    """Derive an in-memory WorkspaceManifest + a ScaffoldReport from a validated domain manifest.

    One member per declared domain member; structural facts (role/namespace/locator) from the domain
    manifest; ingestion locations from each repo's own `.spec-arch-governance.yml`. Member paths are
    expressed relative to the authority dir (the build `base`), matching the domain locators verbatim.
    A declared member whose repo is absent is emitted `optional` and recorded as skipped."""
    authority = Path(authority).resolve()
    members: list[WorkspaceMember] = []
    rmembers: list[ScaffoldMember] = []
    skipped: list[str] = []

    for dm in domain.members:
        repo = (authority / dm.locator).resolve()
        present = repo.exists()
        origin = dm.name.lower()
        badge = _BADGE_ROLE.get(dm.role, "spec")
        loc = dm.locator

        def _join(sub: str) -> str:
            return sub if loc in (".", "") else f"{loc.rstrip('/')}/{sub}"

        specs_dir = adr_dir = None
        if present:
            cfg = gov_config.read_repo_config(repo)
            if cfg is not None:
                specs_dir = cfg.specs_dir
                adr_dir = cfg.adr_dir

        sources: list[IngestionSource] = []
        ingested: list[str] = []
        if dm.role == "source":
            # structure-aware (spec 007): specs read as features (speckit), ADRs as decisions (doc),
            # and the remaining narrative via doc EXCLUDING specs/adr subtrees (no double-ingest).
            if specs_dir:
                sources.append(IngestionSource(adapter="speckit", path=_join(specs_dir)))
                ingested.append(f"specs ({specs_dir}, speckit)")
            if adr_dir:
                sources.append(IngestionSource(adapter="doc", path=_join(adr_dir), adr_dir="."))
                ingested.append(f"ADRs ({adr_dir}, doc)")
            nar_exclude = [d for d in (specs_dir, adr_dir) if d]
            sources.append(IngestionSource(adapter="doc", path=loc, exclude=nar_exclude))
            ingested.append("narrative (doc, excl. specs/adr)")
        else:
            if specs_dir:
                sources.append(IngestionSource(adapter="speckit", path=_join(specs_dir)))
                ingested.append(f"specs ({specs_dir}, speckit)")
            if adr_dir:
                # the doc source targets the adr dir directly; "." marks the whole walked root as ADRs
                sources.append(IngestionSource(adapter="doc", path=_join(adr_dir), adr_dir="."))
                ingested.append(f"ADRs ({adr_dir}, doc)")

        if not present:
            skipped.append(origin)

        members.append(WorkspaceMember(
            origin=origin,
            path=loc,
            adapter="doc" if dm.role == "source" else "speckit",
            role=badge,
            title=dm.name,
            description=f"{dm.role} repo · {dm.namespace}.",
            sources=sources or None,
            optional=not present,
        ))
        rmembers.append(ScaffoldMember(
            origin=origin, domain_role=dm.role, namespace=dm.namespace, locator=dm.locator,
            specs_dir=specs_dir, adr_dir=adr_dir, present=present, ingested=ingested))

    manifest = WorkspaceManifest(
        title="Documentation Portal",
        project_name="Workspace",
        members=members,
    )
    report = ScaffoldReport(authority=str(authority), members=rmembers, skipped=skipped, governed=True)
    return manifest, report


def overlay_manifest(derived: Optional[WorkspaceManifest],
                     operator: Optional[WorkspaceManifest]) -> Optional[WorkspaceManifest]:
    """Overlay a hand-authored manifest on the derived one (FR-010).

    Operator presentation (title/description/theme) always wins; operator-only members are added; an
    operator member matching a derived origin overrides it (e.g. to enable code). Either may be None."""
    if operator is None:
        return derived
    if derived is None:
        return operator
    by_origin = {m.origin: m for m in derived.members}
    order = [m.origin for m in derived.members]
    for om in operator.members:
        if om.origin not in by_origin:
            order.append(om.origin)
        by_origin[om.origin] = om
    return WorkspaceManifest(
        title=operator.title or derived.title,
        project_name=operator.project_name or derived.project_name,
        members=[by_origin[o] for o in order],
        links=list(derived.links) + list(operator.links),
        theme={**derived.theme, **operator.theme},
    )


def format_report(report: ScaffoldReport) -> str:
    """A compact, reviewable rendering of the scaffold report (printed before reasoning)."""
    lines = [f"scaffold: authority = {report.authority} (owns {gov_config.DOMAIN_MANIFEST_FILENAME})"]
    for m in report.members:
        ing = " · ".join(m.ingested) if m.ingested else "(nothing declared to ingest)"
        flag = "" if m.present else "   [skipped — repo absent]"
        lines.append(
            f"  {m.origin:10} {m.domain_role:10} ns={(m.namespace or '-'):6} "
            f"locator={(m.locator or '-'):10} specs={m.specs_dir or '-'} adr={m.adr_dir or '-'}"
            f"  → {ing}{flag}")
    if report.skipped:
        lines.append(f"  skipped (absent repos): {', '.join(report.skipped)}")
    return "\n".join(lines)


__all__ = [
    "ScaffoldMember", "ScaffoldReport",
    "discover_authority", "derive_manifest", "overlay_manifest", "format_report",
]
