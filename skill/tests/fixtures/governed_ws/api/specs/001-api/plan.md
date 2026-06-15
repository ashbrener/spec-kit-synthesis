# API — implementation plan

The API derives from the core write path (FR-001) and exposes it over HTTP.

It implements the durability guarantee decided in CORE-ADR-001, citing it as the authority for
write acknowledgement semantics.

- Derived from the core specification (FR-001).
- Cites CORE-ADR-001 for the durability contract.
