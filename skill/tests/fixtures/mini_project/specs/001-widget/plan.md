# Plan: Widget

## Summary

The widget is implemented as a small shell entry point that delegates name
validation and storage to a Python helper. Creation and lookup are the two
operations; both run synchronously and write to a flat on-disk store.
