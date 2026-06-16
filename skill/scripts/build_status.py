"""build_status.py — deterministic built / partial / planned grading (spec 006, US2).

Grades each capability and each of its tiers from BOTH signals:
  * coverage  — does the tier have real CODE backing its specs (a code fragment present)?
  * lifecycle — the tier's `tasks.md` checkbox ratio (all done / none / mixed / no tasks).
Conflicting signals resolve to `partial` with the reason recorded (never a silent pick — Principle IV);
absent code falls back to lifecycle only. Pure + deterministic.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pydantic import BaseModel  # noqa: E402
from schema import FragmentCorpus, SourceType  # noqa: E402

_CHECK_DONE = re.compile(r"^\s*[-*]\s*\[[xX]\]", re.MULTILINE)
_CHECK_TODO = re.compile(r"^\s*[-*]\s*\[ \]", re.MULTILINE)


class TierStatus(BaseModel):
    model_config = {"extra": "forbid"}
    origin: str
    grade: str                       # built | partial | planned
    coverage: str | None = None      # spec_backed | specced_only | code_only | none
    lifecycle: str | None = None     # e.g. "tasks 6/8", "no tasks"
    reason: str | None = None        # set when coverage and lifecycle disagreed


class CapabilityStatus(BaseModel):
    model_config = {"extra": "forbid"}
    cluster_id: str
    overall: str
    tiers: list[TierStatus] = []


def _tasks_ratio(texts: list[str]) -> tuple[int, int]:
    done = total = 0
    for t in texts:
        d = len(_CHECK_DONE.findall(t))
        td = len(_CHECK_TODO.findall(t))
        done += d
        total += d + td
    return done, total


def _grade_tier(origin: str, frags) -> TierStatus:
    has_code = any(f.source.type is SourceType.CODE for f in frags)
    has_spec = any(f.source.type is not SourceType.CODE for f in frags)
    done, total = _tasks_ratio([f.text for f in frags if f.kind == "tasks"])

    coverage = ("spec_backed" if has_code and has_spec else
                "code_only" if has_code else
                "specced_only" if has_spec else "none")
    lifecycle = f"tasks {done}/{total}" if total else "no tasks"

    life = ("done" if total and done == total else
            "none" if total and done == 0 else
            "partial" if total else "na")

    reason = None
    if has_code and life in ("none", "partial"):
        grade, reason = "partial", "code present but tasks incomplete"
    elif not has_code and life == "partial":
        grade, reason = "partial", "tasks underway, no code yet"
    elif has_code and life in ("done", "na"):
        grade = "built"
    elif not has_code and life in ("none", "na"):
        grade = "planned"
    else:
        grade = "partial"
    return TierStatus(origin=origin, grade=grade, coverage=coverage, lifecycle=lifecycle, reason=reason)


def grade(cluster, corpora: dict[str, FragmentCorpus]) -> CapabilityStatus:
    """Grade one capability cluster: per-tier + overall. `cluster` is a CapabilityCluster."""
    index = {f.id: f for c in corpora.values() for f in c.fragments}
    tiers: list[TierStatus] = []
    for origin in cluster.tiers:
        frags = [index[fid] for fid in cluster.members.get(origin, []) if fid in index]
        if frags:
            tiers.append(_grade_tier(origin, frags))
    grades = {t.grade for t in tiers}
    overall = ("built" if grades == {"built"} else
               "planned" if grades == {"planned"} else
               "partial" if grades else "planned")
    return CapabilityStatus(cluster_id=cluster.id, overall=overall, tiers=tiers)


__all__ = ["TierStatus", "CapabilityStatus", "grade"]
