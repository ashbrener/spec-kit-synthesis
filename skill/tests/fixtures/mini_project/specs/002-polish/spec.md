# Feature: Polish

**Status**: Draft

## Overview

Polish is a follow-up feature that refines how widgets are presented back to the
user. It does not change how widgets are created or stored; it only improves the
formatting of names and the messages shown when a lookup fails.

## Requirements

- **FR-010**: The system SHOULD trim and normalize whitespace in a widget name before display.
- **FR-011**: The system SHOULD show a clear, friendly message when a requested widget is not found.
