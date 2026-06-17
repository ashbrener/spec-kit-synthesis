# Quickstart — declared citations now meld

Nothing changes in how you invoke the atlas. What changes is that the **declared** citations in your
specs now produce cross-tier edges directly.

In a governed build repo, a feature declares its citations in front-matter:

```markdown
---
# specs/007-auth/spec.md
derived_from: [docs:001-auth]        # <source-member-id>:<spec-feature-id> (cross-repo)
---
# Authentication API
…
```

```markdown
---
# specs/007-auth/plan.md
cites: [CORE-ADR-001]                  # fully-qualified <source-NS>-ADR-NNN (cross-repo)
---
# Plan
…
```

Now `synthesize_atlas` (link-discovery) reads those slots and emits:

- a **`derived_from`** edge from the build spec to the source feature `docs:001-auth` — **even if the
  source spec's body never mentions `001-auth`** (previously this produced no edge), and
- a **`cites`** edge to `CORE-ADR-001`,

both graded **`declared`** (the highest trust tier). So the build feature and the source feature land
in the **same capability**, and the cited decision attaches — the meld lights up from the governed
declaration, not from prose coincidence.

Notes:
- The slot key names default to `derived_from` / `cites` but follow a repo's `citation_keys` config if
  set.
- A bare value (`derived_from: [001-auth]`, `cites: [ADR-001]`) is intra-repo (the citing repo's own
  feature / namespace).
- A citation whose target isn't in the workspace (e.g. an optional repo not checked out) produces no
  edge and is reported — never fabricated.
- A workspace whose specs declare no slots renders exactly as before.
