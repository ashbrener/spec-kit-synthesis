# Feature: Widget

**Status**: Draft

## Overview

The widget is the primary unit of work in the system. A user creates a widget,
gives it a name, and the system stores it so it can be retrieved later. The
widget exists to give the rest of the product a small, well-defined thing to
build the workflow around.

## Requirements

- **FR-001**: The system MUST let a user create a widget with a human-readable name.
- **FR-002**: The system MUST persist each widget so it survives a restart and can be looked up by name.
