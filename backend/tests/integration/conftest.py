"""Shared fixtures for backend integration tests."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest

from src.services.workflow_orchestrator import WorkflowOrchestrator
from tests.test_config import (
    get_test_nifi_client,
    get_test_registry_client,
)


@pytest.fixture(scope="module")
def event_loop() -> AsyncIterator[asyncio.AbstractEventLoop]:
    """Provide a dedicated event loop for module-scoped async fixtures."""

    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(scope="module")
async def nifi_client():
    """Yield a configured NiFi client for integration scenarios."""

    client = get_test_nifi_client()
    async with client:
        yield client


@pytest.fixture(scope="module")
async def registry_client():
    """Yield a configured Registry client for integration scenarios."""

    client = get_test_registry_client()
    async with client:
        yield client


@pytest.fixture(scope="module")
def orchestrator(nifi_client, registry_client) -> WorkflowOrchestrator:
    """Return an orchestrator wired to the real clients."""

    return WorkflowOrchestrator(nifi_client, registry_client)
