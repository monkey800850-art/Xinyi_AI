from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(config, items):
    for item in items:
        marker_names = {m.name for m in item.iter_markers()}
        if marker_names.intersection({"unit", "integration", "e2e"}):
            continue

        filename = Path(str(item.fspath)).name.lower()
        if filename.startswith("test_step"):
            item.add_marker(pytest.mark.e2e)
        elif filename.endswith("_unit.py") or filename.startswith("test_sec02_"):
            item.add_marker(pytest.mark.unit)
        else:
            item.add_marker(pytest.mark.integration)
