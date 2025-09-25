"""Integration smoke tests covering NiFi and Registry connectivity."""

from __future__ import annotations

import uuid

import pytest

from src.clients.nifi_base import NiFiClientError
from src.clients.registry_base import RegistryClientError


class TestNiFiClientConnectivity:
    """Validate the NiFi client against a running NiFi instance."""

    @pytest.mark.asyncio
    async def test_nifi_health_check(self, nifi_client) -> None:
        """Basic health probe should succeed."""

        is_healthy = await nifi_client.health_check()
        assert is_healthy is True, "NiFi should be accessible and healthy"

    @pytest.mark.asyncio
    async def test_nifi_get_about_info(self, nifi_client) -> None:
        """Fetch basic metadata from NiFi."""

        about_info = await nifi_client.get_about_info()
        assert (
            "nifiVersion" in about_info
            or "version" in about_info
            or ("about" in about_info and "title" in about_info["about"])
        )

    @pytest.mark.asyncio
    async def test_nifi_get_root_process_group(self, nifi_client) -> None:
        """Ensure the root process group can be retrieved."""

        root_pg = await nifi_client.get_root_process_group()
        assert "processGroupFlow" in root_pg
        assert "id" in root_pg["processGroupFlow"]

    @pytest.mark.asyncio
    async def test_nifi_process_groups_operations(self, nifi_client) -> None:
        """Create and delete a temporary process group."""

        root_pg = await nifi_client.get_root_process_group()
        root_id = root_pg["processGroupFlow"]["id"]

        test_pg = await nifi_client.process_groups.create_process_group(
            parent_group_id=root_id,
            name="test-integration-pg",
            position={"x": 100.0, "y": 100.0},
        )
        pg_id = test_pg["id"]

        retrieved_pg = await nifi_client.process_groups.get_process_group(pg_id)
        assert retrieved_pg["component"]["name"] == "test-integration-pg"

        await nifi_client.process_groups.delete_process_group(pg_id)

    @pytest.mark.asyncio
    async def test_nifi_parameter_contexts_operations(self, nifi_client) -> None:
        """Create and clean up a parameter context."""

        unique_param_name = f"test-integration-params-{uuid.uuid4().hex[:8]}"
        param_context = await nifi_client.parameter_contexts.create_parameter_context(
            name=unique_param_name,
            description="Test parameter context for integration tests",
            parameters=[
                {
                    "parameter": {
                        "name": "test_param",
                        "value": "test_value",
                        "sensitive": False,
                    }
                }
            ],
        )

        param_ctx_id = param_context["id"]
        retrieved_ctx = await nifi_client.parameter_contexts.get_parameter_context(param_ctx_id)
        assert retrieved_ctx["component"]["name"] == unique_param_name

        await nifi_client.parameter_contexts.delete_parameter_context(param_ctx_id)


class TestNiFiClientOperations:
    """Additional NiFi endpoints surfaced through the unified client."""

    @pytest.mark.asyncio
    async def test_nifi_system_diagnostics(self, nifi_client) -> None:
        """Diagnostics endpoint should return telemetry."""

        diagnostics = await nifi_client.get_system_diagnostics()
        assert diagnostics is not None
        assert any(
            key in diagnostics for key in ("systemDiagnostics", "aggregateSnapshot")
        )


class TestNiFiErrorResponses:
    """Error scenarios should include actionable detail."""

    @pytest.mark.asyncio
    async def test_create_process_group_with_invalid_parent(self, nifi_client) -> None:
        """An invalid parent identifier should produce a descriptive exception."""

        invalid_parent_id = "not-a-real-parent-group"
        with pytest.raises(NiFiClientError) as exc_info:
            await nifi_client.process_groups.create_process_group(
                parent_group_id=invalid_parent_id,
                name="invalid-parent-test",
                position={"x": 0.0, "y": 0.0},
            )

        message = str(exc_info.value)
        assert "NiFi API error" in message
        assert invalid_parent_id in message
        assert "log" not in message.lower()

    @pytest.mark.asyncio
    async def test_nifi_processor_lifecycle(self, nifi_client) -> None:
        """Create, run, stop, and delete a processor to cover lifecycle APIs."""

        root_pg = await nifi_client.get_root_process_group()
        root_id = root_pg["processGroupFlow"]["id"]

        processor_name = f"test-generate-flowfile-{uuid.uuid4().hex[:8]}"
        processor = await nifi_client.processors.create_processor(
            parent_group_id=root_id,
            processor_type="org.apache.nifi.processors.standard.GenerateFlowFile",
            name=processor_name,
            properties={
                "Batch Size": "1",
                "Data Format": "Text",
                "Unique FlowFiles": "true",
                "Custom Text": "integration-test",
            },
            auto_terminated_relationships=["success"],
        )

        processor_id = processor["id"]
        revision = processor.get("revision", {}).get("version", 0)

        try:
            fetched = await nifi_client.processors.get_processor(processor_id)
            revision = fetched.get("revision", {}).get("version", revision)
            assert fetched["component"]["name"] == processor_name

            started = await nifi_client.processors.start_processor(processor_id)
            revision = started.get("revision", {}).get("version", revision)
            assert started["component"]["state"] == "RUNNING"

            stopped = await nifi_client.processors.stop_processor(processor_id)
            revision = stopped.get("revision", {}).get("version", revision)
            assert stopped["component"]["state"] == "STOPPED"

            processor_types = await nifi_client.processors.get_processor_types()
            assert processor_types, "Expected processor type metadata from NiFi"
        finally:
            try:
                await nifi_client.processors.delete_processor(processor_id, revision=revision)
            except Exception:
                fetched = await nifi_client.processors.get_processor(processor_id)
                final_revision = fetched.get("revision", {}).get("version", revision)
                await nifi_client.processors.delete_processor(processor_id, revision=final_revision)


class TestRegistryClientConnectivity:
    """Validate basic interactions with NiFi Registry."""

    @pytest.mark.asyncio
    async def test_registry_buckets_round_trip(self, registry_client) -> None:
        """Create and fetch a bucket to validate connectivity."""

        bucket_name = f"integration-bucket-{uuid.uuid4().hex[:8]}"
        bucket = await registry_client.buckets.create_bucket(
            name=bucket_name,
            description="Integration test bucket",
        )
        bucket_id = bucket["identifier"]

        try:
            fetched = await registry_client.buckets.get_bucket(bucket_id)
            assert fetched["identifier"] == bucket_id
            assert fetched["name"] == bucket_name
        finally:
            await registry_client.buckets.delete_bucket(bucket_id, bucket.get("revision"))

    @pytest.mark.asyncio
    async def test_registry_error_propagation(self, registry_client) -> None:
        """Bad bucket IDs should raise rich client exceptions."""

        with pytest.raises(RegistryClientError):
            await registry_client.buckets.get_bucket("not-a-real-bucket")
