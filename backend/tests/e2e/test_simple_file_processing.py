"""End-to-end validation of NiFi file processing through the orchestrator."""

from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Dict, Iterable

import pytest

from src.services.workflow_orchestrator import WorkflowOrchestrator
from tests.test_config import (
    get_test_nifi_client,
    get_test_registry_client,
)

pytestmark = pytest.mark.e2e

SAMPLE_FILES_DIR = Path(__file__).parent / "testdata"
SHARED_VOLUME_ROOT = Path("/e2e_test_files")


@dataclass
class FlowDirectories:
    """Directories used for the NiFi GetFile/PutFile processors."""

    base: Path
    input: Path
    output: Path
    error: Path


@pytest.fixture(scope="module")
def event_loop() -> AsyncIterator[asyncio.AbstractEventLoop]:
    """Provide a dedicated event loop for module-scoped fixtures."""

    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(scope="module")
async def nifi_client():
    """Yield a configured NiFi client for end-to-end scenarios."""

    client = get_test_nifi_client()
    async with client:
        yield client


@pytest.fixture(scope="module")
async def registry_client():
    """Yield a configured Registry client for end-to-end scenarios."""

    client = get_test_registry_client()
    async with client:
        yield client


@pytest.fixture(scope="module")
async def orchestrator(nifi_client, registry_client) -> WorkflowOrchestrator:
    """Return an orchestrator wired to the live clients."""

    return WorkflowOrchestrator(nifi_client, registry_client)


def _create_test_directories(test_run_id: str) -> FlowDirectories:
    """Create and return the directory structure used by the flow under test."""

    base_path = SHARED_VOLUME_ROOT / f"edi_lens_e2e_{test_run_id}"
    input_path = base_path / "input"
    output_path = base_path / "output"
    error_path = base_path / "error"

    for directory in (input_path, output_path, error_path):
        directory.mkdir(parents=True, exist_ok=True)
        os.chmod(directory, 0o777)

    return FlowDirectories(base=base_path, input=input_path, output=output_path, error=error_path)


def _load_sample_files() -> Dict[str, str]:
    """Load bundled sample files that will be staged as test input."""

    return {
        sample_file.name: sample_file.read_text()
        for sample_file in SAMPLE_FILES_DIR.glob("*.txt")
    }


def _stage_input_files(test_directories: FlowDirectories, sample_contents: Dict[str, str]) -> Dict[str, str]:
    """Write sample files to the NiFi input directory and return expected outputs."""

    expected_outputs: Dict[str, str] = {}
    for filename, content in sample_contents.items():
        destination = test_directories.input / filename
        destination.write_text(content)
        os.chmod(destination, 0o666)
        expected_outputs[f"processed_{filename}"] = content
    return expected_outputs


def _build_flow_definition(unique_suffix: str) -> Dict[str, object]:
    """Construct the NiFi flow definition used for the E2E test."""

    getfile_id = f"getfile-{unique_suffix}"
    update_id = f"update-{unique_suffix}"
    putfile_id = f"putfile-{unique_suffix}"

    return {
        "name": f"E2E File Processor {unique_suffix}",
        "description": "Simple file processing flow for end-to-end testing",
        "processors": [
            {
                "identifier": getfile_id,
                "name": f"GetFile-{unique_suffix}",
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
                "identifier": update_id,
                "name": f"UpdateAttribute-{unique_suffix}",
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
                "identifier": putfile_id,
                "name": f"PutFile-{unique_suffix}",
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
                "identifier": f"connection-1-{unique_suffix}",
                "name": f"get-to-update-{unique_suffix}",
                "source": {"id": getfile_id, "type": "PROCESSOR"},
                "destination": {"id": update_id, "type": "PROCESSOR"},
                "selectedRelationships": ["success"],
                "backPressureObjectThreshold": 1000,
                "backPressureDataSizeThreshold": "1 GB",
                "flowFileExpiration": "0 sec",
            },
            {
                "identifier": f"connection-2-{unique_suffix}",
                "name": f"update-to-put-{unique_suffix}",
                "source": {"id": update_id, "type": "PROCESSOR"},
                "destination": {"id": putfile_id, "type": "PROCESSOR"},
                "selectedRelationships": ["success"],
                "backPressureObjectThreshold": 1000,
                "backPressureDataSizeThreshold": "1 GB",
                "flowFileExpiration": "0 sec",
            },
        ],
    }


async def _wait_for_outputs(
    directory: Path,
    expected_files: Iterable[str],
    timeout_seconds: int = 60,
    poll_interval: float = 2.0,
) -> None:
    """Poll the output directory until all expected files are created."""

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    expected = set(expected_files)

    while True:
        current_files = {item.name for item in directory.glob("*") if item.is_file()}
        if expected.issubset(current_files):
            return

        if loop.time() >= deadline:
            missing = expected - current_files
            raise AssertionError(f"Timed out waiting for output files: {sorted(missing)}")

        await asyncio.sleep(poll_interval)


async def test_simple_file_processing_flow(orchestrator, nifi_client, registry_client) -> None:
    """Validate that a NiFi flow processes files end-to-end via the orchestrator."""

    test_run_id = uuid.uuid4().hex[:8]
    flow_name = f"e2e-simple-file-processing-{test_run_id}"
    bucket_name = f"e2e-simple-bucket-{test_run_id}"

    test_dirs = _create_test_directories(test_run_id)
    sample_contents = _load_sample_files()
    expected_outputs = _stage_input_files(test_dirs, sample_contents)

    flow_definition = _build_flow_definition(test_run_id)
    parameters = {
        "input_directory": str(test_dirs.input),
        "output_directory": str(test_dirs.output),
        "input_pattern": ".*\\.txt$",
    }

    process_group_id = None
    parameter_context_id = None
    bucket_id = None
    bucket_info: Dict[str, object] | None = None

    try:
        deploy_result = await orchestrator.deploy_and_register_flow(
            flow_definition=flow_definition,
            flow_name=flow_name,
            bucket_name=bucket_name,
            parameters=parameters,
            comments="E2E simple file processing flow",
        )

        assert deploy_result["success"] is True, f"Deployment failed: {deploy_result}"
        process_group_id = deploy_result.get("process_group_id")
        assert process_group_id, "Deployment did not return a process group id"

        parameter_context_id = deploy_result.get("nifi_deployment", {}).get("parameter_context_id")
        bucket_info = deploy_result.get("bucket_info")
        assert bucket_info, "Bucket information missing from deployment result"
        bucket_id = bucket_info.get("bucket_id")
        assert bucket_id, "Bucket id missing from deployment result"

        start_result = await orchestrator.start_flow_workflow(process_group_id)
        assert start_result["success"] is True, f"Failed to start flow: {start_result}"
        assert start_result["flow_status"]["overall_status"] in {"running", "partially_running"}

        await _wait_for_outputs(test_dirs.output, expected_outputs.keys())

        for output_name, expected_content in expected_outputs.items():
            output_file = test_dirs.output / output_name
            assert output_file.exists(), f"Expected output file missing: {output_name}"
            actual_content = output_file.read_text()
            assert actual_content == expected_content, f"Unexpected content in {output_name}"

        remaining_inputs = list(test_dirs.input.glob("*.txt"))
        assert not remaining_inputs, "Input files should be consumed by the flow"

        stop_result = await orchestrator.stop_flow_workflow(process_group_id)
        assert stop_result["success"] is True, f"Failed to stop flow: {stop_result}"
        assert stop_result["flow_status"]["overall_status"] in {"stopped", "partially_stopped"}

    finally:
        try:
            if process_group_id:
                delete_result = await orchestrator.delete_flow_workflow(
                    process_group_id, remove_from_registry=True
                )
                assert delete_result["success"] is True, f"Failed to delete flow: {delete_result}"
        finally:
            if parameter_context_id:
                try:
                    await nifi_client.parameter_contexts.delete_parameter_context(parameter_context_id)
                except Exception:
                    pass

            if bucket_id:
                try:
                    revision = bucket_info.get("revision") if bucket_info else None
                    await registry_client.buckets.delete_bucket(bucket_id, revision)
                except Exception:
                    pass

            if test_dirs.base.exists():
                shutil.rmtree(test_dirs.base, ignore_errors=True)
