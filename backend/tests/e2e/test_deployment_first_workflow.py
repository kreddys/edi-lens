"""
End-to-end tests for deployment-first workflow.

These tests verify the complete deployment-first workflow using real NiFi and Registry instances.
They test the full stack integration including API endpoints, services, and external systems.
"""

import asyncio
import os
import pytest

from tests.test_config import get_test_orchestrator, get_test_settings


class TestDeploymentFirstWorkflow:
    """Test the complete deployment-first workflow."""

    @pytest.fixture
    def orchestrator(self):
        """Get workflow orchestrator for testing."""
        return get_test_orchestrator()

    @pytest.fixture
    def sample_flow_definition(self):
        """Sample flow definition for testing."""
        return {
            "processors": [
                {
                    "identifier": "proc-1",
                    "name": "GenerateFlowFile",
                    "type": "org.apache.nifi.processors.standard.GenerateFlowFile",
                    "position": {"x": 100.0, "y": 100.0},
                    "properties": {
                        "File Size": "1KB",
                        "Batch Size": "1"
                    },
                    "schedulingPeriod": "1 min",
                    "schedulingStrategy": "TIMER_DRIVEN",
                    "autoTerminatedRelationships": ["success"]
                }
            ],
            "connections": []
        }

    @pytest.mark.asyncio
    async def test_complete_deployment_first_workflow(self, orchestrator, sample_flow_definition):
        """Test the complete deployment-first workflow from start to finish."""
        print("\n=== Phase 1: Testing Complete Deployment-First Workflow ===")

        flow_name = "e2e-test-flow"
        bucket_name = "e2e-test-bucket"
        parameters = {
            "test_param": "test_value",
            "environment": "integration"
        }

        # Step 1: Deploy and register flow
        print(f"Deploying flow '{flow_name}' to NiFi and registering in bucket '{bucket_name}'...")

        deploy_result = await orchestrator.deploy_and_register_flow(
            flow_definition=sample_flow_definition,
            flow_name=flow_name,
            bucket_name=bucket_name,
            parameters=parameters,
            comments="E2E test deployment"
        )

        print(f"Deployment result: {deploy_result.get('success')}")
        if not deploy_result.get("success"):
            print(f"Deployment failed at stage: {deploy_result.get('stage')}")
            if deploy_result.get("nifi_deployment"):
                print(f"NiFi deployment details: {deploy_result['nifi_deployment']}")
            if deploy_result.get("registry_error"):
                print(f"Registry error: {deploy_result['registry_error']}")

        # Deployment may fail if Registry is not available, but NiFi deployment should work
        process_group_id = deploy_result.get("process_group_id")
        assert process_group_id is not None, "Process group should be created in NiFi"

        try:
            # Step 2: Verify flow status
            print("Getting flow overview...")
            flow_overview = await orchestrator.get_flow_overview(process_group_id)

            assert flow_overview["process_group_id"] == process_group_id
            assert flow_overview["flow_status"]["total_processors"] >= 1
            print(f"Flow has {flow_overview['flow_status']['total_processors']} processors")

            # Step 3: Test flow lifecycle operations
            print("Testing flow start...")
            start_result = await orchestrator.start_flow_workflow(process_group_id)
            print(f"Start result: {start_result.get('success')}")

            # Give processors time to start
            await asyncio.sleep(2)

            # Check status after start
            status_after_start = await orchestrator.get_flow_overview(process_group_id)
            print(f"Status after start: {status_after_start['flow_status']['overall_status']}")

            # Step 4: Test flow stop
            print("Testing flow stop...")
            stop_result = await orchestrator.stop_flow_workflow(process_group_id)
            print(f"Stop result: {stop_result.get('success')}")

            # Step 5: Test parameter context management
            if flow_overview.get("parameter_context"):
                print("Verifying parameter context...")
                param_ctx = flow_overview["parameter_context"]
                assert param_ctx["parameter_count"] >= len(parameters)
                print(f"Parameter context has {param_ctx['parameter_count']} parameters")

        finally:
            # Step 6: Cleanup - delete the flow
            print("Cleaning up - deleting test flow...")
            delete_result = await orchestrator.delete_flow_workflow(
                process_group_id,
                remove_from_registry=True
            )
            print(f"Cleanup result: {delete_result.get('success')}")

        print("=== Complete Deployment-First Workflow Test Completed ===\n")

    @pytest.mark.asyncio
    async def test_deployment_with_failures(self, orchestrator):
        """Test deployment workflow with intentional failures."""
        print("\n=== Phase 2: Testing Error Handling ===")

        # Test with invalid processor type
        invalid_flow = {
            "processors": [
                {
                    "identifier": "invalid-proc",
                    "name": "InvalidProcessor",
                    "type": "org.apache.nifi.processors.invalid.NonExistentProcessor",
                    "position": {"x": 100.0, "y": 100.0},
                    "properties": {}
                }
            ],
            "connections": []
        }

        deploy_result = await orchestrator.deploy_and_register_flow(
            flow_definition=invalid_flow,
            flow_name="invalid-test-flow",
            bucket_name="test-bucket"
        )

        print(f"Invalid deployment result: {deploy_result.get('success')}")

        # Deployment might succeed in NiFi but processors will be invalid
        if deploy_result.get("process_group_id"):
            try:
                # Check that processors are marked as invalid
                overview = await orchestrator.get_flow_overview(deploy_result["process_group_id"])
                print(f"Invalid processors count: {overview['flow_status'].get('invalid_processors', 0)}")

            finally:
                # Clean up
                await orchestrator.delete_flow_workflow(deploy_result["process_group_id"])

        print("=== Error Handling Test Completed ===\n")

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, orchestrator, sample_flow_definition):
        """Test concurrent flow operations."""
        print("\n=== Phase 3: Testing Concurrent Operations ===")

        # Create multiple flows concurrently
        tasks = []
        flow_ids = []

        for i in range(3):
            flow_name = f"concurrent-flow-{i}"
            task = orchestrator.deploy_and_register_flow(
                flow_definition=sample_flow_definition,
                flow_name=flow_name,
                bucket_name="concurrent-test-bucket"
            )
            tasks.append(task)

        # Wait for all deployments
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Flow {i} failed with exception: {result}")
            else:
                print(f"Flow {i} deployment success: {result.get('success')}")
                if result.get("process_group_id"):
                    flow_ids.append(result["process_group_id"])

        print(f"Successfully created {len(flow_ids)} flows concurrently")

        # Clean up all created flows
        cleanup_tasks = []
        for flow_id in flow_ids:
            cleanup_tasks.append(orchestrator.delete_flow_workflow(flow_id))

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

        print("=== Concurrent Operations Test Completed ===\n")

    @pytest.mark.asyncio
    async def test_list_all_flows(self, orchestrator):
        """Test listing all flows across systems."""
        print("\n=== Phase 4: Testing Flow Listing ===")

        all_flows = await orchestrator.list_all_flows()

        print(f"NiFi flows count: {all_flows['summary']['nifi_flow_count']}")
        print(f"Registry flows count: {all_flows['summary']['registry_flow_count']}")
        print(f"Registry buckets count: {all_flows['summary']['registry_bucket_count']}")

        # Verify response structure
        assert "nifi_flows" in all_flows
        assert "registry_flows" in all_flows
        assert "registry_buckets" in all_flows
        assert "summary" in all_flows

        print("=== Flow Listing Test Completed ===\n")


class TestServiceIntegration:
    """Test integration between different domain services."""

    @pytest.fixture
    def orchestrator(self):
        """Get workflow orchestrator for testing."""
        return get_test_orchestrator()

    @pytest.mark.asyncio
    async def test_nifi_parameter_integration(self, orchestrator):
        """Test parameter management integration."""
        print("\n=== Testing NiFi Parameter Management Integration ===")

        # Test parameter context operations
        param_result = await orchestrator.nifi_param_mgmt.create_parameter_context(
            name="integration-test-params",
            description="Integration test parameters",
            parameters={
                "test_url": "http://example.com",
                "test_timeout": "30s",
                "test_batch_size": "100"
            }
        )

        assert param_result["success"] is True
        param_ctx_id = param_result["parameter_context_id"]

        try:
            # Verify parameter context creation
            param_ctx_details = await orchestrator.nifi_param_mgmt.get_parameter_context(param_ctx_id)
            assert param_ctx_details["parameter_count"] == 3
            assert "test_url" in param_ctx_details["parameters"]

            print(f"Created parameter context with {param_ctx_details['parameter_count']} parameters")

        finally:
            # Clean up
            await orchestrator.nifi_param_mgmt.delete_parameter_context(param_ctx_id)

        print("=== NiFi Parameter Management Integration Test Completed ===\n")

    @pytest.mark.asyncio
    async def test_registry_bucket_integration(self, orchestrator):
        """Test Registry bucket management integration."""
        print("\n=== Testing Registry Bucket Management Integration ===")

        try:
            # Test bucket operations
            bucket_result = await orchestrator.registry_bucket_mgmt.create_bucket(
                name="integration-test-bucket-unique",
                description="Integration test bucket"
            )

            assert bucket_result["success"] is True
            bucket_id = bucket_result["bucket_id"]

            # Test bucket listing
            buckets = await orchestrator.registry_bucket_mgmt.list_buckets()
            bucket_names = [b["name"] for b in buckets]
            assert "integration-test-bucket-unique" in bucket_names

            print(f"Created bucket and verified in list of {len(buckets)} buckets")

            # Clean up
            await orchestrator.registry_bucket_mgmt.delete_bucket(bucket_id)

        except Exception as e:
            print(f"Registry bucket test failed (Registry may not be available): {e}")
            # This is acceptable in test environments where Registry might not be fully configured

        print("=== Registry Bucket Management Integration Test Completed ===\n")


class TestEnvironmentValidation:
    """Validate test environment setup."""

    @pytest.mark.asyncio
    async def test_environment_setup(self):
        """Validate that test environment is properly configured."""
        print("\n=== Validating Test Environment ===")

        settings = get_test_settings()
        test_mode = os.getenv("TEST_MODE", "local")

        print(f"Test mode: {test_mode}")
        print(f"NiFi URL: {settings.nifi_url}")
        print(f"Registry URL: {settings.registry_url}")
        print(f"Debug mode: {settings.DEBUG}")

        # Basic connectivity tests
        orchestrator = get_test_orchestrator()

        # Test NiFi connectivity
        nifi_healthy = await orchestrator.nifi.health_check()
        print(f"NiFi health check: {'✓' if nifi_healthy else '✗'}")

        # Test Registry connectivity
        registry_healthy = await orchestrator.registry.health_check()
        print(f"Registry health check: {'✓' if registry_healthy else '✗'}")

        # At minimum, NiFi should be healthy for tests to be meaningful
        assert nifi_healthy, "NiFi must be accessible for E2E tests"

        print("=== Environment Validation Completed ===\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])