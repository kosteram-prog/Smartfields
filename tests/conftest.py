"""Skip data-dependent tests when FIELDGO_DATA_DIR is not set (mark them with @pytest.mark.needs_data)."""
import os
from pathlib import Path

import pytest


def pytest_collection_modifyitems(config, items):
    folder = os.environ.get("FIELDGO_DATA_DIR")
    if folder and Path(folder).is_dir():
        return
    skip = pytest.mark.skip(reason="FIELDGO_DATA_DIR is not set (or not a folder)")
    for item in items:
        if "needs_data" in item.keywords:
            item.add_marker(skip)
