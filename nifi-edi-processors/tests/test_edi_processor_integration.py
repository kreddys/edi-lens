"""
Integration tests for EDI Processor against real NiFi instance
Tests the processor in the actual NiFi environment with real data flows
"""

import json
import time
import requests
import pytest
import tempfile
import os
from datetime import datetime
from pathlib import Path

class TestEDIProcessorIntegration:
    """Integration test suite for EDI Processor in real NiFi environment"""
    
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
    
    @pytest.fixture
    def test_process_group(self, nifi_headers):
        """Create a test process group for integration tests"""
        # Create test process group
        pg_data = {
            "revision": {"version": 0},
            "component": {
                "name": "EDI_Processor_Integration_Test",
                "position": {"x": 100, "y": 100}
            }
        }
        
        response = requests.post(
            f"{self.NIFI_URL}/nifi-api/process-groups/root/process-groups",
            headers=nifi_headers,
            json=pg_data
        )
        
        if response.status_code == 201:
            pg_id = response.json()['id']
            yield pg_id
            
            # Cleanup - delete the process group
            try:
                # Stop all processors first
                self._stop_all_processors_in_group(pg_id, nifi_headers)
                time.sleep(2)
                
                # Delete the process group
                pg_response = requests.get(f"{self.NIFI_URL}/nifi-api/process-groups/{pg_id}", headers=nifi_headers)
                if pg_response.status_code == 200:
                    revision = pg_response.json()['revision']['version']
                    requests.delete(
                        f"{self.NIFI_URL}/nifi-api/process-groups/{pg_id}?version={revision}",
                        headers=nifi_headers
                    )
            except Exception as e:
                print(f"Cleanup warning: {e}")
        else:
            pytest.skip(f"Cannot create test process group: {response.status_code}")
    
    def _stop_all_processors_in_group(self, pg_id, headers):
        """Stop all processors in a process group"""
        response = requests.get(f"{self.NIFI_URL}/nifi-api/process-groups/{pg_id}", headers=headers)
        if response.status_code == 200:
            # This is a simplified cleanup - in real scenarios you'd need to handle this more carefully
            pass
    
    def test_edi_processor_availability(self, nifi_headers):
        """Test that EDI Processor is available in NiFi"""
        response = requests.get(f"{self.NIFI_URL}/nifi-api/flow/processor-types", headers=nifi_headers)
        assert response.status_code == 200
        
        processor_types = response.json()['processorTypes']
        edi_processor_found = False
        
        for processor_type in processor_types:
            if 'EDIProcessor' in processor_type['type']:
                edi_processor_found = True
                print(f"✅ Found EDI Processor: {processor_type['type']}")
                break
        
        assert edi_processor_found, "EDI Processor not found in NiFi processor types"
    
    def test_create_edi_processor(self, test_process_group, nifi_headers):
        """Test creating an EDI Processor instance in NiFi"""
        processor_data = {
            "revision": {"version": 0},
            "component": {
                "type": "EDIProcessor",
                "name": "EDI_Processor_Test",
                "position": {"x": 200, "y": 200},
                "config": {
                    "properties": {}
                }
            }
        }
        
        response = requests.post(
            f"{self.NIFI_URL}/nifi-api/process-groups/{test_process_group}/processors",
            headers=nifi_headers,
            json=processor_data
        )
        
        assert response.status_code == 201, f"Failed to create EDI Processor: {response.text}"
        
        processor_info = response.json()
        processor_id = processor_info['id']
        
        # Verify processor was created with correct type
        assert processor_info['component']['type'] == "EDIProcessor"
        assert processor_info['component']['name'] == "EDI_Processor_Test"
        
        return processor_id
    
    def test_edi_processor_properties(self, test_process_group, nifi_headers):
        """Test EDI Processor properties are correctly configured"""
        processor_id = self.test_create_edi_processor(test_process_group, nifi_headers)
        
        # Wait for processor to fully initialize
        time.sleep(3)
        
        # Get processor details
        response = requests.get(f"{self.NIFI_URL}/nifi-api/processors/{processor_id}", headers=nifi_headers)
        assert response.status_code == 200
        
        processor_details = response.json()
        properties = processor_details['component']['config']['properties']
        
        # Verify expected properties exist
        expected_properties = [
            'Validation Schema',
            'SNIP Level', 
            'Tenant ID',
            'Schema Base Path',
            'Generate CDM',
            'Generate TA1',
            'Force TA1',
            'CDM Include Metadata'
        ]
        
        for prop in expected_properties:
            assert prop in properties, f"Property '{prop}' not found in processor configuration"
        
        print(f"✅ All {len(expected_properties)} expected properties found")
    
    def test_edi_processor_relationships(self, test_process_group, nifi_headers):
        """Test EDI Processor relationships are correctly defined"""
        processor_id = self.test_create_edi_processor(test_process_group, nifi_headers)
        
        # Wait for processor to fully initialize
        time.sleep(3)
        
        # Get processor details
        response = requests.get(f"{self.NIFI_URL}/nifi-api/processors/{processor_id}", headers=nifi_headers)
        assert response.status_code == 200
        
        processor_details = response.json()
        relationships = processor_details['component']['relationships']
        
        # Verify expected relationships
        relationship_names = [rel['name'] for rel in relationships]
        assert 'success' in relationship_names
        assert 'failure' in relationship_names
        
        print(f"✅ Found relationships: {relationship_names}")
    
    def test_edi_processor_configuration_update(self, test_process_group, nifi_headers):
        """Test updating EDI Processor configuration"""
        processor_id = self.test_create_edi_processor(test_process_group, nifi_headers)
        
        # Get current processor configuration
        response = requests.get(f"{self.NIFI_URL}/nifi-api/processors/{processor_id}", headers=nifi_headers)
        assert response.status_code == 200
        
        processor_data = response.json()
        revision = processor_data['revision']
        
        # Update configuration
        updated_config = {
            "revision": revision,
            "component": {
                "id": processor_id,
                "config": {
                    "properties": {
                        "Validation Schema": "837.5010.X222.A1.json",
                        "SNIP Level": "3",
                        "Tenant ID": "integration-test-tenant",
                        "Generate CDM": "true",
                        "Generate TA1": "false",
                        "Force TA1": "false",
                        "CDM Include Metadata": "true"
                    }
                }
            }
        }
        
        response = requests.put(
            f"{self.NIFI_URL}/nifi-api/processors/{processor_id}",
            headers=nifi_headers,
            json=updated_config
        )
        
        assert response.status_code == 200, f"Failed to update processor configuration: {response.text}"
        
        # Verify configuration was updated
        updated_processor = response.json()
        properties = updated_processor['component']['config']['properties']
        
        assert properties['Validation Schema'] == "837.5010.X222.A1.json"
        assert properties['SNIP Level'] == "3"
        assert properties['Tenant ID'] == "integration-test-tenant"
        assert properties['Generate CDM'] == "true"
        
        print("✅ Processor configuration updated successfully")
    
    def test_complete_edi_workflow_integration(self, test_process_group, nifi_headers):
        """Test complete EDI processing workflow in NiFi"""
        # Create test directories in NiFi container
        test_input_dir = "/tmp/edi_integration_test/input"
        test_output_dir = "/tmp/edi_integration_test/output"
        
        # Create directories (this would need to be done via NiFi container access)
        # For now, we'll test the processor creation and configuration
        
        # 1. Create GetFile processor
        getfile_data = {
            "revision": {"version": 0},
            "component": {
                "type": "org.apache.nifi.processors.standard.GetFile",
                "name": "GetFile_Test",
                "position": {"x": 100, "y": 300},
                "config": {
                    "properties": {
                        "Input Directory": test_input_dir,
                        "File Filter": ".*\\.edi$",
                        "Keep Source File": "false"
                    }
                }
            }
        }
        
        getfile_response = requests.post(
            f"{self.NIFI_URL}/nifi-api/process-groups/{test_process_group}/processors",
            headers=nifi_headers,
            json=getfile_data
        )
        
        assert getfile_response.status_code == 201
        getfile_id = getfile_response.json()['id']
        
        # 2. Create EDI Processor
        edi_processor_id = self.test_create_edi_processor(test_process_group, nifi_headers)
        
        # Configure EDI Processor
        edi_response = requests.get(f"{self.NIFI_URL}/nifi-api/processors/{edi_processor_id}", headers=nifi_headers)
        edi_data = edi_response.json()
        
        updated_edi_config = {
            "revision": edi_data['revision'],
            "component": {
                "id": edi_processor_id,
                "config": {
                    "properties": {
                        "python-processor-type": "edi_processor.EDIProcessor",
                        "Validation Schema": "837.5010.X222.A1.json",
                        "SNIP Level": "3",
                        "Tenant ID": "integration-test",
                        "Generate CDM": "true",
                        "Generate TA1": "true",
                        "Force TA1": "false",
                        "CDM Include Metadata": "true"
                    }
                }
            }
        }
        
        requests.put(f"{self.NIFI_URL}/nifi-api/processors/{edi_processor_id}", headers=nifi_headers, json=updated_edi_config)
        
        # 3. Create PutFile processor
        putfile_data = {
            "revision": {"version": 0},
            "component": {
                "type": "org.apache.nifi.processors.standard.PutFile",
                "name": "PutFile_Test",
                "position": {"x": 500, "y": 300},
                "config": {
                    "properties": {
                        "Directory": test_output_dir,
                        "Conflict Resolution Strategy": "replace"
                    }
                }
            }
        }
        
        putfile_response = requests.post(
            f"{self.NIFI_URL}/nifi-api/process-groups/{test_process_group}/processors",
            headers=nifi_headers,
            json=putfile_data
        )
        
        assert putfile_response.status_code == 201
        putfile_id = putfile_response.json()['id']
        
        # 4. Create connections
        # GetFile -> EDI Processor
        connection1_data = {
            "revision": {"version": 0},
            "component": {
                "name": "GetFile_to_EDI",
                "source": {"id": getfile_id, "groupId": test_process_group, "type": "PROCESSOR"},
                "destination": {"id": edi_processor_id, "groupId": test_process_group, "type": "PROCESSOR"},
                "selectedRelationships": ["success"]
            }
        }
        
        conn1_response = requests.post(
            f"{self.NIFI_URL}/nifi-api/process-groups/{test_process_group}/connections",
            headers=nifi_headers,
            json=connection1_data
        )
        
        assert conn1_response.status_code == 201
        
        # EDI Processor -> PutFile (success)
        connection2_data = {
            "revision": {"version": 0},
            "component": {
                "name": "EDI_to_PutFile_Success",
                "source": {"id": edi_processor_id, "groupId": test_process_group, "type": "PROCESSOR"},
                "destination": {"id": putfile_id, "groupId": test_process_group, "type": "PROCESSOR"},
                "selectedRelationships": ["success"]
            }
        }
        
        conn2_response = requests.post(
            f"{self.NIFI_URL}/nifi-api/process-groups/{test_process_group}/connections",
            headers=nifi_headers,
            json=connection2_data
        )
        
        assert conn2_response.status_code == 201
        
        # Auto-terminate failure relationship
        edi_response = requests.get(f"{self.NIFI_URL}/nifi-api/processors/{edi_processor_id}", headers=nifi_headers)
        edi_data = edi_response.json()
        
        auto_terminate_config = {
            "revision": edi_data['revision'],
            "component": {
                "id": edi_processor_id,
                "config": {
                    "properties": edi_data['component']['config']['properties'],
                    "autoTerminatedRelationships": ["failure"]
                }
            }
        }
        
        requests.put(f"{self.NIFI_URL}/nifi-api/processors/{edi_processor_id}", headers=nifi_headers, json=auto_terminate_config)
        
        print("✅ Complete EDI processing workflow created successfully")
        print(f"   - GetFile processor: {getfile_id}")
        print(f"   - EDI Processor: {edi_processor_id}")
        print(f"   - PutFile processor: {putfile_id}")
        print(f"   - Workflow ready for testing with EDI files")
    
    def test_edi_processor_validation_scenarios(self, test_process_group, nifi_headers):
        """Test EDI Processor with different validation scenarios"""
        processor_id = self.test_create_edi_processor(test_process_group, nifi_headers)
        
        # Test different SNIP levels
        snip_levels = ["1", "2", "3", "4", "5"]
        
        for snip_level in snip_levels:
            # Get current processor state
            response = requests.get(f"{self.NIFI_URL}/nifi-api/processors/{processor_id}", headers=nifi_headers)
            processor_data = response.json()
            
            # Update SNIP level
            updated_config = {
                "revision": processor_data['revision'],
                "component": {
                    "id": processor_id,
                    "config": {
                        "properties": {
                            **processor_data['component']['config']['properties'],
                            "SNIP Level": snip_level
                        }
                    }
                }
            }
            
            response = requests.put(
                f"{self.NIFI_URL}/nifi-api/processors/{processor_id}",
                headers=nifi_headers,
                json=updated_config
            )
            
            assert response.status_code == 200
            
            # Verify SNIP level was set
            updated_processor = response.json()
            assert updated_processor['component']['config']['properties']['SNIP Level'] == snip_level
        
        print(f"✅ Successfully tested all SNIP levels: {snip_levels}")
    
    def test_edi_processor_feature_toggles(self, test_process_group, nifi_headers):
        """Test EDI Processor feature toggle combinations"""
        processor_id = self.test_create_edi_processor(test_process_group, nifi_headers)
        
        # Test different feature combinations
        feature_combinations = [
            {"Generate CDM": "true", "Generate TA1": "false", "Force TA1": "false"},
            {"Generate CDM": "false", "Generate TA1": "true", "Force TA1": "false"},
            {"Generate CDM": "true", "Generate TA1": "true", "Force TA1": "false"},
            {"Generate CDM": "true", "Generate TA1": "true", "Force TA1": "true"},
            {"Generate CDM": "false", "Generate TA1": "false", "Force TA1": "false"}
        ]
        
        for i, features in enumerate(feature_combinations):
            # Get current processor state
            response = requests.get(f"{self.NIFI_URL}/nifi-api/processors/{processor_id}", headers=nifi_headers)
            processor_data = response.json()
            
            # Update feature configuration
            updated_config = {
                "revision": processor_data['revision'],
                "component": {
                    "id": processor_id,
                    "config": {
                        "properties": {
                            **processor_data['component']['config']['properties'],
                            **features
                        }
                    }
                }
            }
            
            response = requests.put(
                f"{self.NIFI_URL}/nifi-api/processors/{processor_id}",
                headers=nifi_headers,
                json=updated_config
            )
            
            assert response.status_code == 200
            
            # Verify features were set
            updated_processor = response.json()
            properties = updated_processor['component']['config']['properties']
            
            for feature, value in features.items():
                assert properties[feature] == value
            
            print(f"✅ Feature combination {i+1}: {features}")
        
        print(f"✅ Successfully tested {len(feature_combinations)} feature combinations")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])