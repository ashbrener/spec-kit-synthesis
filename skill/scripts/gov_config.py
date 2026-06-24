"""gov_config.py — the governed-repo config reader (spec 004, Foundational).

Atlas conforms to the architecture-governance contracts **as a documented format**: it
reads two YAML files a governed project may publish, with NO runtime/import dependency on the
governance extension (pyyaml is a generic parser).

  * `.spec-arch-governance.yml` — a per-repo config carrying that repo's `namespace`
    (the ADR prefix) plus optional `adr_dir` / `specs_dir`. Used to qualify bare `ADR-NNN`
    ids under the owning repo's namespace (spec 004 US3).

  * `.spec-arch-domain.yml` — the authority repo's domain manifest: the declared registry of
    members (name / role / namespace / locator). Validated against the vendored
    `vendor/domain.schema.json`; when valid it is the source of truth for structural topology
    (spec 004 US2). When absent or malformed the reader falls back to its own record.

Pure + deterministic: stdlib + pydantic + pyyaml; no clock/rng. Tolerant of absent files
(returns None) — an ungoverned project reads nothing here and renders unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ValidationError

# The vendored, pinned contract copies (conform-as-format; no runtime dep on the extension).
_VENDOR = Path(__file__).resolve().parent / "vendor"
_DOMAIN_SCHEMA_PATH = _VENDOR / "domain.schema.json"

GOV_CONFIG_FILENAME = ".spec-arch-governance.yml"
DOMAIN_MANIFEST_FILENAME = ".spec-arch-domain.yml"


# ───────────────────────────── read models ─────────────────────────────────

class RepoSource(BaseModel):
    """A pointer from a (build) repo to one of its sources (`.spec-arch-governance.yml` `sources[]`).

    The reader follows a `role: source` entry's `locator` to discover the authority repo that owns
    the domain manifest (spec 005)."""

    model_config = {"extra": "ignore"}

    id: Optional[str] = None
    locator: str
    role: Optional[str] = None


class RepoConfig(BaseModel):
    """A governed repo's per-repo config (`.spec-arch-governance.yml`)."""

    model_config = {"extra": "ignore"}

    namespace: Optional[str] = None
    adr_dir: Optional[str] = None
    specs_dir: Optional[str] = None
    sources: list[RepoSource] = []
    citation_keys: dict[str, str] = {}   # spec 008: override the slot key names (source_specs/adrs); absent → contract defaults


class DomainMember(BaseModel):
    """One member of a declared domain manifest. Mirrors `domain.schema.json` $defs/member."""

    model_config = {"extra": "forbid"}

    name: str
    role: str  # source | build | standalone (enum enforced against the vendored schema)
    namespace: str
    locator: str


class DomainManifest(BaseModel):
    """A validated `.spec-arch-domain.yml` — the structural-topology source of truth."""

    model_config = {"extra": "forbid"}

    version: Optional[str] = None
    members: list[DomainMember]


class ManifestError(BaseModel):
    """A structured load/validation failure: the caller falls back, never raises through."""

    model_config = {"extra": "forbid"}

    path: str
    message: str


# ───────────────────────────── vendored schema ─────────────────────────────

def _load_domain_schema() -> dict:
    return json.loads(_DOMAIN_SCHEMA_PATH.read_text(encoding="utf-8"))


def _role_enum() -> list[str]:
    """The allowed member roles, read from the vendored schema (single source of truth)."""
    schema = _load_domain_schema()
    return list(schema["$defs"]["member"]["properties"]["role"]["enum"])


# ───────────────────────────── readers ─────────────────────────────────────

def read_repo_config(repo_dir: Path | str) -> Optional[RepoConfig]:
    """Read a repo's `.spec-arch-governance.yml` → RepoConfig, or None if absent/empty.

    Tolerant: a missing file or unparseable/empty YAML returns None (the repo is read as
    ungoverned), never raises."""
    path = Path(repo_dir) / GOV_CONFIG_FILENAME
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    try:
        return RepoConfig.model_validate(data)
    except ValidationError:
        return None


def namespace_for(repo_dir: Path | str) -> Optional[str]:
    """The configured ADR namespace for a repo (or None when unconfigured/ungoverned)."""
    cfg = read_repo_config(repo_dir)
    return cfg.namespace if cfg else None


def find_repo_config(start: Path | str, ceiling: Path | str | None = None) -> Optional[RepoConfig]:
    """Walk up from a member's source path to find its `.spec-arch-governance.yml`.

    A member's source often sits below its repo root (e.g. `core/specs` under repo `core/`),
    so the config is searched from `start` upward. The walk stops at `ceiling` (inclusive) when
    given — the workspace base — so it never escapes the workspace. Returns None when no config
    is found (the member is read as ungoverned)."""
    start = Path(start).resolve()
    ceiling = Path(ceiling).resolve() if ceiling is not None else None
    cur = start
    while True:
        cfg = read_repo_config(cur)
        if cfg is not None:
            return cfg
        if ceiling is not None and cur == ceiling:
            return None
        if cur.parent == cur:  # filesystem root
            return None
        cur = cur.parent


def _validate_against_schema(data: dict) -> Optional[str]:
    """Structural validation of a domain-manifest dict against the vendored schema.

    Returns an error message string on failure, or None when valid. Deliberately a small,
    schema-driven check (required keys, no extra keys, the role enum) — enough to reject a
    malformed manifest without pulling in a jsonschema runtime dependency."""
    schema = _load_domain_schema()
    if not isinstance(data, dict):
        return "manifest is not a mapping"
    allowed_top = set(schema.get("properties", {}))
    for k in data:
        if k not in allowed_top:
            return f"unknown top-level key {k!r}"
    for req in schema.get("required", []):
        if req not in data:
            return f"missing required key {req!r}"
    members = data.get("members")
    if not isinstance(members, list):
        return "'members' must be a list"
    member_schema = schema["$defs"]["member"]
    allowed_member = set(member_schema.get("properties", {}))
    required_member = member_schema.get("required", [])
    role_enum = member_schema["properties"]["role"]["enum"]
    for i, m in enumerate(members):
        if not isinstance(m, dict):
            return f"member[{i}] is not a mapping"
        for k in m:
            if k not in allowed_member:
                return f"member[{i}] has unknown key {k!r}"
        for req in required_member:
            if req not in m:
                return f"member[{i}] missing required key {req!r}"
        if m.get("role") not in role_enum:
            return f"member[{i}] role {m.get('role')!r} not in {role_enum}"
    return None


def read_domain_manifest(authority_dir: Path | str) -> Optional[DomainManifest] | ManifestError:
    """Read + validate an authority repo's `.spec-arch-domain.yml`.

    Returns:
      * None — no manifest present (the reader falls back to its own record).
      * ManifestError — a manifest is present but malformed/invalid (caller falls back AND can
        surface the error; never raises through).
      * DomainManifest — a present, valid manifest (the structural-topology source of truth)."""
    path = Path(authority_dir) / DOMAIN_MANIFEST_FILENAME
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return ManifestError(path=str(path), message=f"YAML parse error: {exc}")
    err = _validate_against_schema(data)
    if err is not None:
        return ManifestError(path=str(path), message=err)
    try:
        return DomainManifest.model_validate(data)
    except ValidationError as exc:
        return ManifestError(path=str(path), message=f"schema validation error: {exc}")


__all__ = [
    "GOV_CONFIG_FILENAME",
    "DOMAIN_MANIFEST_FILENAME",
    "RepoConfig",
    "RepoSource",
    "DomainMember",
    "DomainManifest",
    "ManifestError",
    "read_repo_config",
    "namespace_for",
    "find_repo_config",
    "read_domain_manifest",
]
