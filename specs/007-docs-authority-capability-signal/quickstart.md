# Quickstart — a docs-authority workspace

Same one command as before, on a governed docs-authority workspace (the source repo is a docs
repository: `specs_dir` with spec-kit specs, an `adr_dir`, and narrative folders):

```
SYN=.specify/extensions/synthesis
uv run --with pydantic --with pyyaml python "$SYN/skill/scripts/synthesize_atlas.py" \
    --from . --work .synthesis-portal            # then re-run with --out site/ after reasoning
```

What changes (vs before this feature):

- **Source specs are read as features, not one bucket.** The source repo's `docs/specs/NNN-*` are
  ingested structure-aware — each a distinct feature — so a build repo's spec lands in the **same
  capability** as the source spec it derives from. Cross-tier melding actually happens.
- **No double-counting.** The narrative pass skips the `specs_dir` and `adr_dir` subtrees, so a spec
  isn't also read as prose.
- **Decisions and background know their place.** A decision a capability cites renders **inline** in
  that capability; uncited decisions gather in a **Decisions appendix**; free-form narrative becomes a
  short **Overview/Background** — none of them masquerade as capabilities. Everything is still in the
  hierarchical catalog.

What stays the same: the cross-tier signal (a build spec deriving from a source spec; a spec citing a
decision) — it's the same signal, it just now fires; the fail-closed gates; build/standalone repos;
and any ungoverned or non-docs-authority workspace (unchanged output).

You don't configure any of this — a governed source repo's declared `specs_dir`/`adr_dir` drive it.
