"""Web handler implementing the core write path (FR-101)."""


def write(command):
    # FR-101: every write goes through this single command handler.
    return command.apply()
