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

# ADR identifiers (governance vocabulary @0.2.0). A *qualified* id (<NS>-ADR-NNN) is
# cross-repo-resolvable as written; a *bare* id (ADR-NNN) is repo-local and is qualified at
# read time with the owning repo's configured namespace (spec 004 US3). The two patterns are
# disjoint by construction; we scan for both and normalise bare → qualified per origin.
_ADR_QUALIFIED = re.compile(r"\b([A-Z][A-Z0-9]*-ADR-\d{3,})\b")
_ADR_BARE = re.compile(r"\b(ADR-\d{3,})\b")

# Fragment kinds that may CITE a decision (subject of `cites` in the contract) and the kind
# that IS a decision (object). Kept narrow so a generic doc never mints a citation.
_CITING_KINDS = {"spec", "plan"}
_ADR_KIND = "adr"


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
    Inputs a, b are (origin, locator, role).

    Mapping reconciled to the governance vocabulary (spec 004): code↔spec → `implements`;
    spec↔spec → `derived_from`; docs↔spec → `references` (the contract has no typed docs↔spec
    relation); anything else → the untyped `references` fallback. (Citation edges, code↔adr,
    are discovered separately as `cites` — see discover_adr_edges.)"""
    ra, rb = a[2], b[2]
    roles = {ra, rb}
    if roles == {"code", "spec"}:
        code, spec = (a, b) if ra == "code" else (b, a)
        return _ep(code[0], code[1]), _ep(spec[0], spec[1]), LinkRel.IMPLEMENTS
    if roles == {"spec"}:
        lo, hi = sorted([a, b], key=lambda x: x[0])
        return _ep(lo[0], lo[1]), _ep(hi[0], hi[1]), LinkRel.DERIVED_FROM
    lo, hi = sorted([a, b], key=lambda x: x[0])  # stable order for a plain reference (incl. docs↔spec)
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


def qualify_adr(token: str, namespace: str | None) -> str | None:
    """Normalise an ADR reference to its cross-repo-resolvable, qualified form, or None.

    A qualified `<NS>-ADR-NNN` is returned unchanged (already cross-repo). A bare `ADR-NNN`
    is qualified with the owning repo's `namespace` → `<namespace>-ADR-NNN`; if the repo has
    no configured namespace the bare id cannot be qualified (stays repo-local) → None. No file
    is renamed: this is purely a read-time normalisation (spec 004 US3, FR-003)."""
    if _ADR_QUALIFIED.fullmatch(token):
        return token
    if _ADR_BARE.fullmatch(token):
        if namespace:
            return f"{namespace}-{token}"
        return None
    return None


def extract_adr_refs(corpus: FragmentCorpus, namespace: str | None) -> dict[str, dict[str, str]]:
    """Per-corpus ADR references → {qualified_adr_id: {kind: representative_locator}}.

    Both qualified and bare forms are scanned; a bare id is qualified with `namespace` (the
    owning repo's). Bare ids with no namespace are dropped (repo-local, never cross-matched).
    Only citing kinds (spec/plan) and adr kinds participate, so a generic doc mentioning an
    ADR id in passing never mints a citation. Representative = the min locator per (id, kind),
    keeping the edge count bounded and deterministic."""
    out: dict[str, dict[str, str]] = defaultdict(dict)
    for f in corpus.fragments:
        kind = f.kind
        if kind != _ADR_KIND and kind not in _CITING_KINDS:
            continue
        role_kind = _ADR_KIND if kind == _ADR_KIND else "citing"
        tokens = set(_ADR_QUALIFIED.findall(f.text or "")) | set(_ADR_BARE.findall(f.text or ""))
        for tok in tokens:
            qid = qualify_adr(tok, namespace)
            if qid is None:
                continue
            cur = out[qid].get(role_kind)
            out[qid][role_kind] = f.id if cur is None else min(cur, f.id)
    return out


def discover_adr_edges(manifest: WorkspaceManifest, corpora: dict[str, FragmentCorpus],
                       namespaces: dict[str, str | None] | None = None) -> list[LinkEdge]:
    """Deterministic `cites` edges: a citing fragment (spec/plan) → a decision (adr) sharing a
    qualified ADR id (spec 004 US1, FR-002).

    Bare `ADR-NNN` ids are qualified per-origin with that repo's configured namespace
    (`namespaces[origin]`) before indexing, so a bare id stays repo-local — two repos that
    each hold a bare `ADR-001` qualify to different namespaces and never cross-match; only the
    fully-qualified form resolves across a repo boundary (FR-003)."""
    namespaces = namespaces or {}
    # qualified_adr_id → role_kind ("citing"/"adr") → {origin: representative_locator}
    index: dict[str, dict[str, dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
    for origin in sorted(corpora):
        ns = namespaces.get(origin)
        for qid, by_kind in extract_adr_refs(corpora[origin], ns).items():
            for role_kind, loc in by_kind.items():
                cur = index[qid][role_kind].get(origin)
                index[qid][role_kind][origin] = loc if cur is None else min(cur, loc)
    edges: list[LinkEdge] = []
    for qid in sorted(index):
        citing = index[qid].get("citing", {})
        adrs = index[qid].get("adr", {})
        if not citing or not adrs:
            continue
        for c_origin in sorted(citing):
            for a_origin in sorted(adrs):
                if c_origin == a_origin and citing[c_origin] == adrs[a_origin]:
                    continue  # same fragment is both citing-shaped and adr-shaped — skip self
                edges.append(LinkEdge(
                    src=_ep(c_origin, citing[c_origin]),
                    dst=_ep(a_origin, adrs[a_origin]),
                    rel=LinkRel.CITES,
                    evidence_kind=LinkEvidenceKind.IDENTIFIER, evidence=qid))
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
                     prose_edges: list[LinkEdge] | None = None,
                     namespaces: dict[str, str | None] | None = None) -> LinkGraph:
    """Merge declared (trusted) + identifier + cites (deterministic) + prose (agent), deduped
    by (src, dst, rel) preferring the most-trusted evidence first. Deterministic.

    `namespaces` maps each member origin → its configured ADR namespace (from the repo's
    `.spec-arch-governance.yml`), used to qualify bare `ADR-NNN` ids before citation discovery
    (spec 004). Absent → bare ids stay repo-local and mint no cross-repo citation."""
    seen: set[tuple] = set()
    merged: list[LinkEdge] = []
    for e in [*declared_edges(manifest),
              *discover_identifier_edges(manifest, corpora),
              *discover_adr_edges(manifest, corpora, namespaces),
              *(prose_edges or [])]:
        k = _key(e)
        if k in seen:
            continue
        seen.add(k)
        merged.append(e)
    return LinkGraph(edges=merged)
