"""Deterministic build-status grading (build_status.py — spec 006, US2).

Neutral examples only (CORE / API / WEB).
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_status as bs  # noqa: E402
from cluster import CapabilityCluster  # noqa: E402
from schema import Fragment, FragmentCorpus, SourceRef, SourceType  # noqa: E402


def _spec(origin, locator, kind="spec", text="x"):
    fid = f"{origin}::{locator}"
    return Fragment(id=fid, kind=kind, feature_key="auth", text=text,
                    source=SourceRef(type=SourceType.SPEC, origin=origin, name=locator, locator=fid))


def _code(origin, locator):
    fid = f"{origin}::{locator}"
    return Fragment(id=fid, kind="code", feature_key="auth", text="def f(): ...",
                    source=SourceRef(type=SourceType.CODE, origin=origin, name=locator, locator=fid))


def _corpora(frags):
    by: dict[str, list] = {}
    for f in frags:
        by.setdefault(f.source.origin, []).append(f)
    return {o: FragmentCorpus(project_name=o, fragments=fs) for o, fs in by.items()}


def _cluster(members):
    return CapabilityCluster(id="auth", seed="auth", members=members, tiers=list(members))


def test_built_when_code_backs_spec():
    frags = [_spec("backend", "007/spec.md"), _code("backend", "src/auth.py")]
    st = bs.grade(_cluster({"backend": [f.id for f in frags]}), _corpora(frags))
    assert st.overall == "built"
    assert st.tiers[0].coverage == "spec_backed"


def test_planned_when_specced_only_and_not_started():
    frags = [_spec("backend", "007/spec.md"),
             _spec("backend", "007/tasks.md", kind="tasks", text="- [ ] a\n- [ ] b\n")]
    st = bs.grade(_cluster({"backend": [f.id for f in frags]}), _corpora(frags))
    assert st.overall == "planned"
    assert st.tiers[0].coverage == "specced_only"


def test_partial_on_conflict_code_present_tasks_incomplete():
    frags = [_spec("backend", "007/spec.md"), _code("backend", "src/auth.py"),
             _spec("backend", "007/tasks.md", kind="tasks", text="- [x] a\n- [ ] b\n")]
    st = bs.grade(_cluster({"backend": [f.id for f in frags]}), _corpora(frags))
    assert st.tiers[0].grade == "partial"
    assert st.tiers[0].reason


def test_overall_partial_when_tiers_differ():
    frags = [_spec("backend", "b/spec.md"), _code("backend", "src/b.py"),   # built
             _spec("frontend", "f/spec.md")]                                # planned
    st = bs.grade(_cluster({"backend": ["backend::b/spec.md", "backend::src/b.py"],
                            "frontend": ["frontend::f/spec.md"]}), _corpora(frags))
    assert st.overall == "partial"
