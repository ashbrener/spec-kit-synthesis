# Core — write path specification

The core service owns the canonical write path.

- **FR-001**: The system MUST persist each record exactly once.
- **FR-002**: The system MUST expose the persisted record by its stable id.

See ADR-001 for the durability decision behind FR-001.
