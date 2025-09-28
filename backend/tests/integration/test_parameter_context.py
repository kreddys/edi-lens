"""
Integration tests for parameter context functionality.
Tests the pure parameter context approach (Option 1) implementation.
"""
import pytest
import time
from typing import Dict, Any

from src.services.workflow_orchestrator import WorkflowOrchestrator
from src.clients.nifi_unified import NiFiUnifiedClient
from tests.test_config import get_test_nifi_client, get_test_registry_client


@pytest.fixture
async def nifi_client():
    """NiFi client for integration tests."""
    client = get_test_nifi_client()
    async with client:
        yield client


@pytest.fixture
async def registry_client():
    """Registry client for integration tests."""
    client = get_test_registry_client()
    async with client:
        yield client


@pytest.fixture
async def workflow_orchestrator(nifi_client, registry_client):
    """Workflow orchestrator for integration tests."""
    return WorkflowOrchestrator(nifi_client, registry_client)


class TestParameterContextIntegration:
    """Test parameter context functionality with NiFi integration."""

    @pytest.fixture
    def test_flow_definition(self) -> Dict[str, Any]:
        """Test flow definition with parameter references."""
        return {
            "name": "Parameter Context Test Flow",
            "description": "Test flow for parameter context functionality",
            "processors": [
                {
                    "name": "GenerateFlowFile_Test",
                    "type": "org.apache.nifi.processors.standard.GenerateFlowFile",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "schedulingPeriod": "30 sec",
                        "schedulingStrategy": "TIMER_DRIVEN",
                        "autoTerminatedRelationships": ["success"],  # Auto-terminate to avoid connection requirements
                        "properties": {
                            "Batch Size": "#{batch_size}",  # Parameter reference
                            "Custom Text": "Input: #{input_directory}, Output: #{output_directory}",  # Parameter references
                            "Data Format": "Text"
                        }
                    }
                }
            ],
            "connections": [],  # No connections needed for this test
            "process_groups": []
        }

    @pytest.fixture
    def test_parameters(self) -> Dict[str, Any]:
        """Test parameters with metadata."""
        return {
            "input_directory": {
                "value": "/tmp/test_input",
                "description": "Directory to monitor for input files",
                "sensitive": False
            },
            "output_directory": {
                "value": "/tmp/test_output", 
                "description": "Directory where processed files are written",
                "sensitive": False
            },
            "batch_size": {
                "value": "5",
                "description": "Number of files to process in each batch",
                "sensitive": False
            }
        }

    @pytest.fixture
    def simple_parameters(self) -> Dict[str, str]:
        """Simple parameters as key-value pairs (like from UI)."""
        return {
            "input_directory": "/tmp/test_input",
            "output_directory": "/tmp/test_output",
            "batch_size": "5"
        }

    @pytest.mark.integration
    async def test_parameter_context_creation_and_linking(
        self, 
        workflow_orchestrator: WorkflowOrchestrator,
        nifi_client: NiFiUnifiedClient,
        test_flow_definition: Dict[str, Any],
        test_parameters: Dict[str, Any]
    ):
        """Test that parameter context is created and linked to process group."""
        flow_name = f"param_test_{int(time.time())}"
        
        # Deploy flow with parameters
        result = await workflow_orchestrator.deploy_and_register_flow(
            flow_definition=test_flow_definition,
            flow_name=flow_name,
            bucket_name="test-bucket",
            parameters=test_parameters,
            comments="Parameter context integration test"
        )
        
        assert result.get("success"), f"Flow deployment failed: {result}"
        
        process_group_id = result.get("process_group_id")
        parameter_context_id = result.get("parameter_context_id")
        
        assert process_group_id, "Process group ID not returned"
        assert parameter_context_id, "Parameter context ID not returned"
        
        try:
            # Verify parameter context exists
            param_context = await nifi_client.parameter_contexts.get_parameter_context(parameter_context_id)
            assert param_context, "Parameter context not found"
            
            # Verify parameter context has correct parameters
            context_component = param_context.get('component', {})
            parameters_list = context_component.get('parameters', [])
            
            assert len(parameters_list) == len(test_parameters), f"Expected {len(test_parameters)} parameters, got {len(parameters_list)}"
            
            # Check each parameter
            param_names = {param.get('parameter', {}).get('name') for param in parameters_list}
            expected_names = set(test_parameters.keys())
            assert param_names == expected_names, f"Parameter names mismatch. Expected: {expected_names}, Got: {param_names}"
            
            # Verify process group is linked to parameter context
            process_group = await nifi_client.process_groups.get_process_group(process_group_id)
            pg_param_context = process_group.get('component', {}).get('parameterContext')
            
            assert pg_param_context, "Process group not linked to any parameter context"
            assert pg_param_context.get('id') == parameter_context_id, "Process group linked to wrong parameter context"
            
        finally:
            # Cleanup
            await nifi_client.process_groups.delete_process_group(process_group_id)

    @pytest.mark.integration
    async def test_parameter_references_preserved(
        self,
        workflow_orchestrator: WorkflowOrchestrator,
        nifi_client: NiFiUnifiedClient,
        test_flow_definition: Dict[str, Any],
        simple_parameters: Dict[str, str]
    ):
        """Test that parameter references are preserved in processor properties (not substituted)."""
        flow_name = f"param_ref_test_{int(time.time())}"
        
        # Deploy flow with simple parameters
        result = await workflow_orchestrator.deploy_and_register_flow(
            flow_definition=test_flow_definition,
            flow_name=flow_name,
            bucket_name="test-bucket",
            parameters=simple_parameters,
            comments="Parameter reference preservation test"
        )
        
        assert result.get("success"), f"Flow deployment failed: {result}"
        process_group_id = result.get("process_group_id")
        
        try:
            # Get processors in the process group
            processors = await nifi_client.process_groups.get_processors(process_group_id)
            
            assert len(processors) >= 1, "Expected at least 1 processor"
            
            # Check each processor for parameter references
            for processor in processors:
                proc_name = processor.get('component', {}).get('name')
                properties = processor.get('component', {}).get('config', {}).get('properties', {})
                
                if proc_name == "GenerateFlowFile_Test":
                    batch_size = properties.get("Batch Size")
                    custom_text = properties.get("Custom Text")
                    
                    assert batch_size == "#{batch_size}", f"Batch Size should contain parameter reference, got: {batch_size}"
                    assert "#{input_directory}" in custom_text and "#{output_directory}" in custom_text, \
                        f"Custom Text should contain parameter references, got: {custom_text}"
                    
            # Ensure no parameter values were directly substituted
            for processor in processors:
                properties = processor.get('component', {}).get('config', {}).get('properties', {})
                for prop_name, prop_value in properties.items():
                    if prop_value:
                        # Check that actual parameter values are not directly embedded (unless they contain parameter references)
                        for param_value in simple_parameters.values():
                            assert param_value not in str(prop_value) or "#{" in str(prop_value), \
                                f"Parameter value '{param_value}' was directly substituted in {prop_name} instead of using parameter reference"
                                
        finally:
            # Cleanup
            await nifi_client.process_groups.delete_process_group(process_group_id)

    @pytest.mark.integration
    async def test_parameter_context_with_metadata(
        self,
        workflow_orchestrator: WorkflowOrchestrator,
        nifi_client: NiFiUnifiedClient,
        test_flow_definition: Dict[str, Any],
        test_parameters: Dict[str, Any]
    ):
        """Test parameter context creation with parameter metadata (description, sensitivity)."""
        flow_name = f"param_metadata_test_{int(time.time())}"
        
        result = await workflow_orchestrator.deploy_and_register_flow(
            flow_definition=test_flow_definition,
            flow_name=flow_name,
            bucket_name="test-bucket",
            parameters=test_parameters,
            comments="Parameter metadata test"
        )
        
        assert result.get("success"), f"Flow deployment failed: {result}"
        parameter_context_id = result.get("parameter_context_id")
        process_group_id = result.get("process_group_id")
        
        try:
            # Verify parameter context has metadata
            param_context = await nifi_client.parameter_contexts.get_parameter_context(parameter_context_id)
            parameters_list = param_context.get('component', {}).get('parameters', [])
            
            # Create a map for easy lookup
            param_map = {
                param.get('parameter', {}).get('name'): param.get('parameter', {})
                for param in parameters_list
            }
            
            # Verify each parameter has correct metadata
            for param_name, expected_param in test_parameters.items():
                actual_param = param_map.get(param_name)
                assert actual_param, f"Parameter {param_name} not found in context"
                
                expected_value = expected_param.get("value")
                expected_description = expected_param.get("description")
                expected_sensitive = expected_param.get("sensitive", False)
                
                assert actual_param.get('value') == expected_value, \
                    f"Parameter {param_name} value mismatch. Expected: {expected_value}, Got: {actual_param.get('value')}"
                    
                assert actual_param.get('description') == expected_description, \
                    f"Parameter {param_name} description mismatch. Expected: {expected_description}, Got: {actual_param.get('description')}"
                    
                assert actual_param.get('sensitive') == expected_sensitive, \
                    f"Parameter {param_name} sensitivity mismatch. Expected: {expected_sensitive}, Got: {actual_param.get('sensitive')}"
                    
        finally:
            # Cleanup
            await nifi_client.process_groups.delete_process_group(process_group_id)

    @pytest.mark.integration  
    async def test_parameter_context_update(
        self,
        workflow_orchestrator: WorkflowOrchestrator,
        nifi_client: NiFiUnifiedClient,
        test_flow_definition: Dict[str, Any],
        simple_parameters: Dict[str, str]
    ):
        """Test dynamic parameter updates without redeployment."""
        flow_name = f"param_update_test_{int(time.time())}"
        
        result = await workflow_orchestrator.deploy_and_register_flow(
            flow_definition=test_flow_definition,
            flow_name=flow_name,
            bucket_name="test-bucket", 
            parameters=simple_parameters,
            comments="Parameter update test"
        )
        
        assert result.get("success"), f"Flow deployment failed: {result}"
        parameter_context_id = result.get("parameter_context_id")
        process_group_id = result.get("process_group_id")

        try:
            # Update parameters
            updated_params = {
                "input_directory": "/tmp/updated_input",
                "output_directory": "/tmp/updated_output"
            }

            # Update parameter context using the proper update request mechanism
            await nifi_client.parameter_contexts.update_parameter_context(
                parameter_context_id,
                updated_params
            )

            # Verify parameters were updated
            updated_context = await nifi_client.parameter_contexts.get_parameter_context(parameter_context_id)
            parameters_list = updated_context.get('component', {}).get('parameters', [])

            param_map = {
                param.get('parameter', {}).get('name'): param.get('parameter', {}).get('value')
                for param in parameters_list
            }

            for param_name, expected_value in updated_params.items():
                actual_value = param_map.get(param_name)
                assert actual_value == expected_value, \
                    f"Parameter {param_name} was not updated. Expected: {expected_value}, Got: {actual_value}"

            # Also verify that batch_size parameter is still there and unchanged
            assert param_map.get("batch_size") == "5", \
                f"Parameter batch_size should remain unchanged. Got: {param_map.get('batch_size')}"

        finally:
            # Cleanup
            await nifi_client.process_groups.delete_process_group(process_group_id)
            await nifi_client.parameter_contexts.delete_parameter_context(parameter_context_id)