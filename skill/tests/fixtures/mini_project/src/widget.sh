#!/usr/bin/env bash
# Tiny widget entry point: create and look up widgets by name.

widget_create() {
  local name="$1"
  python3 "$(dirname "$0")/util.py" create "$name"
}

widget_lookup() {
  local name="$1"
  python3 "$(dirname "$0")/util.py" lookup "$name"
}
