"""cluster.py — deterministic, source-anchored capability clustering (spec 006/007/009).

Groups the workspace's fragments into CAPABILITIES — the spine of the melded story — over the existing
typed, evidence-graded cross-repo link graph. No external graph system, no graph database, no
embeddings, no new runtime dependency (FR-006); the graph is small and already built, so this is plain
stdlib logic.

Membership only: clustering decides which fragments belong together; the in-session agent later names
and groups clusters into theme sections (FR-004a) but cannot fabricate or split membership.

Model (spec 009 — replaced connected-component union-find, which over-merged): a capability is anchored
to ONE source feature and is NEVER merged with another anchor. Membership grows by a typed one-hop
fixpoint over STRONG edges (the weak untyped `references` edge never confers membership — over-merge
guard):
  * fragments of the same feature (origin + feature_key) form one unit, the unit of membership;
  * R1 `derived_from`  — a spec deriving from a member spec/source joins;
  * R2 `implements`    — code implementing a member spec joins;
  * R3 `cites`         — a decision a member spec cites rides inside the capability;
  * R4 `cites` (meld)  — a build spec that cites a decision THIS source anchor also cites melds in
                         (it implements the source's decision); restricted to the anchor's own
                         citations, so a shared ADR never bridges two anchors or two build specs.
ADR and code units are membership SINKS (attached, never traversed outward). A unit reachable from
several anchors is a member of EACH (multi-membership); a unit reachable from none is emitted honestly
as an orphan capability, a standalone `decision` (uncited ADR), `background`, or unclustered (a
feature-less, edge-less fragment). Deterministic + reproducible: identical inputs → byte-identical
ClusterSet.

Spec 010 makes membership a faithful projection of the DECLARED graph: only `declared` edges +
same-feature grouping confer membership; an `identifier` edge confers for `cites` (a specific ADR id)
and for `derived_from`/`implements` only across a source↔build pair (never build↔build / source↔source
— the measured noise); `prose` never. A broad/hub feature (one several others declare derived_from) is
rendered faithfully and FLAGGED via `hub_dependents` (a governance signal) — never split or re-anchored.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pydantic import BaseModel  # noqa: E402
from schema import FragmentCorpus, LinkEvidenceKind, LinkGraph, SourceType  # noqa: E402

# The cross-repo relations strong enough to mean "same capability" (excludes untyped `references`).
_STRONG_RELS = {"derived_from", "cites", "implements"}

# Spec-kit artifact kinds that make a cluster a CAPABILITY (vs a lone decision / background).
_SPEC_KINDS = {"spec", "plan", "tasks", "data-model", "contract", "research"}


def _classify(fids: list[str], index: dict) -> str:
    """Label a cluster by membership (spec 007): capability (has a spec/code), else decision (only
    ADRs), else background (only free-form narrative). Pure + deterministic."""
    has_spec = has_adr = has_code = False
    for fid in fids:
        f = index.get(fid)
        if f is None:
            continue
        t = f.source.type
        if t is SourceType.CODE or f.kind in ("code", "code-symbol"):
            has_code = True
        elif t is SourceType.ADR or f.kind == "adr":
            has_adr = True
        elif t is SourceType.SPEC or f.kind in _SPEC_KINDS:
            has_spec = True
    if has_spec or has_code:
        return "capability"
    if has_adr:
        return "decision"
    return "background"


class CapabilityCluster(BaseModel):
    """One capability's membership (build IR; named later by the agent)."""

    model_config = {"extra": "forbid"}

    id: str
    seed: str | None = None                  # the source feature_key that anchors it (None = orphan)
    members: dict[str, list[str]] = {}       # origin -> fragment ids (grouped by tier)
    tiers: list[str] = []                    # contributing origins, source first
    evidence: list[str] = []                 # why members joined — reviewable
    kind: str = "capability"                 # capability | decision | background (spec 007)
    hub_dependents: int = 0                  # # distinct features that DECLARE derived_from this
    #                                          anchor; >=2 == "broad (hub)" — a governance signal that
    #                                          the declared grain is coarse (spec 010, FR-004). Faithful:
    #                                          the reader flags, it does not split/re-anchor.


class ClusterSet(BaseModel):
    model_config = {"extra": "forbid"}

    clusters: list[CapabilityCluster] = []
    unclustered: list[str] = []              # fragment ids that joined no capability


class _UF:
    """Tiny deterministic union-find over string keys."""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self.parent.setdefault(x, x)

    def find(self, x: str) -> str:
        self.add(x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        # deterministic: smaller key becomes the root
        lo, hi = sorted((ra, rb))
        self.parent[hi] = lo


def _feature_key(frag) -> str | None:
    """A fragment's feature grouping key (source-internal), or None when it carries none."""
    return frag.feature_key or None


def _unit_key(origin: str, frag) -> str:
    """The clustering unit a fragment belongs to: its feature `(origin::feature_key)`, or a
    per-fragment singleton `(origin::#id)` when it carries no feature key."""
    fk = _feature_key(frag)
    return f"{origin}::{fk}" if fk is not None else f"{origin}::#{frag.id}"


def _shape(fids: list[str], index: dict) -> str:
    """The propagation shape of a unit, by its fragments: `spec` (anything spec-like — can propagate),
    else `code`, else `adr`, else `other`. Spec wins so a mixed spec+code feature still propagates."""
    has_spec = has_code = has_adr = False
    for fid in fids:
        f = index.get(fid)
        if f is None:
            continue
        t = f.source.type
        if t is SourceType.SPEC or f.kind in _SPEC_KINDS:
            has_spec = True
        elif t is SourceType.CODE or f.kind in ("code", "code-symbol"):
            has_code = True
        elif t is SourceType.ADR or f.kind == "adr":
            has_adr = True
    if has_spec:
        return "spec"
    if has_code:
        return "code"
    if has_adr:
        return "adr"
    return "other"


def _emit_cluster(unit_ids: list[str], seed: str | None, evidence: list[str],
                  unit_frags: dict[str, list[str]], unit_origin: dict[str, str],
                  source_origins: set[str], index: dict, hub_dependents: int = 0) -> CapabilityCluster:
    members: dict[str, list[str]] = {}
    for u in sorted(unit_ids):
        for fid in sorted(unit_frags[u]):
            members.setdefault(unit_origin[u], []).append(fid)
    fids = [fid for u in unit_ids for fid in unit_frags[u]]
    srcs = sorted(o for o in members if o in source_origins)
    rest = sorted(o for o in members if o not in source_origins)
    cid = seed or f"orphan:{min(fids)}"
    return CapabilityCluster(id=cid, seed=seed, members=members, tiers=srcs + rest,
                             evidence=sorted(set(evidence)), kind=_classify(fids, index),
                             hub_dependents=hub_dependents)


def build_clusters(corpora: dict[str, FragmentCorpus], link_graph: LinkGraph,
                   source_origins: set[str]) -> ClusterSet:
    """Cluster the merged workspace into source-anchored capabilities (spec 009). Deterministic.

    A capability is anchored to ONE source feature and never merged with another anchor. Membership
    grows by a typed one-hop fixpoint over strong edges — `derived_from` adds the deriving spec,
    `implements` adds the code, `cites` adds the decision — in which ADR and code units are SINKS
    (attached, never traversed outward). A unit reachable from several anchors is a member of each
    (multi-membership); a unit reachable from none is an honest orphan/decision/background/unclustered.

    `corpora` maps origin -> its origin-stamped FragmentCorpus; `source_origins` are the origins whose
    role is source (their spec features anchor capabilities)."""
    index = {f.id: f for c in corpora.values() for f in c.fragments}

    # ── feature units (the unit of membership) ───────────────────────────────
    unit_of: dict[str, str] = {}                 # fragment id -> unit id
    unit_frags: dict[str, list[str]] = {}        # unit id -> fragment ids
    unit_origin: dict[str, str] = {}
    unit_feature: dict[str, str | None] = {}     # unit id -> feature_key (None for singletons)
    for origin in sorted(corpora):
        for f in corpora[origin].fragments:
            u = _unit_key(origin, f)
            unit_of[f.id] = u
            unit_frags.setdefault(u, []).append(f.id)
            unit_origin[u] = origin
            unit_feature.setdefault(u, _feature_key(f))
    shape = {u: _shape(fids, index) for u, fids in unit_frags.items()}

    # ── typed strong edges, lifted to the unit level + EVIDENCE-TIER gated (spec 010, R1) ──
    # Only DECLARED edges + same-feature grouping confer membership. An IDENTIFIER edge confers
    # membership for `cites` (a specific ADR id — reliable) and for `derived_from`/`implements` ONLY
    # across a source↔build pair (a real refinement); never build↔build / source↔source (the measured
    # noise that chained the catch-alls). PROSE never confers. The weak `references` rel is excluded.
    strong: list[tuple[str, str, str, str]] = []   # (rel, src_unit, dst_unit, evidence_note)
    declared_df_in: dict[str, set[str]] = {}        # anchor unit -> {units that DECLARE derived_from it} (FR-004)
    for e in link_graph.edges:
        rel = e.rel.value if hasattr(e.rel, "value") else str(e.rel)
        if rel not in _STRONG_RELS:
            continue
        s, d = e.src.locator, e.dst.locator
        if s not in unit_of or d not in unit_of:
            continue
        ek = e.evidence_kind
        if ek is LinkEvidenceKind.DECLARED and rel == "derived_from":
            declared_df_in.setdefault(unit_of[d], set()).add(unit_of[s])
        if ek is LinkEvidenceKind.PROSE:
            continue                                # inferred prose never confers membership
        if ek is LinkEvidenceKind.IDENTIFIER and rel != "cites":
            n_src = (e.src.origin in source_origins) + (e.dst.origin in source_origins)
            if n_src != 1:
                continue                            # identifier derived_from/implements: source↔build only
        note = f"{e.src.origin}:{_short(s)} {rel} {e.dst.origin}:{_short(d)}"
        strong.append((rel, unit_of[s], unit_of[d], note))
    strong.sort()

    # anchors: source-role, spec-shaped units with a real feature key (decisions/narrative never anchor)
    anchors = sorted(u for u in unit_frags
                     if unit_origin[u] in source_origins and unit_feature[u] is not None
                     and shape[u] == "spec")
    anchor_set = set(anchors)

    # ── per-anchor typed fixpoint (multi-membership; ADR/code are sinks) ──────
    clusters: list[CapabilityCluster] = []
    claimed: set[str] = set()
    for s in anchors:
        members = {s}
        notes: list[str] = []
        # decisions the SOURCE anchor itself cites — the only ADRs that may meld a build spec in (R4).
        s_adrs = {du for rel, su, du in ((r, a, b) for r, a, b, _ in strong) if rel == "cites" and su == s}
        changed = True
        while changed:
            changed = False
            for rel, su, du, note in strong:
                add = None
                if rel == "derived_from" and du in members and shape[du] == "spec" and su not in anchor_set:
                    add = su                                   # R1: a spec deriving from a member spec/source
                elif rel == "implements" and du in members and shape[du] == "spec" and su not in anchor_set:
                    add = su                                   # R2: code implementing a member spec
                elif rel == "cites" and su in members and shape[su] == "spec" and shape[du] == "adr" \
                        and du not in anchor_set:
                    add = du                                   # R3: a decision a member spec cites rides inside
                elif rel == "cites" and du in s_adrs and su != s and su not in anchor_set:
                    add = su                                   # R4: a build spec citing a decision THIS source
                    #      anchor also cites melds in (build implements the source's decision). Restricted to
                    #      the anchor's own citations so a shared ADR never bridges two anchors / two builds.
                if add is not None and add not in members:
                    members.add(add)
                    notes.append(note)
                    changed = True
        claimed |= members
        clusters.append(_emit_cluster(sorted(members), unit_feature[s], notes,
                                      unit_frags, unit_origin, source_origins, index,
                                      hub_dependents=len(declared_df_in.get(s, ()))))

    # ── orphans: union remaining units over derived_from/implements only (NO ADR bridge) ──
    remaining = [u for u in sorted(unit_frags) if u not in claimed]
    rem_set = set(remaining)
    ouf = _UF()
    for u in remaining:
        ouf.add(u)
    orphan_notes: dict[str, list[str]] = {}
    for rel, su, du, note in strong:
        if rel == "cites":
            continue                                           # a shared ADR must not fuse orphans
        if su in rem_set and du in rem_set:
            ouf.union(su, du)
            orphan_notes.setdefault(ouf.find(su), []).append(note)

    ocomps: dict[str, list[str]] = {}
    for u in remaining:
        ocomps.setdefault(ouf.find(u), []).append(u)

    unclustered: list[str] = []
    for root, us in ocomps.items():
        # a lone, feature-less, edge-less fragment has no capability signal → genuinely unclustered
        if len(us) == 1 and unit_feature[us[0]] is None and len(unit_frags[us[0]]) == 1:
            unclustered.append(unit_frags[us[0]][0])
            continue
        notes = [n for r, ns in orphan_notes.items() if ouf.find(r) == root for n in ns]
        clusters.append(_emit_cluster(sorted(us), None, notes,
                                      unit_frags, unit_origin, source_origins, index))

    # deterministic order: capabilities, then decisions, then background; source-seeded before orphans, by id
    _kind_rank = {"capability": 0, "decision": 1, "background": 2}
    clusters.sort(key=lambda c: (_kind_rank.get(c.kind, 3), c.seed is None, c.id))
    return ClusterSet(clusters=clusters, unclustered=sorted(unclustered))


def _short(locator: str) -> str:
    """A compact locator for evidence notes (drop the origin:: prefix)."""
    return locator.split("::", 1)[-1]


__all__ = ["CapabilityCluster", "ClusterSet", "build_clusters"]
