#!/usr/bin/env python3

import importlib.util
import sys
import os

print("=== TESTING IMPORTLIB MODULE LOADING ===")
print(f"Current sys.path: {sys.path[:3]}...")
print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'NOT SET')}")

# Test the exact method NiFi uses
module_file = "/opt/nifi/nifi-current/python_extensions/edi_validation_processor.py"
module_name = "edi_validation_processor"

print(f"\nTesting importlib.util method on: {module_file}")

try:
    # Create the module specification (same as NiFi)
    module_spec = importlib.util.spec_from_file_location(module_name, module_file)
    print(f"Module Spec: {module_spec}")

    # Create the module from the specification (same as NiFi)
    module = importlib.util.module_from_spec(module_spec)
    print(f"Module: {module}")

    # Load the module (same as NiFi)
    sys.modules[module_name] = module
    module_spec.loader.exec_module(module)
    print("SUCCESS: Module loaded using importlib method!")

except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()

print("=== END TEST ===")