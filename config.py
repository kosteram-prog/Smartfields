"""Shared configuration. The organisers' data lives OUTSIDE the repository.

Set the environment variable FIELDGO_DATA_DIR to the folder holding the Parquet
extracts (output of `python -m engine.data`). Nothing from that folder is ever committed.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "FIELDGO_DATA_DIR"
ASSETS_DIR = Path(__file__).resolve().parent / "app" / "assets"


def get_data_dir() -> Path:
    """Return the data folder, or raise a clear error if it is missing."""
    raw = os.environ.get(ENV_VAR)
    if not raw:
        raise RuntimeError(
            f"Environment variable {ENV_VAR} is not set. Point it at the folder with the "
            f"FieldGo Parquet extracts, e.g. (PowerShell)  $env:{ENV_VAR} = 'E:\\fieldgo-data'"
        )
    path = Path(raw)
    if not path.is_dir():
        raise RuntimeError(f"{ENV_VAR} points to '{raw}', which is not an existing folder.")
    return path


def data_dir_or_none() -> Path | None:
    """Same as get_data_dir() but returns None instead of raising (used by tests / stub mode)."""
    try:
        return get_data_dir()
    except RuntimeError:
        return None


# Convenience constant: None when the variable is not set or the folder does not exist,
# so that importing config never crashes the stub-only skeleton. Real loaders call get_data_dir().
DATA_DIR: Path | None = data_dir_or_none()
