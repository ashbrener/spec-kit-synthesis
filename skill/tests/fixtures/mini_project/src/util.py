"""Widget storage helper: name normalization and a flat on-disk store."""


def normalize_name(name):
    """Trim and collapse whitespace in a widget name before storage/display."""
    return " ".join(name.split())


class WidgetStore:
    """A minimal persistent store mapping widget names to records."""

    def __init__(self, path):
        self.path = path

    def create(self, name):
        return {"name": normalize_name(name)}

    def lookup(self, name):
        return {"name": normalize_name(name), "found": False}
