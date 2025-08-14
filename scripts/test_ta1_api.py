#!/usr/bin/env python3
"""
Test script to verify TA1 Generation API functionality.
This script can be used to manually test the API endpoint.
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = os.getenv('BACKEND_URL', 'http://localhost:8000')
API_KEY = os.getenv('SERVICE_API_KEY', 'test-token')

# Sample EDI content (valid 837P)
SAMPLE_EDI = """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*TESTCLAIM*20240715*1200*CH~
NM1*41*2*TEST PROVIDER*****46*TST001~
PER*IC*CONTACT NAME*TE*1234567890~
NM1*40*2*PAYER*****46*PAY001~
HL*1**20*1~
NM1*85*2*TEST PROVIDER*****XX*1234567890~
N3*123 TEST STREET~
N4*TEST CITY*CA*90210~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*POLICY123******CI~
NM1*IL*1*PATIENT*JOHN****MI*PAT123~
N3*456 PATIENT STREET~
N4*PATIENT CITY*CA*90210~
DMG*D8*19800101*M~
REF*SY*123456789~
HL*3*2*23*0~
PAT*19~
NM1*QC*1*PATIENT*JOHN~
CLM*CLAIM123*100.00***11:B:1*Y*A*Y*I~
DTP*431*D8*20240701~
CL1*1*1*01~
REF*D9*CLAIM123~
HI*BK:Z1234~
LX*1~
SV1*HC:99213*75.00*UN*1***1~
DTP*472*D8*20240701~
LX*2~
SV1*HC:99214*25.00*UN*1***1~
DTP*472*D8*20240701~
SE*32*0001~
GE*1*1~
IEA*1*000000001~"""

def test_ta1_generation():
    """Test TA1 generation API endpoint."""
    
    # Test cases
    test_cases = [
        {
            "name": "Acceptance TA1",
            "acknowledgment_code": "A",
            "description": "Generate acceptance TA1 acknowledgment"
        },
        {
            "name": "Rejection TA1",
            "acknowledgment_code": "R",
            "error_code": "IK901",
            "error_note": "Interchange rejected due to syntax errors",
            "description": "Generate rejection TA1 acknowledgment"
        },
        {
            "name": "Error TA1",
            "acknowledgment_code": "E",
            "error_code": "IK903",
            "error_note": "Interchange control number mismatch",
            "description": "Generate error TA1 acknowledgment"
        }
    ]
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    print("Testing TA1 Generation API...")
    print("=" * 50)
    
    for test_case in test_cases:
        print(f"\nTesting: {test_case['name']}")
        print(f"Description: {test_case['description']}")
        
        # Prepare request payload
        payload = {
            "edi_content": SAMPLE_EDI,
            "tenant_id": "tenant-a",
            "workflow_id": f"test-ta1-{test_case['acknowledgment_code'].lower()}-001",
            "acknowledgment_code": test_case['acknowledgment_code']
        }
        
        # Add error fields if present
        if "error_code" in test_case:
            payload["error_code"] = test_case["error_code"]
        if "error_note" in test_case:
            payload["error_note"] = test_case["error_note"]
        
        try:
            # Make API request
            response = requests.post(
                f"{BASE_URL}/api/v1/edi/generate-ta1",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Control Number: {data.get('control_number', 'N/A')}")
                print(f"Processing Time: {data.get('processing_time_ms', 'N/A')}ms")
                print("✅ Test PASSED")
                
                # Show a snippet of the TA1 content
                ta1_content = data.get('ta1_content', '')
                ta1_lines = ta1_content.split('\n')
                print("TA1 Content Preview:")
                for line in ta1_lines[:3]:  # Show first 3 lines
                    print(f"  {line}")
            else:
                print(f"❌ Test FAILED - {response.status_code}")
                print(f"Error: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
    
    print("\n" + "=" * 50)
    print("TA1 Generation API Testing Complete")

if __name__ == "__main__":
    test_ta1_generation()