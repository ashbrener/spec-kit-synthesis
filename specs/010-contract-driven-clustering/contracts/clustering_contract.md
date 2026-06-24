# Contract: contract-driven clustering

Extends the spec-009 `build_clusters()` contract. Signature unchanged; guarantees tightened to "faithful projection of the declared graph."

## `build_clusters(corpora, link_graph, source_origins) -> ClusterSet`

Pure + deterministic, stdlib only.

### Membership guarantees
1. **Declared-driven.** A fragment joins a capability only via (a) a `declared` edge, (b) same-feature grouping, or (c) an `identifier` edge whose endpoints are a source↔build pair. No `prose` edge and no build↔build / source↔source `identifier` edge confers membership.
2. **Inference-invariant.** Removing every build↔build identifier edge and every prose edge from the input leaves the `ClusterSet` membership byte-identical.
3. **Hubs faithful + flagged.** A broad/hub feature is rendered as the declared capability (not demoted, re-anchored, or split); its cluster carries `hub_dependents = <count of distinct features declaring it>`.
4. **Leaf/planned anchors.** A declared feature with no declared dependents anchors its own capability.
5. **Preserved.** Multi-membership, classification (`capability`/`decision`/`background`), deterministic ordering, evidence notes, and the cited-ADR behaviour (now restricted to declared `cites`) all hold.
6. **Fail-closed.** Every membership rests on a real declared/same-feature/source↔build basis; nothing fabricated.

### Negative guarantees (must NOT happen)
- Two build features co-cluster because of a shared identifier.
- A capability's shape is altered by a reader heuristic (split/merge/re-anchor).
- A `prose` edge places a fragment in a capability.

## Ingestion contract (`adapter_doc.build_corpus`)
- Archive/audit directories and agent/process meta files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `RESUME.md`, `*HANDOFF*`, `WORKTREES.md`) are excluded deterministically at any depth → they produce no fragments and therefore no clusters.
- Genuine specs, ADRs, and narrative are unaffected (only non-source residue is excluded).

## Schema contract (`schema.py`)
- `CapabilityCluster.hub_dependents: int = 0` — additive, defaulted; absence/zero is the non-hub case and keeps prior golden output stable.

## Downstream tolerance
Render/meld/status/index require no change; the additive `hub_dependents` is ignored unless a consumer opts to surface it.
