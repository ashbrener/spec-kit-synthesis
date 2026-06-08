"""discover_links.py — cross-repo edge discovery for the portal LinkGraph (spec 002, Phase D).

Tiered discovery, following the §5.4 evidence ladder (key decision #2):

  1. DECLARED   — operator-authored edges in the manifest. Trusted.
  2. IDENTIFIER — shared QUALIFIED identifiers (FR-NNN, feature slugs) across members.
                  Deterministic, NO LLM. A generic word like "config" never mints an edge.
  3. PROSE      — literal prose references found in a source fragment. Agent-discovered and
                  passed in (only within manifest-declared repo pairs). Not done here — it is
                  the in-session agent's reasoning, merged under the same discipline.

This module is PURE + deterministic (stdlib only): identical inputs → identical LinkGraph.
Every edge carries grounded evidence; the Phase-E `verify_links` gate is fail-closed over it.
"""

from __future__ import annotations

import re
from collections import defaultdict

from schema import (
    DeclaredLink,
    FragmentCorpus,
    LinkEdge,
    LinkEndpoint,
    LinkEvidenceKind,
    LinkGraph,
    LinkRel,
    WorkspaceManifest,
)

# Stable, QUALIFIED cross-repo identifiers ONLY — requirement codes (FR-/SC-/NFR-/US-NNN)
# and feature slugs (NNN-some-slug). Deliberately not generic words, so a bare "config"
# or "database" can never mint a spurious edge (the top risk named in the spec).
_QUALIFIED_ID = re.compile(r"\b(?:(?:FR|SC|NFR|US)-\d+|\d{3}-[a-z][a-z0-9]*(?:-[a-z0-9]+)+)\b")


def extract_identifiers(corpus: FragmentCorpus) -> dict[str, set[str]]:
    """Map each qualified identifier → the set of fragment locators that mention it."""
    out: dict[str, set[str]] = defaultdict(set)
    for f in corpus.fragments:
        for tok in _QUALIFIED_ID.findall(f.text or ""):
            out[tok].add(f.id)
    return out


def _ep(origin: str, locator: str) -> LinkEndpoint:
    return LinkEndpoint(origin=origin, locator=locator)


def _typed_edge(a: tuple[str, str, str], b: tuple[str, str, str]) -> tuple[LinkEndpoint, LinkEndpoint, LinkRel]:
    """Direction + rel for a shared identifier between two members, inferred from their roles.
    Inputs a, b are (origin, locator, role)."""
    ra, rb = a[2], b[2]
    roles = {ra, rb}
    if roles == {"code", "spec"}:
        code, spec = (a, b) if ra == "code" else (b, a)
        return _ep(code[0], code[1]), _ep(spec[0], spec[1]), LinkRel.IMPLEMENTS
    if roles == {"docs", "spec"}:
        docs, spec = (a, b) if ra == "docs" else (b, a)
        return _ep(docs[0], docs[1]), _ep(spec[0], spec[1]), LinkRel.SPECIFIED_BY
    if "intent" in roles and roles != {"intent"}:
        other, intent = (a, b) if ra != "intent" else (b, a)
        return _ep(other[0], other[1]), _ep(intent[0], intent[1]), LinkRel.DERIVES_FROM
    lo, hi = sorted([a, b], key=lambda x: x[0])  # stable order for a plain reference
    return _ep(lo[0], lo[1]), _ep(hi[0], hi[1]), LinkRel.REFERENCES


def discover_identifier_edges(manifest: WorkspaceManifest, corpora: dict[str, FragmentCorpus]) -> list[LinkEdge]:
    """Deterministic: an edge for every qualified identifier shared across two members.
    Each member contributes one representative fragment per token (the min locator), so the
    edge count is bounded and stable regardless of how often a token recurs within a repo."""
    roles = {m.origin: m.role for m in manifest.members}
    tok_member_rep: dict[str, dict[str, str]] = defaultdict(dict)
    for origin in sorted(corpora):
        for tok, locs in extract_identifiers(corpora[origin]).items():
            rep = min(locs)
            cur = tok_member_rep[tok].get(origin)
            tok_member_rep[tok][origin] = rep if cur is None else min(cur, rep)
    edges: list[LinkEdge] = []
    for tok in sorted(tok_member_rep):
        members = sorted(tok_member_rep[tok])
        if len(members) < 2:
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                oa, ob = members[i], members[j]
                a = (oa, tok_member_rep[tok][oa], roles.get(oa, "spec"))
                b = (ob, tok_member_rep[tok][ob], roles.get(ob, "spec"))
                src, dst, rel = _typed_edge(a, b)
                edges.append(LinkEdge(src=src, dst=dst, rel=rel,
                                      evidence_kind=LinkEvidenceKind.IDENTIFIER, evidence=tok))
    return edges


def _ns(origin: str, locator: str) -> str:
    pref = f"{origin}::"
    return locator if locator.startswith(pref) else pref + locator


def declared_edges(manifest: WorkspaceManifest) -> list[LinkEdge]:
    """Operator-declared edges → trusted LinkEdges (member-relative locators namespaced)."""
    return [
        LinkEdge(
            src=_ep(d.src_origin, _ns(d.src_origin, d.src_locator)),
            dst=_ep(d.dst_origin, _ns(d.dst_origin, d.dst_locator)),
            rel=d.rel, evidence_kind=LinkEvidenceKind.DECLARED, evidence="manifest",
        )
        for d in manifest.links
    ]


def _key(e: LinkEdge) -> tuple:
    return (e.src.origin, e.src.locator, e.dst.origin, e.dst.locator, e.rel.value)


def build_link_graph(manifest: WorkspaceManifest, corpora: dict[str, FragmentCorpus],
                     prose_edges: list[LinkEdge] | None = None) -> LinkGraph:
    """Merge declared (trusted) + identifier (deterministic) + prose (agent), deduped by
    (src, dst, rel) preferring the most-trusted evidence first. Deterministic."""
    seen: set[tuple] = set()
    merged: list[LinkEdge] = []
    for e in [*declared_edges(manifest), *discover_identifier_edges(manifest, corpora), *(prose_edges or [])]:
        k = _key(e)
        if k in seen:
            continue
        seen.add(k)
        merged.append(e)
    return LinkGraph(edges=merged)
