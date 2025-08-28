"""
End-to-End integration test for EDI Processor
Tests actual file processing through NiFi with real EDI content
"""

import json
import time
import requests
import pytest
import tempfile
import os
from pathlib import Path

class TestEDIProcessorE2E:
    """End-to-End test for EDI Processor in real NiFi environment"""
    
    # NiFi configuration
    NIFI_URL = "http://localhost:8080"
    USERNAME = "superuser@edilens.com"
    PASSWORD = "password123456789"
    
    @pytest.fixture(scope="class")
    def nifi_auth_token(self):
        """Get authentication token from NiFi"""
        auth_url = f"{self.NIFI_URL}/nifi-api/access/token"
        data = {
            'username': self.USERNAME,
            'password': self.PASSWORD
        }
        
        response = requests.post(auth_url, data=data)
        if response.status_code == 201:
            return response.text
        else:
            pytest.skip(f"Cannot authenticate with NiFi: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def nifi_headers(self, nifi_auth_token):
        """Create headers for NiFi API requests"""
        return {
            'Authorization': f'Bearer {nifi_auth_token}',
            'Content-Type': 'application/json'
        }
    
    def test_edi_processor_file_processing_e2e(self, nifi_headers):
        """
        End-to-end test: Create a complete workflow and process an actual EDI file
        """
    def test_edi_processor_file_processing_e2e(self, nifi_headers, valid_837p_edi_string):
        """
        End-to-end test: Create a complete workflow and process an actual EDI file
        """
        # Use real EDI content from conftest
        sample_edi = valid_837p_edi_string
        
        print("🧪 Starting End-to-End EDI Processing Test")
        
        # Step 1: Create test directories in NiFi container
        test_input_dir = "/tmp/edi_e2e_test/input"
        test_output_dir = "/tmp/edi_e2e_test/output"
        
        # Create the directories via docker exec
        os.system(f"docker exec nifi mkdir -p {test_input_dir}")
        os.system(f"docker exec nifi mkdir -p {test_output_dir}")
        
        print(f"✅ Created test directories: {test_input_dir}, {test_output_dir}")
        
        # Step 2: Create a test process group
        pg_data = {
            "revision": {"version": 0},
            "component": {
                "name": "EDI_E2E_Test",
                "position": {"x": 100, "y": 100}
            }
        }
        
        pg_response = requests.post(
            f"{self.NIFI_URL}/nifi-api/process-groups/root/process-groups",
            headers=nifi_headers,
            json=pg_data
        )
        
        assert pg_response.status_code == 201
        pg_id = pg_response.json()['id']
        print(f"✅ Created process group: {pg_id}")
        
        try:
            # Step 3: Create GetFile processor
            getfile_data = {
                "revision": {"version": 0},
                "component": {
                    "type": "org.apache.nifi.processors.standard.GetFile",
                    "name": "GetFile_E2E",
                    "position": {"x": 100, "y": 200},
                    "config": {
                        "properties": {
                            "Input Directory": test_input_dir,
                            "File Filter": ".*\\.edi$",
                            "Keep Source File": "false",
                            "Polling Interval": "1 sec"
                        }
                    }
                }
            }
            
            getfile_response = requests.post(
                f"{self.NIFI_URL}/nifi-api/process-groups/{pg_id}/processors",
                headers=nifi_headers,
                json=getfile_data
            )
            
            assert getfile_response.status_code == 201
            getfile_id = getfile_response.json()['id']
            print(f"✅ Created GetFile processor: {getfile_id}")
            
            # Step 4: Create EDI Processor
            edi_data = {
                "revision": {"version": 0},
                "component": {
                    "type": "EDIProcessor",
                    "name": "EDI_Processor_E2E",
                    "position": {"x": 300, "y": 200},
                    "config": {
                        "properties": {
                            "Validation Schema": "837.5010.X222.A1.json",
                            "SNIP Level": "3",
                            "Tenant ID": "e2e-test",
                            "Generate CDM": "true",
                            "Generate TA1": "true",
                            "Force TA1": "false",
                            "CDM Include Metadata": "true"
                        }
                    }
                }
            }
            
            edi_response = requests.post(
                f"{self.NIFI_URL}/nifi-api/process-groups/{pg_id}/processors",
                headers=nifi_headers,
                json=edi_data
            )
            
            assert edi_response.status_code == 201
            edi_id = edi_response.json()['id']
            print(f"✅ Created EDI Processor: {edi_id}")
            
            # Step 5: Create PutFile processor
            putfile_data = {
                "revision": {"version": 0},
                "component": {
                    "type": "org.apache.nifi.processors.standard.PutFile",
                    "name": "PutFile_E2E",
                    "position": {"x": 500, "y": 200},
                    "config": {
                        "properties": {
                            "Directory": test_output_dir,
                            "Conflict Resolution Strategy": "replace"
                        },
                        "autoTerminatedRelationships": ["success", "failure"]
                    }
                }
            }
            
            putfile_response = requests.post(
                f"{self.NIFI_URL}/nifi-api/process-groups/{pg_id}/processors",
                headers=nifi_headers,
                json=putfile_data
            )
            
            assert putfile_response.status_code == 201
            putfile_id = putfile_response.json()['id']
            print(f"✅ Created PutFile processor: {putfile_id}")
            
            # Step 6: Create connections
            # GetFile -> EDI Processor
            conn1_data = {
                "revision": {"version": 0},
                "component": {
                    "name": "GetFile_to_EDI",
                    "source": {"id": getfile_id, "groupId": pg_id, "type": "PROCESSOR"},
                    "destination": {"id": edi_id, "groupId": pg_id, "type": "PROCESSOR"},
                    "selectedRelationships": ["success"]
                }
            }
            
            conn1_response = requests.post(
                f"{self.NIFI_URL}/nifi-api/process-groups/{pg_id}/connections",
                headers=nifi_headers,
                json=conn1_data
            )
            
            assert conn1_response.status_code == 201
            print("✅ Created GetFile -> EDI Processor connection")
            
            # EDI Processor -> PutFile (success)
            conn2_data = {
                "revision": {"version": 0},
                "component": {
                    "name": "EDI_to_PutFile",
                    "source": {"id": edi_id, "groupId": pg_id, "type": "PROCESSOR"},
                    "destination": {"id": putfile_id, "groupId": pg_id, "type": "PROCESSOR"},
                    "selectedRelationships": ["success"]
                }
            }
            
            conn2_response = requests.post(
                f"{self.NIFI_URL}/nifi-api/process-groups/{pg_id}/connections",
                headers=nifi_headers,
                json=conn2_data
            )
            
            assert conn2_response.status_code == 201
            print("✅ Created EDI Processor -> PutFile connection")
            
            # Auto-terminate failure relationship
            time.sleep(2)  # Wait for processor to be ready
            edi_current = requests.get(f"{self.NIFI_URL}/nifi-api/processors/{edi_id}", headers=nifi_headers)
            if edi_current.status_code == 200:
                edi_data_current = edi_current.json()
                auto_terminate_config = {
                    "revision": edi_data_current['revision'],
                    "component": {
                        "id": edi_id,
                        "config": {
                            "properties": edi_data_current['component']['config']['properties'],
                            "autoTerminatedRelationships": ["failure"]
                        }
                    }
                }
                
                requests.put(f"{self.NIFI_URL}/nifi-api/processors/{edi_id}", headers=nifi_headers, json=auto_terminate_config)
                print("✅ Auto-terminated failure relationship")
            
            # Step 7: Wait for processor initialization before starting
            time.sleep(3)
            
            # Step 8: Start all processors
            processors = [getfile_id, edi_id, putfile_id]
            for proc_id in processors:
                proc_response = requests.get(f"{self.NIFI_URL}/nifi-api/processors/{proc_id}", headers=nifi_headers)
                if proc_response.status_code == 200:
                    proc_data = proc_response.json()
                    start_config = {
                        "revision": proc_data['revision'],
                        "component": {
                            "id": proc_id,
                            "state": "RUNNING"
                        }
                    }
                    
                    start_response = requests.put(f"{self.NIFI_URL}/nifi-api/processors/{proc_id}", headers=nifi_headers, json=start_config)
                    if start_response.status_code == 200:
                        print(f"✅ Started processor: {proc_id}")
                    else:
                        print(f"⚠️ Failed to start processor {proc_id}: {start_response.status_code}")
                        print(f"   Response: {start_response.text}")
            
            # Wait for processors to be fully running
            time.sleep(5)
            
            # Step 9: Create test EDI file
            test_filename = f"test_edi_{int(time.time())}.edi"
            
            # Escape the EDI content properly for shell
            escaped_edi = sample_edi.replace('"', '\\"').replace('$', '\\$')
            
            # Write EDI content to container
            write_result = os.system(f'docker exec nifi bash -c \'echo "{escaped_edi}" > {test_input_dir}/{test_filename}\'')
            if write_result == 0:
                print(f"✅ Created test EDI file: {test_filename}")
            else:
                print(f"⚠️ Failed to create test file, exit code: {write_result}")
            
            # Verify file was created
            file_check = os.popen(f"docker exec nifi ls -la {test_input_dir}/{test_filename} 2>/dev/null").read().strip()
            if file_check:
                print(f"✅ File verified: {file_check}")
            else:
                print(f"⚠️ File not found after creation")
            
            # Step 10: Wait for processing and check results
            print("⏰ Waiting for file processing...")
            time.sleep(15)  # Increased wait time
            
            # Check if output file was created
            result = os.system(f"docker exec nifi ls -la {test_output_dir}/")
            
            # Check for output files
            output_check = os.popen(f"docker exec nifi ls {test_output_dir}/ 2>/dev/null").read().strip()
            
            if output_check:
                print(f"✅ Output files found: {output_check}")
                
                # Try to read the output content
                output_content = os.popen(f"docker exec nifi cat {test_output_dir}/{output_check.split()[0]} 2>/dev/null").read()
                
                if output_content:
                    try:
                        # Parse as JSON to verify it's proper CDM format
                        output_json = json.loads(output_content)
                        
                        print("✅ Successfully processed EDI file!")
                        print(f"   - Validation present: {'validation' in output_json}")
                        print(f"   - CDM present: {'cdm' in output_json}")
                        print(f"   - TA1 present: {'ta1' in output_json}")
                        
                        if 'cdm' in output_json:
                            cdm = output_json['cdm']
                            print(f"   - CDM format: {cdm.get('metadata', {}).get('format', 'UNKNOWN')}")
                            print(f"   - Functional groups: {cdm.get('metadata', {}).get('functional_group_count', 0)}")
                        
                        # Verify proper CDM structure
                        if 'cdm' in output_json:
                            assert 'header' in output_json['cdm'], "CDM should have header"
                            assert 'functional_groups' in output_json['cdm'], "CDM should have functional_groups"
                            assert output_json['cdm']['metadata']['format'] == 'CDM_HIERARCHICAL_V2', "Should use proper CDM format"
                        
                        print("🎉 End-to-End test PASSED!")
                        
                    except json.JSONDecodeError:
                        print(f"⚠️ Output is not valid JSON: {output_content[:200]}...")
                        assert False, "Output should be valid JSON"
                else:
                    print("⚠️ Could not read output file content")
            else:
                print("❌ No output files found")
                
                # Debug: Check processor status
                print("🔍 Debugging processor status...")
                for proc_id, proc_name in [(getfile_id, "GetFile"), (edi_id, "EDI"), (putfile_id, "PutFile")]:
                    try:
                        proc_response = requests.get(f"{self.NIFI_URL}/nifi-api/processors/{proc_id}", headers=nifi_headers)
                        if proc_response.status_code == 200:
                            proc_data = proc_response.json()
                            state = proc_data['component']['state']
                            print(f"   - {proc_name} processor state: {state}")
                            
                            # Check for validation errors
                            validation_errors = proc_data['component'].get('validationErrors', [])
                            if validation_errors:
                                print(f"   - {proc_name} validation errors: {validation_errors}")
                    except Exception as e:
                        print(f"   - Error checking {proc_name}: {e}")
                
                # Check if input file is still there (processing failed)
                input_check = os.popen(f"docker exec nifi ls {test_input_dir}/ 2>/dev/null").read().strip()
                if input_check:
                    print(f"⚠️ Input file still present: {input_check}")
                else:
                    print("✅ Input file was consumed (good sign)")
                
                # Check NiFi logs for errors
                print("🔍 Checking recent NiFi logs...")
                log_check = os.popen("docker exec nifi tail -20 /opt/nifi/nifi-current/logs/nifi-app.log 2>/dev/null").read()
                if "ERROR" in log_check or "Exception" in log_check:
                    print("⚠️ Found errors in NiFi logs:")
                    for line in log_check.split('\n'):
                        if "ERROR" in line or "Exception" in line:
                            print(f"   {line}")
                
                # If still no output after debugging, this is a real failure
                assert False, "No output files were created"
        
        finally:
            # Cleanup: Stop processors and delete process group
            try:
                print("🧹 Cleaning up test resources...")
                
                # Stop all processors first
                for proc_id in [getfile_id, edi_id, putfile_id]:
                    try:
                        proc_response = requests.get(f"{self.NIFI_URL}/nifi-api/processors/{proc_id}", headers=nifi_headers)
                        if proc_response.status_code == 200:
                            proc_data = proc_response.json()
                            stop_config = {
                                "revision": proc_data['revision'],
                                "component": {
                                    "id": proc_id,
                                    "state": "STOPPED"
                                }
                            }
                            requests.put(f"{self.NIFI_URL}/nifi-api/processors/{proc_id}", headers=nifi_headers, json=stop_config)
                    except:
                        pass
                
                time.sleep(2)
                
                # Delete process group
                pg_response = requests.get(f"{self.NIFI_URL}/nifi-api/process-groups/{pg_id}", headers=nifi_headers)
                if pg_response.status_code == 200:
                    revision = pg_response.json()['revision']['version']
                    requests.delete(
                        f"{self.NIFI_URL}/nifi-api/process-groups/{pg_id}?version={revision}",
                        headers=nifi_headers
                    )
                
                # Clean up test directories
                os.system(f"docker exec nifi rm -rf /tmp/edi_e2e_test")
                
                print("✅ Cleanup completed")
                
            except Exception as e:
                print(f"⚠️ Cleanup warning: {e}")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])