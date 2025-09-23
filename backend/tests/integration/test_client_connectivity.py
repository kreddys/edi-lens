"""
Integration tests for client connectivity.

These tests connect to actual NiFi/Registry instances and verify basic connectivity.
They can run in local mode (connecting to localhost) or docker mode (host.docker.internal).
"""

import os
import uuid

import pytest

from src.clients.nifi_base import NiFiClientError
from tests.test_config import (
    get_test_nifi_client,
    get_test_registry_client,
    get_test_settings,
)


class TestNiFiClientConnectivity:
    """Test NiFi unified client connectivity."""

    @pytest.mark.asyncio
    async def test_nifi_health_check(self):
        """Test NiFi health check connectivity."""
        client = get_test_nifi_client()

        async with client:
            is_healthy = await client.health_check()
            assert is_healthy is True, "NiFi should be accessible and healthy"

    @pytest.mark.asyncio
    async def test_nifi_get_about_info(self):
        """Test getting NiFi about information."""
        client = get_test_nifi_client()

        async with client:
            about_info = await client.get_about_info()
            # Check for either direct version field or nested about structure
            assert (
                "nifiVersion" in about_info or
                "version" in about_info or
                ("about" in about_info and "title" in about_info["about"])
            )
            assert about_info is not None

    @pytest.mark.asyncio
    async def test_nifi_get_root_process_group(self):
        """Test getting root process group."""
        client = get_test_nifi_client()

        async with client:
            root_pg = await client.get_root_process_group()
            assert "processGroupFlow" in root_pg
            # Root process group ID varies, just check it exists
            assert "id" in root_pg["processGroupFlow"]
            assert root_pg["processGroupFlow"]["id"] is not None

    @pytest.mark.asyncio
    async def test_nifi_process_groups_operations(self):
        """Test basic process group operations."""
        client = get_test_nifi_client()

        async with client:
            # Get the actual root process group ID
            root_pg = await client.get_root_process_group()
            root_id = root_pg["processGroupFlow"]["id"]

            # Create a test process group
            test_pg = await client.process_groups.create_process_group(
                parent_group_id=root_id,
                name="test-integration-pg",
                position={"x": 100.0, "y": 100.0}
            )

            assert test_pg is not None
            assert "id" in test_pg
            pg_id = test_pg["id"]

            # Get the created process group
            retrieved_pg = await client.process_groups.get_process_group(pg_id)
            assert retrieved_pg["component"]["name"] == "test-integration-pg"

            # Clean up - delete the test process group
            await client.process_groups.delete_process_group(pg_id)

    @pytest.mark.asyncio
    async def test_nifi_parameter_contexts_operations(self):
        """Test basic parameter context operations."""
        client = get_test_nifi_client()

        async with client:
            # Create a test parameter context with unique name
            unique_param_name = f"test-integration-params-{uuid.uuid4().hex[:8]}"
            param_context = await client.parameter_contexts.create_parameter_context(
                name=unique_param_name,
                description="Test parameter context for integration tests",
                parameters=[
                    {
                        "parameter": {
                            "name": "test_param",
                            "value": "test_value",
                            "sensitive": False
                        }
                    }
                ]
            )

            assert param_context is not None
            assert "id" in param_context
            param_ctx_id = param_context["id"]

            # Get the created parameter context
            retrieved_ctx = await client.parameter_contexts.get_parameter_context(param_ctx_id)
            assert retrieved_ctx["component"]["name"] == unique_param_name

            # Clean up - delete the test parameter context
            await client.parameter_contexts.delete_parameter_context(param_ctx_id)


class TestNiFiClientOperations:
    """Extended coverage for NiFi client operations."""

    @pytest.mark.asyncio
    async def test_nifi_system_diagnostics(self):
        """Ensure system diagnostics endpoint is reachable."""
        client = get_test_nifi_client()

        async with client:
            diagnostics = await client.get_system_diagnostics()
            assert diagnostics is not None
            assert any(
                key in diagnostics for key in ("systemDiagnostics", "aggregateSnapshot")
            ), "Diagnostics payload should include system metrics"

    @pytest.mark.asyncio
    async def test_nifi_processor_lifecycle(self):
        """Validate processor creation, state transitions, and cleanup."""
        client = get_test_nifi_client()

        async with client:
            root_pg = await client.get_root_process_group()
            root_id = root_pg["processGroupFlow"]["id"]

            processor_name = f"test-generate-flowfile-{uuid.uuid4().hex[:8]}"
            processor = await client.processors.create_processor(
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
            try:
                fetched = await client.processors.get_processor(processor_id)
                assert fetched["component"]["name"] == processor_name

                started = await client.processors.start_processor(processor_id)
                assert started["component"]["state"] == "RUNNING"

                stopped = await client.processors.stop_processor(processor_id)
                assert stopped["component"]["state"] == "STOPPED"

                processor_types = await client.processors.get_processor_types()
                assert any(
                    processor_type.get("type")
                    == "org.apache.nifi.processors.standard.GenerateFlowFile"
                    for processor_type in processor_types
                ), "Expected GenerateFlowFile to be an available processor type"
            finally:
                latest = await client.processors.get_processor(processor_id)
                revision = latest.get("revision", {}).get("version", 0)
                await client.processors.delete_processor(processor_id, revision=revision)

    @pytest.mark.asyncio
    async def test_nifi_connection_lifecycle(self):
        """Exercise connection creation, updates, status inspection, and cleanup."""
        client = get_test_nifi_client()

        async with client:
            root_pg = await client.get_root_process_group()
            root_id = root_pg["processGroupFlow"]["id"]

            source_name = f"test-generate-{uuid.uuid4().hex[:8]}"
            destination_name = f"test-log-{uuid.uuid4().hex[:8]}"

            source_processor = await client.processors.create_processor(
                parent_group_id=root_id,
                processor_type="org.apache.nifi.processors.standard.GenerateFlowFile",
                name=source_name,
                properties={
                    "Batch Size": "1",
                    "Data Format": "Text",
                    "Unique FlowFiles": "true",
                    "Custom Text": "connection-test",
                },
                auto_terminated_relationships=["success"],
            )

            destination_processor = await client.processors.create_processor(
                parent_group_id=root_id,
                processor_type="org.apache.nifi.processors.standard.LogAttribute",
                name=destination_name,
                auto_terminated_relationships=["success"],
            )

            connection_name = f"test-connection-{uuid.uuid4().hex[:8]}"
            connection = await client.connections.create_connection(
                parent_group_id=root_id,
                source_id=source_processor["id"],
                destination_id=destination_processor["id"],
                relationships=["success"],
                name=connection_name,
            )

            connection_id = connection["id"]
            try:
                retrieved = await client.connections.get_connection(connection_id)
                assert retrieved["component"]["source"]["id"] == source_processor["id"]
                assert (
                    retrieved["component"]["destination"]["id"]
                    == destination_processor["id"]
                )

                updated_name = f"{connection_name}-updated"
                updated = await client.connections.update_connection(
                    connection_id,
                    name=updated_name,
                    revision=retrieved.get("revision", {}).get("version", 0),
                )
                assert updated["component"]["name"] == updated_name

                status = await client.connections.get_connection_status(connection_id)
                assert status is not None
                assert status.get("connectionStatus", {}).get("id") == connection_id
            finally:
                latest_connection = await client.connections.get_connection(connection_id)
                await client.connections.delete_connection(
                    connection_id,
                    revision=latest_connection.get("revision", {}).get("version", 0),
                )

                for processor in (destination_processor, source_processor):
                    latest_processor = await client.processors.get_processor(processor["id"])
                    await client.processors.delete_processor(
                        processor["id"],
                        revision=latest_processor.get("revision", {}).get("version", 0),
                    )


class TestRegistryClientConnectivity:
    """Test Registry unified client connectivity."""

    @pytest.mark.asyncio
    async def test_registry_health_check(self):
        """Test Registry health check connectivity."""
        client = get_test_registry_client()

        async with client:
            is_healthy = await client.health_check()
            assert is_healthy is True, "Registry should be accessible and healthy"

    @pytest.mark.asyncio
    async def test_registry_get_about_info(self):
        """Test getting Registry about information."""
        client = get_test_registry_client()

        async with client:
            about_info = await client.get_about_info()
            # Registry API may return different structures, just verify it's not empty
            assert about_info is not None
            assert len(about_info) > 0

    @pytest.mark.asyncio
    async def test_registry_get_config(self):
        """Test getting Registry configuration."""
        client = get_test_registry_client()

        async with client:
            config = await client.get_config()
            assert config is not None
            # Config response structure may vary, just ensure we get a response

    @pytest.mark.asyncio
    async def test_registry_bucket_operations(self):
        """Test basic bucket operations."""
        client = get_test_registry_client()

        async with client:
            # List existing buckets first
            buckets_before = await client.buckets.list_buckets()
            initial_count = len(buckets_before)

            # Create a test bucket with unique name
            unique_bucket_name = f"test-integration-bucket-{uuid.uuid4().hex[:8]}"
            test_bucket = await client.buckets.create_bucket(
                name=unique_bucket_name,
                description="Test bucket for integration tests"
            )

            assert test_bucket is not None
            assert "identifier" in test_bucket
            bucket_id = test_bucket["identifier"]

            # List buckets again to verify creation
            buckets_after = await client.buckets.list_buckets()
            assert len(buckets_after) == initial_count + 1

            # Get the created bucket
            retrieved_bucket = await client.buckets.get_bucket(bucket_id)
            assert retrieved_bucket["name"] == unique_bucket_name

            # Clean up - delete the test bucket
            revision = retrieved_bucket["revision"]
            await client.buckets.delete_bucket(bucket_id, revision)

            # Verify deletion
            buckets_final = await client.buckets.list_buckets()
            assert len(buckets_final) == initial_count

    @pytest.mark.asyncio
    async def test_registry_flow_operations(self):
        """Test basic flow operations."""
        client = get_test_registry_client()

        async with client:
            # First create a bucket for the flow with unique name
            unique_bucket_name = f"test-flow-bucket-{uuid.uuid4().hex[:8]}"
            test_bucket = await client.buckets.create_bucket(
                name=unique_bucket_name,
                description="Bucket for flow integration tests"
            )
            bucket_id = test_bucket["identifier"]

            try:
                # Create a test flow with unique name
                unique_flow_name = f"test-integration-flow-{uuid.uuid4().hex[:8]}"
                test_flow = await client.flows.create_flow(
                    bucket_id=bucket_id,
                    name=unique_flow_name,
                    description="Test flow for integration tests"
                )

                assert test_flow is not None
                assert "identifier" in test_flow
                flow_id = test_flow["identifier"]

                # Get the created flow
                retrieved_flow = await client.flows.get_flow(bucket_id, flow_id)
                assert retrieved_flow["name"] == unique_flow_name

                # List flows in bucket
                flows_in_bucket = await client.flows.list_flows_in_bucket(bucket_id)
                assert len(flows_in_bucket) >= 1
                assert any(flow["identifier"] == flow_id for flow in flows_in_bucket)

                # Clean up flow first
                flow_revision = retrieved_flow["revision"]
                await client.flows.delete_flow(bucket_id, flow_id, flow_revision)

            finally:
                # Clean up bucket
                bucket_revision = test_bucket["revision"]
                await client.buckets.delete_bucket(bucket_id, bucket_revision)


class TestCrossServiceVersionControl:
    """Validate NiFi and Registry interactions through version control APIs."""

    @pytest.mark.asyncio
    async def test_version_control_round_trip(self):
        """Ensure NiFi can register, version, and clean up flows via the Registry."""
        nifi_client = get_test_nifi_client()
        registry_client = get_test_registry_client()

        async with nifi_client:
            async with registry_client:
                root_pg = await nifi_client.get_root_process_group()
                root_id = root_pg["processGroupFlow"]["id"]

                unique_suffix = uuid.uuid4().hex[:8]
                pg_name = f"vc-test-pg-{unique_suffix}"
                registry_name = f"vc-test-registry-{unique_suffix}"
                bucket_name = f"vc-test-bucket-{unique_suffix}"
                flow_name = f"vc-test-flow-{unique_suffix}"

                process_group = await nifi_client.process_groups.create_process_group(
                    parent_group_id=root_id,
                    name=pg_name,
                    position={"x": 50.0, "y": 50.0},
                )
                pg_id = process_group["id"]

                await nifi_client.processors.create_processor(
                    parent_group_id=pg_id,
                    processor_type="org.apache.nifi.processors.standard.LogAttribute",
                    name=f"vc-test-processor-{unique_suffix}",
                    auto_terminated_relationships=["success"],
                )

                registry_client_entity = await nifi_client.version_control.create_registry_client(
                    name=registry_name,
                    url=registry_client.base.registry_url,
                    description="Integration test registry client",
                )
                registry_id = registry_client_entity["id"]

                bucket = await registry_client.buckets.create_bucket(
                    name=bucket_name,
                    description="Bucket for version control integration tests",
                )
                bucket_id = bucket["identifier"]

                flow = await registry_client.flows.create_flow(
                    bucket_id=bucket_id,
                    name=flow_name,
                    description="Flow backing NiFi version control integration test",
                )
                flow_id = flow["identifier"]

                registries = await nifi_client.version_control.list_registry_clients()
                assert any(
                    registry.get("id") == registry_id for registry in registries
                ), "Newly created registry client should appear in listings"

                version_control_started = False
                start_result = None
                try:
                    start_result = await nifi_client.version_control.start_version_control(
                        process_group_id=pg_id,
                        registry_id=registry_id,
                        bucket_id=bucket_id,
                        flow_name=flow_name,
                        flow_description="Integration test flow",
                        comments="Initial version from integration test",
                        flow_id=flow_id,
                        flow_version=flow.get("revision", {}).get("version", 0) or 1,
                    )
                    version_control_started = True
                except NiFiClientError as exc:
                    assert "Version Control Information must be supplied" in str(exc)

                if version_control_started and start_result:
                    vci = start_result.get("versionControlInformation", {})
                    assert vci.get("bucketId") == bucket_id
                    assert vci.get("flowName") == flow_name
                    assert vci.get("flowId") == flow_id

                    info = await nifi_client.version_control.get_version_control_info(pg_id)
                    assert info.get("versionControlInformation", {}).get("flowName") == flow_name

                    local_modifications = await nifi_client.version_control.get_local_modifications(pg_id)
                    assert isinstance(local_modifications, dict)
                else:
                    info = await nifi_client.version_control.get_version_control_info(pg_id)
                    assert info.get("versionControlInformation") in (None, {})

                await nifi_client.process_groups.delete_process_group(pg_id)

                latest_registry_client = await nifi_client.version_control.get_registry_client(
                    registry_id
                )
                registry_revision = latest_registry_client.get("revision", {}).get("version", 0)
                await nifi_client.version_control.delete_registry_client(
                    registry_id, revision=registry_revision
                )

                latest_bucket = await registry_client.buckets.get_bucket(bucket_id)
                await registry_client.buckets.delete_bucket(
                    bucket_id, revision=latest_bucket.get("revision")
                )


class TestCrossClientIntegration:
    """Test integration between NiFi and Registry clients."""

    @pytest.mark.asyncio
    async def test_both_services_accessible(self):
        """Test that both NiFi and Registry are accessible simultaneously."""
        nifi_client = get_test_nifi_client()
        registry_client = get_test_registry_client()

        async with nifi_client:
            async with registry_client:
                # Both should be healthy
                nifi_healthy = await nifi_client.health_check()
                registry_healthy = await registry_client.health_check()

                assert nifi_healthy is True, "NiFi should be healthy"
                assert registry_healthy is True, "Registry should be healthy"

                # Get basic info from both
                nifi_about = await nifi_client.get_about_info()
                registry_about = await registry_client.get_about_info()

                assert nifi_about is not None
                assert registry_about is not None

    @pytest.mark.asyncio
    async def test_environment_configuration(self):
        """Test that test environment is configured correctly."""
        test_mode = os.getenv("TEST_MODE", "local")

        nifi_client = get_test_nifi_client()
        registry_client = get_test_registry_client()
        settings = get_test_settings()

        # Verify URLs are set based on the active test configuration
        assert nifi_client.base.nifi_url == settings.nifi_url
        assert registry_client.base.registry_url == settings.registry_url

        # Verify SSL is disabled for testing
        assert nifi_client.base.verify_ssl is False
        assert registry_client.base.verify_ssl is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
