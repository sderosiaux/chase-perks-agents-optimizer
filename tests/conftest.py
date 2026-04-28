"""Pytest fixtures: isolate per-test data dir."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import pytest

from chase_agent import config

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CHASE_AGENT_DATA_DIR", str(tmp_path))
    importlib.reload(config)
    return tmp_path
