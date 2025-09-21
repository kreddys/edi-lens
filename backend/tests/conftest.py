"""Pytest configuration for test suite markers and shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Automatically tag tests based on their location."""

    for item in items:
        path = Path(item.fspath)
        parts = set(path.parts)
        if "unit" in parts:
            item.add_marker("unit")
        if "integration" in parts:
            item.add_marker("integration")
        if "e2e" in parts:
            item.add_marker("e2e")
