"""Contract drift guard (spec 004, FR-007 / SC-005).

Atlas conforms to the governance contracts AS A FORMAT — its enums must equal the pinned,
vendored `vocabulary.json` (@0.2.0). This test fails the build the moment the reader's relation /
role / kind / evidence set diverges from the pinned copy, so a silent mistruth can never ship.
The vendored copy is updated only by re-pinning to a newer published tag.
"""

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from schema import LinkEvidenceKind, LinkRel  # noqa: E402

VENDOR = SCRIPTS / "vendor"


def _vocabulary() -> dict:
    return json.loads((VENDOR / "vocabulary.json").read_text(encoding="utf-8"))


def _domain_schema() -> dict:
    return json.loads((VENDOR / "domain.schema.json").read_text(encoding="utf-8"))


def test_link_rel_matches_vendored_relations():
    relations = set(_vocabulary()["relations"])
    assert {r.value for r in LinkRel} == relations, (
        "LinkRel has drifted from the pinned vocabulary.json relations")


def test_evidence_kind_matches_vendored_evidence():
    evidence = set(_vocabulary()["evidence"]["values"])
    assert {e.value for e in LinkEvidenceKind} == evidence, (
        "LinkEvidenceKind has drifted from the pinned vocabulary.json evidence values")


def test_pinned_vocabulary_version_is_expected():
    # the pin is 0.3.0 (adds citation_slots); bumping the vendored copy is a deliberate act, surfaced here.
    assert _vocabulary()["version"] == "0.3.0"


def test_citation_slots_block_present_and_shaped():
    # spec 008: atlas reads the typed citation slots; pin their documented shape (ARCH-ADR-000 Amendment 2).
    cs = _vocabulary()["citation_slots"]
    assert cs["slots"]["derived_from"]["file"] == "spec.md"
    assert cs["slots"]["cites"]["file"] == "plan.md"
    assert cs["keys"]["config_field"] == "citation_keys"
    assert cs["keys"]["defaults"] == {"source_specs": "derived_from", "adrs": "cites"}
    assert ":" in cs["derived_from"]["example_cross_repo"]            # <source>:<feature>
    assert cs["cites"]["example_cross_repo"].count("-ADR-") == 1      # qualified <NS>-ADR-NNN


def test_domain_member_roles_match_vendored_schema():
    # the manifest member-role enum the reader validates against == the shared vocabulary roles
    schema_roles = set(_domain_schema()["$defs"]["member"]["properties"]["role"]["enum"])
    vocab_roles = set(_vocabulary()["roles"]["values"])
    assert schema_roles == vocab_roles, (
        "domain.schema.json member roles have drifted from vocabulary.json roles")
