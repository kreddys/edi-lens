#!/usr/bin/env python3

import sys
import os

print("=== DEBUG PROCESSOR ===")
print(f"Python executable: {sys.executable}")
print(f"Working directory: {os.getcwd()}")
print("Python path:")
for i, path in enumerate(sys.path):
    print(f"  {i}: {path}")

print(f"PYTHONPATH env: {os.environ.get('PYTHONPATH', 'NOT SET')}")

print("\n=== TESTING IMPORTS ===")
try:
    print("Testing pydantic import...")
    from pydantic import BaseModel, Field
    print("SUCCESS: pydantic imported!")
except Exception as e:
    print(f"FAILED: {e}")
    print("Attempting to debug...")
    
    # Check if pydantic directory exists
    for path in sys.path:
        pydantic_path = os.path.join(path, 'pydantic')
        if os.path.exists(pydantic_path):
            print(f"Found pydantic directory at: {pydantic_path}")
            print(f"Contents: {os.listdir(pydantic_path)[:5]}...")  # Show first 5 files
        else:
            print(f"No pydantic at: {pydantic_path}")

try:
    print("Testing edi_common import...")
    from edi_common.validation_service import EDIValidationService
    print("SUCCESS: edi_common imported!")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()

print("=== END DEBUG ===")