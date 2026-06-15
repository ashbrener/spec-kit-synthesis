# Reader conformance contract (what synthesis guarantees as a reader)

Synthesis conforms to the governance contracts **as a documented format**, in code, with no runtime
dependency on the extension. The guarantees:

1. **Relations** — synthesis's `LinkRel` values equal the `relations` keys in the vendored
   `vocabulary.json` (enforced by `test_contract_conformance.py`). Mapping of legacy edges:
   `derives_from`→`derived_from`, docs↔spec→`references`, code→spec→`implements`, `cites` added.
2. **ADR identifiers** — accepts bare `^ADR-\d{3,}$` (qualified by the owning repo's namespace) and
   qualified `^[A-Z][A-Z0-9]*-ADR-\d{3,}$`; bare ids never cross a repo boundary.
3. **Domain manifest** — when `.spec-arch-domain.yml` is present it is validated against the vendored
   `domain.schema.json`; if valid it is the source of truth for structural topology; if invalid it
   is reported and the reader falls back to its own record.
4. **Precedence** — manifest wins on structural fields; `synthesis.workspace.json` supplies
   presentation always and topology fallback when no manifest is present.
5. **Evidence** — every cross-repo fact is graded `declared` / `identifier` / `prose`.
6. **Safety** — read-only on consumer repos; ungoverned projects render unchanged; no real consumer
   names in source/docs/tests.

Vendored conformance targets: `skill/scripts/vendor/vocabulary.json` (@0.2.0),
`skill/scripts/vendor/domain.schema.json`. Update them only by re-pinning to a newer published tag.
