"""
Integration tests for client connectivity.

These tests connect to actual NiFi/Registry instances and verify basic connectivity.
They can run in local mode (connecting to localhost) or docker mode (host.docker.internal).
"""

import os
import pytest
import uuid

from tests.test_config import get_test_nifi_client, get_test_registry_client


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

        # Verify URLs are set correctly based on test mode
        if test_mode == "local":
            assert "localhost" in nifi_client.base.nifi_url
            assert "localhost" in registry_client.base.registry_url
        else:
            assert "host.docker.internal" in nifi_client.base.nifi_url
            assert "host.docker.internal" in registry_client.base.registry_url

        # Verify SSL is disabled for testing
        assert nifi_client.base.verify_ssl is False
        assert registry_client.base.verify_ssl is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])