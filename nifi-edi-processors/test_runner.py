#!/usr/bin/env python3
"""
Test runner script for NiFi EDI Processors.
Provides convenient ways to run different test suites.
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a shell command and handle errors."""
    print(f"\n🔍 {description}")
    print(f"   Command: {command}\n")
    
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              cwd=os.path.dirname(os.path.abspath(__file__)))
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed with exit code {e.returncode}")
        return False

def main():
    """Main test runner."""
    if len(sys.argv) < 2:
        print("🧪 NiFi EDI Processors Test Runner")
        print("\nUsage:")
        print("  python test_runner.py all          - Run all tests")
        print("  python test_runner.py unit         - Run unit tests only")
        print("  python test_runner.py integration  - Run integration tests only")
        print("  python test_runner.py format       - Run format tests only")
        print("  python test_runner.py validation   - Run validation service tests")
        print("  python test_runner.py workflow     - Run workflow integration tests")
        print("  python test_runner.py parsing      - Run parsing format tests")
        print("  python test_runner.py verbose      - Run all tests with verbose output")
        print("  python test_runner.py coverage     - Run tests with coverage report")
        return
    
    command = sys.argv[1]
    
    if command == "all":
        success = run_command("pytest", "Running all tests")
    elif command == "unit":
        success = run_command("pytest tests/edi_parser/", "Running unit tests")
    elif command == "integration":
        success = run_command("pytest tests/test_validation_service.py tests/test_integrated_workflow.py", 
                             "Running integration tests")
    elif command == "format":
        success = run_command("pytest tests/test_parsing_formats.py", "Running format tests")
    elif command == "validation":
        success = run_command("pytest tests/test_validation_service.py", "Running validation service tests")
    elif command == "workflow":
        success = run_command("pytest tests/test_integrated_workflow.py", "Running workflow integration tests")
    elif command == "parsing":
        success = run_command("pytest tests/test_parsing_formats.py", "Running parsing format tests")
    elif command == "verbose":
        success = run_command("pytest -v", "Running all tests with verbose output")
    elif command == "coverage":
        success = run_command("pytest --cov=edi_common --cov=processors --cov-report=html", 
                             "Running tests with coverage")
    else:
        print(f"❌ Unknown command: {command}")
        print("Use 'python test_runner.py' without arguments to see usage.")
        return
    
    if success:
        print("\n✅ All tests completed successfully!")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()