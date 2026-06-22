# Quickstart: Source-Anchored Capability Clustering

## What changed

Clustering no longer merges everything a build artifact touches into one component. Capabilities are anchored to source features and stay separate; cross-cutting build artifacts and cited ADRs attach to each capability they serve (multi-membership). Uncited ADRs and untied narrative stay honest standalones.

## Run the test suite

```bash
uv run pytest skill/tests -q                 # full suite, must be green
uv run pytest skill/tests/test_cluster.py -q # the membership model
```

## Verify the two pathologies are gone (conceptual checks, encoded as tests)

- **Anti-over-merge (Q1):** a corpus with two unconnected source features S1, S2 and a build feature B that relates to both ⟹ still two `capability` clusters; B is a member of both.
- **No singleton ADRs (Q2):** an ADR cited by a capability's spec is a member of that capability; an ADR cited by nothing remains its own `decision` cluster.

## Verify determinism

```bash
# build_clusters is pure: same inputs -> byte-identical ClusterSet
uv run python - <<'PY'
import sys; sys.path.insert(0, "skill/scripts")
# (see test_cluster.py for the canonical determinism assertion)
PY
```
The canonical determinism assertion lives in `test_cluster.py` (serialize twice, compare bytes).

## Verify downstream still melds

```bash
uv run pytest skill/tests/test_atlas_meld.py skill/tests/test_render_meld.py -q
```
These confirm the meld/render tolerate a fragment surfacing under more than one capability (content bundled once, cited from each).

## Gates

- `verify.py` / `verify_links.py` are unaffected (they grade claims/edges, not clusters) and are never edited to pass.
- `uv run pytest skill/tests -q` green before any push.
