# ADR-001: Single write path

## Status

Accepted

## Context

Multiple call sites mutated state directly, which made invariants hard to enforce.

## Decision

All writes go through one command handler. This is decision ADR-001.
