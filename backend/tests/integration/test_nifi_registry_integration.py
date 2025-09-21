"""Integration tests that exercise the live NiFi and Registry services."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

import aiohttp
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.clients.nifi_client import NiFiClient, NiFiClientError
from src.clients.registry_client import RegistryClient, RegistryClientError
from src.core.config import get_settings

pytestmark = pytest.mark.integration

RETRYABLE_HINTS = (
    "cannot connect",
    "connection refused",
    "service unavailable",
    "operation not permitted",
    "temporarily unavailable",
)


def _settings():
    """Return cached application settings."""

    return get_settings()


def _should_skip(message: str) -> bool:
    lowered = message.lower()
    return any(hint in lowered for hint in RETRYABLE_HINTS)


async def _await_service(
    call_factory: Callable[[], Awaitable[Any]],
    service_name: str,
    retries: int = 5,
    delay: float = 3.0,
) -> Any:
    """Run the coroutine factory with retry/skip semantics."""

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return await call_factory()
        except (aiohttp.ClientConnectorError, asyncio.TimeoutError) as exc:  # pragma: no cover - integration safety
            last_exc = exc
        except (NiFiClientError, RegistryClientError) as exc:
            last_exc = exc
            if not _should_skip(str(exc)):
                raise

        if attempt < retries - 1:
            await asyncio.sleep(delay)
        else:
            pytest.skip(f"{service_name} is not reachable: {last_exc}")


def _assert_auth_failure(message: str) -> None:
    if _should_skip(message):
        pytest.skip(f"Service not reachable: {message}")

    lowered = message.lower()
    assert (
        "unauthorized" in lowered
        or "access is denied" in lowered
        or "401" in message
        or "403" in message
        or "bad credentials" in lowered
    )


@pytest.mark.asyncio
async def test_nifi_allows_valid_credentials():
    """NiFi should respond to API requests when valid credentials are provided."""

    settings = _settings()
    async with NiFiClient(
        settings.NIFI_URL,
        settings.NIFI_USERNAME,
        settings.NIFI_PASSWORD,
        verify_ssl=settings.VERIFY_SSL,
    ) as client:
        root_pg = await _await_service(client.get_root_process_group, "NiFi")
        assert isinstance(root_pg, dict)
        assert root_pg.get("processGroupFlow", {}).get("id") == "root"


@pytest.mark.asyncio
async def test_nifi_rejects_invalid_credentials():
    """NiFi must reject invalid credentials with an authorization error."""

    settings = _settings()
    async with NiFiClient(
        settings.NIFI_URL,
        username="wrong-user",
        password="wrong-pass",
        verify_ssl=settings.VERIFY_SSL,
    ) as client:
        with pytest.raises(NiFiClientError) as exc:
            await client.get_root_process_group()

        _assert_auth_failure(str(exc.value))


@pytest.mark.asyncio
async def test_registry_allows_access_with_default_config():
    """Registry should serve configuration details with the provided credentials/token."""

    settings = _settings()
    async with RegistryClient(
        settings.NIFI_REGISTRY_URL,
        settings.NIFI_REGISTRY_AUTH_TOKEN,
        verify_ssl=settings.VERIFY_SSL,
    ) as client:
        info = await _await_service(client.get_registry_info, "NiFi Registry")
        assert isinstance(info, dict)
        assert "nifiRegistryId" in info or "registryId" in info


@pytest.mark.asyncio
async def test_registry_rejects_invalid_token():
    """Registry must reject invalid authentication tokens."""

    settings = _settings()
    async with RegistryClient(
        settings.NIFI_REGISTRY_URL,
        auth_token="bogus-token",
        verify_ssl=settings.VERIFY_SSL,
    ) as client:
        with pytest.raises(RegistryClientError) as exc:
            await client.list_buckets()

        _assert_auth_failure(str(exc.value))
