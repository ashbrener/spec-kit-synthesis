# Quickstart: Contract-Driven Capability Clustering

## What changed
Clustering now trusts the **declared** governance graph: only declared citations + same-feature grouping (plus a source↔build identifier signal) place a fragment in a capability. Build↔build identifier noise no longer chains the catch-alls. Broad/hub capabilities render faithfully and are flagged (`hub_dependents`), not re-shaped. Archive/agent-meta files are no longer ingested.

## Run the tests
```bash
uv run pytest skill/tests -q
uv run pytest skill/tests/test_cluster.py skill/tests/test_adapter_doc.py -q
```

## The three acceptance checks (encoded as tests)
- **R1 — inference doesn't cluster:** two build features joined only by a shared identifier are not co-members; removing build↔build identifier + prose edges leaves membership unchanged.
- **FR-004 — hubs faithful + flagged:** a feature declared `derived_from` by N≥2 features renders as the declared capability with `hub_dependents == N`; no split/re-anchor.
- **R3 — ingestion hygiene:** an archive dir + agent/handoff/resume meta files produce no fragments/clusters; real specs/ADRs/narrative unaffected.

## Optional: re-confirm on the real workspace (read-only)
Re-run the structural assessment (the script used during planning) against the live workspace and confirm: the three near-duplicate ~380-frag catch-alls are gone, background noise clusters drop, and any remaining broad capability is flagged `hub_dependents>=2` (the governance signal to refine the docs).

## Gates
`verify.py` / `verify_links.py` untouched; `uv run pytest skill/tests -q` green before push.
