# Vendored governance contracts (pinned)

`vocabulary.json` (@0.3.0 — adds the `citation_slots` block, ARCH-ADR-000 Amendment 2) and
`domain.schema.json` are verbatim copies of the published
spec-kit-arch-governance contracts (`docs/adr/`), pinned here so atlas conforms **in code**
with no runtime dependency on the extension. The drift guard (`test_contract_conformance.py`)
fails the build if the reader's enums diverge. Update only by re-pinning to a newer published tag.
