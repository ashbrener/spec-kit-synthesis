"""cluster.py — deterministic capability clustering (spec 006).

Groups the workspace's fragments into CAPABILITIES — the spine of the melded story — by union-find
over the existing typed, evidence-graded cross-repo link graph. No external graph system, no graph
database, no embeddings, no new runtime dependency (FR-006); the graph is small and already built, so
this is plain stdlib union-find.

Membership only: clustering decides which fragments belong together; the in-session agent later names
and groups clusters into theme sections (FR-004a) but cannot fabricate or split membership.

Cohesion rules (deterministic, reproducible):
  * fragments of the SAME feature (same origin + feature_key) are unioned;
  * fragments joined by a STRONG cross-repo edge — `derived_from` / `cites` / `implements` — are
    unioned (the weak untyped `references` edge is excluded, so a shared utility does not fuse
    everything into one mega-cluster — the over-merge guard);
  * a component containing a source-role fragment is seeded by (anchored to) that source feature;
    components with no source member are orphan capabilities (kept on their own).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pydantic import BaseModel  # noqa: E402
from schema import FragmentCorpus, LinkGraph  # noqa: E402

# The cross-repo relations strong enough to mean "same capability" (excludes untyped `references`).
_STRONG_RELS = {"derived_from", "cites", "implements"}


class CapabilityCluster(BaseModel):
    """One capability's membership (build IR; named later by the agent)."""

    model_config = {"extra": "forbid"}

    id: str
    seed: str | None = None                  # the source feature_key that anchors it (None = orphan)
    members: dict[str, list[str]] = {}       # origin -> fragment ids (grouped by tier)
    tiers: list[str] = []                    # contributing origins, source first
    evidence: list[str] = []                 # why members joined — reviewable


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


def build_clusters(corpora: dict[str, FragmentCorpus], link_graph: LinkGraph,
                   source_origins: set[str]) -> ClusterSet:
    """Cluster the merged workspace into capabilities. Deterministic + reproducible.

    `corpora` maps origin -> its origin-stamped FragmentCorpus; `source_origins` are the origins whose
    role is source (their features seed/anchor capabilities)."""
    uf = _UF()
    frag_origin: dict[str, str] = {}
    frag_feature: dict[str, str | None] = {}
    # feature anchor key (origin::feature_key) -> representative fragment id, for intra-feature union
    feature_rep: dict[str, str] = {}

    # register fragments + union within a feature
    for origin in sorted(corpora):
        for f in corpora[origin].fragments:
            uf.add(f.id)
            frag_origin[f.id] = origin
            fk = _feature_key(f)
            frag_feature[f.id] = fk
            if fk is not None:
                anchor = f"{origin}::{fk}"
                if anchor in feature_rep:
                    uf.union(feature_rep[anchor], f.id)
                else:
                    feature_rep[anchor] = f.id

    # union across strong cross-repo edges
    evidence_by_root: dict[str, list[str]] = {}
    for e in link_graph.edges:
        rel = e.rel.value if hasattr(e.rel, "value") else str(e.rel)
        if rel not in _STRONG_RELS:
            continue
        s, d = e.src.locator, e.dst.locator
        if s not in frag_origin or d not in frag_origin:
            continue
        uf.union(s, d)
        note = f"{e.src.origin}:{_short(s)} {rel} {e.dst.origin}:{_short(d)}"
        evidence_by_root.setdefault(uf.find(s), []).append(note)

    # gather components
    comps: dict[str, list[str]] = {}
    for fid in frag_origin:
        comps.setdefault(uf.find(fid), []).append(fid)

    clusters: list[CapabilityCluster] = []
    unclustered: list[str] = []
    for root, fids in comps.items():
        origins = {frag_origin[f] for f in fids}
        has_source = bool(origins & source_origins)
        # a lone fragment with no feature and no cross-repo tie is genuinely unclustered
        if len(fids) == 1 and frag_feature[fids[0]] is None and not has_source:
            unclustered.append(fids[0])
            continue
        members: dict[str, list[str]] = {}
        for f in sorted(fids):
            members.setdefault(frag_origin[f], []).append(f)
        # seed = a source feature key in the component (deterministic: smallest)
        seed = None
        src_feats = sorted({frag_feature[f] for f in fids
                            if frag_origin[f] in source_origins and frag_feature[f]})
        if src_feats:
            seed = src_feats[0]
        # tiers: source origins first, then the rest — both alphabetical
        srcs = sorted(o for o in members if o in source_origins)
        rest = sorted(o for o in members if o not in source_origins)
        tiers = srcs + rest
        # collect evidence accumulated for any root that merged into this component
        ev = sorted(set(evidence_by_root.get(root, [])))
        cid = seed or f"orphan:{min(fids)}"
        clusters.append(CapabilityCluster(id=cid, seed=seed, members=members, tiers=tiers, evidence=ev))

    # deterministic order: source-seeded first (by id), then orphans (by id)
    clusters.sort(key=lambda c: (c.seed is None, c.id))
    return ClusterSet(clusters=clusters, unclustered=sorted(unclustered))


def _short(locator: str) -> str:
    """A compact locator for evidence notes (drop the origin:: prefix)."""
    return locator.split("::", 1)[-1]


__all__ = ["CapabilityCluster", "ClusterSet", "build_clusters"]
