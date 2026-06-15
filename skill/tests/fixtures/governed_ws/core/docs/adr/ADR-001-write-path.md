# ADR-001: Durable single-writer write path

**Status**: Accepted

## Context

Records must be persisted exactly once (FR-001).

## Decision

Adopt a single-writer durable log for the write path.

## Consequences

Downstream build repos read this decision as CORE-ADR-001.
