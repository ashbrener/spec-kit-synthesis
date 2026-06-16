"""End-to-end signal on a docs-authority workspace (spec 007, US1/US2).

The dogfood-#2 fix: a source repo (docs repository with specs_dir + adr_dir + narrative) is ingested
structure-aware, so build specs and the source specs they derive from MELD into shared capabilities;
cited ADRs ride inside them; uncited ADRs are decisions; narrative is background. Neutral names only.
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import cluster as cl  # noqa: E402
import discover_links  # noqa: E402
import gov_config  # noqa: E402
import scaffold  # noqa: E402
import synthesize_atlas as sa  # noqa: E402

WS = Path(__file__).parent / "fixtures" / "docs_authority"
CORE = WS / "core"


def _build(tmp_path):
    auth = scaffold.discover_authority(CORE)
    assert auth == CORE.resolve()
    domain = gov_config.read_domain_manifest(auth)
    manifest, _report = scaffold.derive_manifest(auth, domain)
    base = auth
    corpora = {}
    for m in manifest.members:
        mw = tmp_path / m.origin
        mw.mkdir(parents=True, exist_ok=True)
        corpora[m.origin] = sa.build_member_corpus(m, base, mw)
    ns = {"core": "CORE", "api": "API", "web": "WEB"}
    lg = discover_links.build_link_graph(manifest, corpora, namespaces=ns)
    cs = cl.build_clusters(corpora, lg, source_origins={"core"})
    return corpora, lg, cs


def _members_str(c):
    return " ".join(f for fs in c.members.values() for f in fs)


def test_source_specs_are_distinct_features_not_one_bucket(tmp_path):
    corpora, _, _ = _build(tmp_path)
    core = corpora["core"]
    feats = {f.feature_key for f in core.fragments if f.kind in ("spec", "plan", "tasks")}
    # both source features are present and distinct (not collapsed to one "specs" bucket)
    assert "001-auth" in feats and "002-reporting" in feats


def test_no_double_ingest_specs_not_also_narrative(tmp_path):
    corpora, _, _ = _build(tmp_path)
    core = corpora["core"]
    # a spec fragment is never ALSO ingested as a design-doc (the narrative pass excludes specs/adr)
    spec_files = {f.id.split("#")[0] for f in core.fragments if f.kind in ("spec", "plan", "tasks")}
    doc_files = {f.id.split("#")[0] for f in core.fragments if f.kind == "design-doc"}
    assert spec_files.isdisjoint(doc_files)
    # narrative WAS ingested (background present), ADRs are adr-typed
    assert any("01_overview" in f.id or "05_research" in f.id for f in core.fragments)
    assert any(f.kind == "adr" for f in core.fragments)


def test_cross_tier_meld_build_spec_with_source_spec(tmp_path):
    _, _, cs = _build(tmp_path)
    # the auth capability contains BOTH the source spec (001-auth) and the build spec (007-auth)
    auth = [c for c in cs.clusters if c.kind == "capability"
            and "001-auth" in _members_str(c) and "007-auth" in _members_str(c)]
    assert auth, "build auth spec must meld with the source auth spec into one capability"
    assert {"core", "api"} <= set(auth[0].members)


def test_cited_adr_rides_in_capability_uncited_is_decision_narrative_is_background(tmp_path):
    _, _, cs = _build(tmp_path)
    cap_text = " ".join(_members_str(c) for c in cs.clusters if c.kind == "capability")
    dec_text = " ".join(_members_str(c) for c in cs.clusters if c.kind == "decision")
    bg_text = " ".join(_members_str(c) for c in cs.clusters if c.kind == "background")
    assert "ADR-001-auth" in cap_text          # cited ADR rides inside the auth capability
    assert "ADR-001-auth" not in dec_text
    assert "ADR-050-legacy" in dec_text         # uncited ADR → decision
    assert "01_overview" in bg_text or "05_research" in bg_text  # narrative → background


def test_clustering_reproducible(tmp_path):
    _, _, a = _build(tmp_path)
    _, _, b = _build(tmp_path / "second")
    assert a.model_dump_json() == b.model_dump_json()
