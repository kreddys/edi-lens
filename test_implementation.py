#!/usr/bin/env python3
"""
Simple test script to verify our NiFi workflow service implementation.
"""

import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Mock the settings
class MockSettings:
    NIFI_URL = "http://localhost:8080"
    NIFI_REGISTRY_URL = "http://localhost:18080"

# Mock the config module
import sys
from unittest.mock import MagicMock
sys.modules['src.core.config'] = MagicMock()
sys.modules['src.core.config'].settings = MockSettings()

from src.services.nifi_workflow_service import NiFiWorkflowService
from src.services.workflow_execution_service import WorkflowExecutionService

async def test_nifi_workflow_service():
    """Test that our NiFi workflow service can be instantiated."""
    print("Testing NiFiWorkflowService...")
    try:
        # This should work without errors
        service = NiFiWorkflowService(None)
        print("✓ NiFiWorkflowService can be instantiated")
        return True
    except Exception as e:
        print(f"✗ NiFiWorkflowService failed: {e}")
        return False

async def test_workflow_execution_service():
    """Test that our workflow execution service can be instantiated."""
    print("Testing WorkflowExecutionService...")
    try:
        # This should work without errors
        service = WorkflowExecutionService(None)
        print("✓ WorkflowExecutionService can be instantiated")
        return True
    except Exception as e:
        print(f"✗ WorkflowExecutionService failed: {e}")
        return False

async def main():
    """Run all tests."""
    print("Running implementation verification tests...\\n")
    
    tests = [
        test_nifi_workflow_service,
        test_workflow_execution_service
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            results.append(False)
        print()
    
    passed = sum(results)
    total = len(results)
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)