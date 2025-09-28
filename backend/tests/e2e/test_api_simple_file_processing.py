"""End-to-end test covering a complete file processing workflow via V1 REST APIs."""

from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable

import pytest
from httpx import AsyncClient

from src.api.dependencies import (
    get_nifi_client,
    get_registry_client,
    get_workflow_orchestrator,
)
from src.main import app
from tests.test_config import (
    get_test_nifi_client,
    get_test_registry_client,
)

pytestmark = pytest.mark.e2e

SAMPLE_FILES_DIR = Path(__file__).parent / "testdata"
# Use the nifi-working directory for all test data (mounted at /tmp/nifi-working)
# For local development/testing
TEST_DATA_ROOT = Path(__file__).parent.parent.parent.parent / "tmp" / "nifi-working" / "e2e_api_test_files"
# For NiFi container access (mounted at /tmp/nifi-working)
NIFI_TEST_DATA_ROOT = Path("/tmp/nifi-working/e2e_api_test_files")


@dataclass
class FlowDirectories:
    """Directories used for the NiFi GetFile/PutFile processors."""

    base: Path
    input: Path
    output: Path
    error: Path


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(scope="module")
async def nifi_client():
    client = get_test_nifi_client()
    async with client:
        yield client


@pytest.fixture(scope="module")
async def registry_client():
    client = get_test_registry_client()
    async with client:
        yield client


@pytest.fixture(scope="module")
async def api_client(nifi_client, registry_client):
    """HTTP client for testing API endpoints with dependency overrides."""
    
    # Override dependencies to use our test clients
    def get_test_orchestrator():
        from src.services.workflow_orchestrator import WorkflowOrchestrator
        return WorkflowOrchestrator(nifi_client, registry_client)
    
    app.dependency_overrides[get_nifi_client] = lambda: nifi_client
    app.dependency_overrides[get_registry_client] = lambda: registry_client
    app.dependency_overrides[get_workflow_orchestrator] = get_test_orchestrator
    
    try:
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            yield client
    finally:
        # Clean up overrides
        app.dependency_overrides.clear()


def _create_test_directories(test_run_id: str) -> FlowDirectories:
    """Create test directories for file processing."""
    # Ensure the root test data directory exists locally
    TEST_DATA_ROOT.mkdir(parents=True, exist_ok=True)
    
    # Create directories locally (host filesystem)
    local_base_path = TEST_DATA_ROOT / f"edi_lens_api_e2e_{test_run_id}"
    local_input_path = local_base_path / "input"
    local_output_path = local_base_path / "output"
    local_error_path = local_base_path / "error"

    for directory in (local_input_path, local_output_path, local_error_path):
        directory.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(directory, 0o777)
        except (OSError, PermissionError):
            # In some environments, chmod might fail, but the directory should still be usable
            pass

    # Return paths that NiFi container can access (via volume mount)
    nifi_base_path = NIFI_TEST_DATA_ROOT / f"edi_lens_api_e2e_{test_run_id}"
    nifi_input_path = nifi_base_path / "input"
    nifi_output_path = nifi_base_path / "output"
    nifi_error_path = nifi_base_path / "error"

    return FlowDirectories(
        base=nifi_base_path, 
        input=nifi_input_path, 
        output=nifi_output_path, 
        error=nifi_error_path
    )


def _load_sample_files() -> Dict[str, str]:
    """Load sample test files content."""
    contents: Dict[str, str] = {}
    for sample_file in SAMPLE_FILES_DIR.glob("*.txt"):
        contents[sample_file.name] = sample_file.read_text()
    return contents


def _stage_input_files(test_directories: FlowDirectories, sample_contents: Dict[str, str], test_run_id: str) -> Dict[str, str]:
    """Stage input files for processing and return expected outputs."""
    expected_outputs: Dict[str, str] = {}

    # Write files to local directory (host filesystem)
    local_input_path = TEST_DATA_ROOT / f"edi_lens_api_e2e_{test_run_id}" / "input"
    
    for filename, content in sample_contents.items():
        destination = local_input_path / filename
        destination.write_text(content)
        try:
            os.chmod(destination, 0o666)
        except (OSError, PermissionError):
            # In some environments, chmod might fail, but the file should still be readable
            pass
        expected_outputs[f"processed_{filename}"] = content

    return expected_outputs


def _load_sample_files() -> Dict[str, str]:
    """Load sample test files content."""
    contents: Dict[str, str] = {}
    for sample_file in SAMPLE_FILES_DIR.glob("*.txt"):
        contents[sample_file.name] = sample_file.read_text()
    return contents


async def _wait_for_outputs(
    local_directory: Path, expected_files: Iterable[str], timeout_seconds: int = 60, poll_interval: float = 2.0
) -> None:
    """Wait for output files to appear in the local directory."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    expected = set(expected_files)

    while True:
        current_files = {item.name for item in local_directory.glob("*") if item.is_file()}
        if expected.issubset(current_files):
            return

        if loop.time() >= deadline:
            missing = expected - current_files
            raise AssertionError(f"Timed out waiting for output files: {sorted(missing)}")

        await asyncio.sleep(poll_interval)


async def test_api_simple_file_processing_flow(api_client: AsyncClient):
    """Validate that a NiFi flow processes files end-to-end via the V1 REST APIs."""

    test_run_id = uuid.uuid4().hex[:8]
    flow_name = f"api-e2e-simple-file-processing-{test_run_id}"
    bucket_name = f"api-e2e-simple-bucket-{test_run_id}"

    # Setup test environment
    test_dirs = _create_test_directories(test_run_id)
    sample_contents = _load_sample_files()
    expected_outputs = _stage_input_files(test_dirs, sample_contents, test_run_id)

    # Variables to track created resources for cleanup
    bucket_id = None
    flow_id = None  # This will be the NiFi process group ID
    
    try:
        # Step 1: Create a registry bucket via API
        bucket_payload = {
            "name": bucket_name,
            "description": f"E2E API test bucket for {flow_name}"
        }
        bucket_response = await api_client.post("/api/v1/registry/buckets/", json=bucket_payload)
        assert bucket_response.status_code == 201, f"Failed to create bucket: {bucket_response.text}"
        bucket_data = bucket_response.json()
        bucket_id = bucket_data["id"]
        
        # Step 2: Get available templates and create the flow via API  
        templates_response = await api_client.get("/api/v1/templates/")
        assert templates_response.status_code == 200, f"Failed to get templates: {templates_response.text}"
        templates_data = templates_response.json()
        templates = templates_data.get("templates", [])
        assert templates, "No templates available for flow creation"
        
        # Find a simple file processing template
        template_id = None
        for template in templates:
            if "file" in template.get("name", "").lower() or "simple" in template.get("name", "").lower():
                template_id = template["id"]
                break
        
        if not template_id:
            template_id = templates[0]["id"]  # Fallback to first available
        
        flow_definition = {
            "name": flow_name,
            "description": "Simple file processing flow for API end-to-end testing",
            "bucket_id": bucket_id,  # Use the bucket we created
            "definition": {
                "name": flow_name,
                "description": "Simple file processing flow for API end-to-end testing",
                "processors": [
                    {
                        "identifier": f"getfile-{test_run_id}",
                        "name": f"GetFile-{test_run_id}",
                        "type": "org.apache.nifi.processors.standard.GetFile",
                        "position": {"x": 0.0, "y": 0.0},
                        "properties": {
                            "Input Directory": "#{input_directory}",
                            "File Filter": "#{input_pattern}",
                            "Keep Source File": "false",
                            "Minimum File Age": "0 sec",
                        },
                        "schedulingPeriod": "1 sec",
                        "schedulingStrategy": "TIMER_DRIVEN",
                        "executionNode": "ALL",
                        "concurrentlySchedulableTaskCount": 1,
                    },
                    {
                        "identifier": f"update-{test_run_id}",
                        "name": f"UpdateAttribute-{test_run_id}",
                        "type": "org.apache.nifi.processors.attributes.UpdateAttribute",
                        "position": {"x": 350.0, "y": 0.0},
                        "properties": {
                            "filename": "processed_${filename}",
                        },
                        "schedulingPeriod": "0 sec",
                        "schedulingStrategy": "TIMER_DRIVEN",
                        "executionNode": "ALL",
                        "concurrentlySchedulableTaskCount": 1,
                    },
                    {
                        "identifier": f"putfile-{test_run_id}",
                        "name": f"PutFile-{test_run_id}",
                        "type": "org.apache.nifi.processors.standard.PutFile",
                        "position": {"x": 650.0, "y": 0.0},
                        "properties": {
                            "Directory": "#{output_directory}",
                            "Create Missing Directories": "true",
                        },
                        "schedulingPeriod": "0 sec",
                        "schedulingStrategy": "TIMER_DRIVEN",
                        "executionNode": "ALL",
                        "concurrentlySchedulableTaskCount": 1,
                        "autoTerminatedRelationships": ["success", "failure"],
                    },
                ],
                "connections": [
                    {
                        "identifier": f"connection-1-{test_run_id}",
                        "name": f"get-to-update-{test_run_id}",
                        "source": {"id": f"getfile-{test_run_id}", "type": "PROCESSOR"},
                        "destination": {"id": f"update-{test_run_id}", "type": "PROCESSOR"},
                        "selectedRelationships": ["success"],
                        "backPressureObjectThreshold": 1000,
                        "backPressureDataSizeThreshold": "1 GB",
                        "flowFileExpiration": "0 sec",
                    },
                    {
                        "identifier": f"connection-2-{test_run_id}",
                        "name": f"update-to-put-{test_run_id}",
                        "source": {"id": f"update-{test_run_id}", "type": "PROCESSOR"},
                        "destination": {"id": f"putfile-{test_run_id}", "type": "PROCESSOR"},
                        "selectedRelationships": ["success"],
                        "backPressureObjectThreshold": 1000,
                        "backPressureDataSizeThreshold": "1 GB",
                        "flowFileExpiration": "0 sec",
                    },
                ],
                "process_groups": []
            },
            "parameters": {
                "input_directory": str(test_dirs.input),
                "output_directory": str(test_dirs.output),
                "input_pattern": ".*\\.txt$",
            }
        }

        flow_response = await api_client.post("/api/v1/flows/", json=flow_definition)
        assert flow_response.status_code == 201, f"Failed to create flow: {flow_response.text}"
        flow_data = flow_response.json()
        flow_id = flow_data["id"]  # NiFi process group ID
        
        # Step 3: Start the flow via API
        start_response = await api_client.post(f"/api/v1/flows/{flow_id}/executions/start")
        assert start_response.status_code == 200, f"Failed to start flow: {start_response.text}"
        start_data = start_response.json()
        assert start_data["success"] is True, f"Start flow returned success=False: {start_data}"
        
        # Verify flow is running
        status_response = await api_client.get(f"/api/v1/flows/{flow_id}")
        assert status_response.status_code == 200, f"Failed to get flow status: {status_response.text}"
        status_data = status_response.json()
        assert status_data["status"] in ["running", "partially_running"], f"Flow should be running, got: {status_data['status']}"
        
        # Step 4: Wait for file processing to complete
        # Wait for outputs in local directory
        local_output_path = TEST_DATA_ROOT / f"edi_lens_api_e2e_{test_run_id}" / "output"
        await _wait_for_outputs(local_output_path, expected_outputs.keys())

        # Step 5: Verify file processing results
        # Check output files in local directory
        for output_name, expected_content in expected_outputs.items():
            output_file = local_output_path / output_name
            assert output_file.exists(), f"Expected output file missing: {output_name}"
            actual_content = output_file.read_text()
            assert actual_content == expected_content, f"Unexpected content in {output_name}"

        # Check that input files were consumed (in local directory)
        local_input_path = TEST_DATA_ROOT / f"edi_lens_api_e2e_{test_run_id}" / "input"
        remaining_inputs = list(local_input_path.glob("*.txt"))
        assert not remaining_inputs, "Input files should be consumed by the flow"

        # Step 6: Stop the flow via API
        stop_response = await api_client.post(f"/api/v1/flows/{flow_id}/executions/stop")
        assert stop_response.status_code == 200, f"Failed to stop flow: {stop_response.text}"
        stop_data = stop_response.json()
        assert stop_data["success"] is True, f"Stop flow returned success=False: {stop_data}"
        
        # Verify flow is stopped
        final_status_response = await api_client.get(f"/api/v1/flows/{flow_id}")
        assert final_status_response.status_code == 200, f"Failed to get final flow status: {final_status_response.text}"
        final_status_data = final_status_response.json()
        assert final_status_data["status"] in ["stopped", "partially_stopped"], f"Flow should be stopped, got: {final_status_data['status']}"

    finally:
        # Step 7: Cleanup via API
        try:
            if flow_id:
                # Delete the flow via API
                delete_response = await api_client.delete(f"/api/v1/flows/{flow_id}")
                # Note: 501 Not Implemented is expected if delete endpoint doesn't exist yet
                if delete_response.status_code not in [200, 204, 404, 501]:
                    print(f"Warning: Failed to delete flow via API: {delete_response.status_code} {delete_response.text}")
        except Exception as e:
            print(f"Warning: Exception during flow cleanup: {e}")
            
        try:
            if bucket_id:
                # Delete the bucket via API  
                bucket_delete_response = await api_client.delete(f"/api/v1/registry/buckets/{bucket_id}")
                # Note: 501 Not Implemented is expected if delete endpoint doesn't exist yet
                if bucket_delete_response.status_code not in [200, 204, 404, 501]:
                    print(f"Warning: Failed to delete bucket via API: {bucket_delete_response.status_code} {bucket_delete_response.text}")
        except Exception as e:
            print(f"Warning: Exception during bucket cleanup: {e}")

        # Clean up local test directories
        local_base_path = TEST_DATA_ROOT / f"edi_lens_api_e2e_{test_run_id}"
        if local_base_path.exists():
            shutil.rmtree(local_base_path, ignore_errors=True)