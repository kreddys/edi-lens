"""Shared fixtures for backend unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_nifi_client() -> MagicMock:
    """Return a NiFi client double with the interfaces exercised in unit tests."""

    client = MagicMock(name="NiFiUnifiedClientMock")
    client.process_groups = MagicMock(name="process_groups")
    client.processors = MagicMock(name="processors")
    client.connections = MagicMock(name="connections")
    client.parameter_contexts = MagicMock(name="parameter_contexts")
    client.version_control = MagicMock(name="version_control")
    return client


@pytest.fixture
def mock_registry_client() -> MagicMock:
    """Return a Registry client double with the interfaces exercised in unit tests."""

    client = MagicMock(name="RegistryUnifiedClientMock")
    client.buckets = MagicMock(name="buckets")
    client.flows = MagicMock(name="flows")
    client.flow_versions = MagicMock(name="flow_versions")
    client.items = MagicMock(name="items")
    return client
