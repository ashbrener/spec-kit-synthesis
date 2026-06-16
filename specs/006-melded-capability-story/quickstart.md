# Quickstart — the melded capability story

Same one command as before, on a governed (or ungoverned) workspace:

```
SYN=.specify/extensions/synthesis
uv run --with pydantic --with pyyaml python "$SYN/skill/scripts/synthesize_atlas.py" \
    --from . --work .synthesis-portal            # then re-run with --out site/ after reasoning
```

What you get now (vs the old book-of-books):

- **One story, by capability.** `index.html` is a single melded narrative whose sections are
  capabilities (e.g. "Identity & Access"), not repositories. There are no separate `docs.html` /
  `backend.html` / `frontend.html` storybooks.
- **Woven across tiers.** Each capability opens with a plain-English functional read (from the source
  layer), then a per-tier "Backend" disclosure (endpoints, data model, services) and a "Frontend /
  integration" disclosure (how the client calls the API across tiers) — each linking to its own repo.
- **Built vs planned.** Capabilities and tiers are graded built / partial / planned; planned work is
  faded with a marker, so you see the system as built *and* as designed.
- **Diagrams.** Each capability carries the diagrams that fit it — an architecture-at-a-glance, a
  cross-tier request flow, a data model.
- **Human-titled sources.** Citations show titles like "Authentication — Contract (backend)" in a
  per-section sources table, not `spec-001 · auth-contract.md`.
- **A real index.** The reference surface is a tree — repo › feature (human title) › its artifacts
  (spec · plan · tasks · contracts · data-model · cited ADRs) — each drilling to source. The edge-list
  atlas is gone.

What stays the same: the single-repo storybook command, drill-to-source, and the fail-closed gates —
every claim still resolves to real source, or it doesn't ship.

For the build status to reflect code, the meld ingests each build repo's code automatically (you don't
configure it). An ungoverned or sparse workspace still produces a coherent capability story (clustered
by shared identifiers / feature-slug), never reverting to per-repo silos.
