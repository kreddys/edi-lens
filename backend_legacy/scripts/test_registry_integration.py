#!/usr/bin/env python3
"""
Test script for Registry-first architecture.

This script tests the basic functionality of the new Registry-first models
and services to ensure everything is working correctly.
"""

import asyncio
import sys
import logging
from uuid import uuid4

# Add the src directory to the path
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.core.config import settings
from src.services.registry_service import RegistryService
from src.models.registry_models import RegistryTemplate, WorkflowInstance, RegistryBucket

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class RegistryTester:
    """Test the Registry-first architecture."""
    
    def __init__(self):
        self.engine = None
        self.session_factory = None
    
    async def initialize(self):
        """Initialize database connection."""
        database_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        self.engine = create_async_engine(database_url, echo=False)
        self.session_factory = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        log.info("Database connection initialized")
    
    async def cleanup(self):
        """Cleanup database connection."""
        if self.engine:
            await self.engine.dispose()
            log.info("Database connection closed")
    
    async def test_template_creation(self):
        """Test creating a template in Registry."""
        log.info("=== Testing Template Creation ===")
        
        async with self.session_factory() as session:
            registry_service = RegistryService(session)
            
            # Sample flow definition
            flow_definition = {
                "processors": [
                    {
                        "id": "getfile-test",
                        "name": "Get Test Files",
                        "type": "org.apache.nifi.processors.standard.GetFile",
                        "position": {"x": 100, "y": 100},
                        "properties": {
                            "Input Directory": "/tmp/test-input",
                            "File Filter": ".*\\.txt"
                        }
                    },
                    {
                        "id": "logmessage-test",
                        "name": "Log Test Message",
                        "type": "org.apache.nifi.processors.standard.LogMessage",
                        "position": {"x": 400, "y": 100},
                        "properties": {}
                    }
                ],
                "connections": [
                    {
                        "id": "connection-test",
                        "source": {"id": "getfile-test"},
                        "destination": {"id": "logmessage-test"},
                        "selectedRelationships": ["success"]
                    }
                ]
            }
            
            try:
                template = await registry_service.create_template(
                    name="Test Registry Template",
                    description="A test template for Registry integration",
                    flow_definition=flow_definition,
                    scope="GLOBAL",
                    created_by="test-user"
                )
                
                log.info(f"✅ Template created successfully: {template.template_id}")
                log.info(f"   Name: {template.name}")
                log.info(f"   Bucket: {template.bucket_id}")
                log.info(f"   Version: {template.current_version}")
                
                return template
                
            except Exception as e:
                log.error(f"❌ Template creation failed: {str(e)}")
                return None
    
    async def test_workflow_instance_creation(self, template):
        """Test creating a workflow instance."""
        if not template:
            log.warning("Skipping workflow instance test - no template available")
            return None
            
        log.info("=== Testing Workflow Instance Creation ===")
        
        async with self.session_factory() as session:
            registry_service = RegistryService(session)
            
            try:
                workflow = await registry_service.create_workflow(
                    template_id=template.template_id,
                    name="Test Workflow Instance",
                    tenant_id="test-tenant",
                    configuration={
                        "input_directory": "/tmp/test-input",
                        "log_level": "INFO"
                    },
                    description="A test workflow instance",
                    created_by="test-user"
                )
                
                log.info(f"✅ Workflow instance created successfully: {workflow.workflow_id}")
                log.info(f"   Name: {workflow.name}")
                log.info(f"   Template: {workflow.template_id}")
                log.info(f"   Version: {workflow.template_version}")
                log.info(f"   Status: {workflow.status}")
                
                return workflow
                
            except Exception as e:
                log.error(f"❌ Workflow instance creation failed: {str(e)}")
                return None
    
    async def test_flow_definition_retrieval(self, template):
        """Test retrieving flow definition from Registry."""
        if not template:
            log.warning("Skipping flow definition test - no template available")
            return
            
        log.info("=== Testing Flow Definition Retrieval ===")
        
        async with self.session_factory() as session:
            registry_service = RegistryService(session)
            
            try:
                flow_definition = await registry_service.get_template_flow_definition(
                    template_id=template.template_id
                )
                
                log.info("✅ Flow definition retrieved successfully")
                log.info(f"   Processors: {len(flow_definition.get('processors', []))}")
                log.info(f"   Connections: {len(flow_definition.get('connections', []))}")
                
                # Verify structure
                processors = flow_definition.get('processors', [])
                if processors:
                    log.info(f"   First processor: {processors[0].get('name', 'Unknown')}")
                
            except Exception as e:
                log.error(f"❌ Flow definition retrieval failed: {str(e)}")
    
    async def test_template_listing(self):
        """Test listing templates."""
        log.info("=== Testing Template Listing ===")
        
        async with self.session_factory() as session:
            registry_service = RegistryService(session)
            
            try:
                # List all templates
                all_templates = await registry_service.list_templates()
                log.info(f"✅ Found {len(all_templates)} total templates")
                
                # List global templates
                global_templates = await registry_service.list_templates(scope="GLOBAL")
                log.info(f"✅ Found {len(global_templates)} global templates")
                
                # List tenant templates
                tenant_templates = await registry_service.list_templates(scope="TENANT", tenant_id="test-tenant")
                log.info(f"✅ Found {len(tenant_templates)} tenant templates")
                
            except Exception as e:
                log.error(f"❌ Template listing failed: {str(e)}")
    
    async def test_workflow_listing(self):
        """Test listing workflow instances."""
        log.info("=== Testing Workflow Instance Listing ===")
        
        async with self.session_factory() as session:
            registry_service = RegistryService(session)
            
            try:
                # List all workflows
                all_workflows = await registry_service.list_workflow_instances()
                log.info(f"✅ Found {len(all_workflows)} total workflow instances")
                
                # List tenant workflows
                tenant_workflows = await registry_service.list_workflow_instances(tenant_id="test-tenant")
                log.info(f"✅ Found {len(tenant_workflows)} tenant workflow instances")
                
            except Exception as e:
                log.error(f"❌ Workflow instance listing failed: {str(e)}")
    
    async def run_all_tests(self):
        """Run all tests."""
        log.info("Starting Registry-first architecture tests...")
        
        try:
            await self.initialize()
            
            # Test template creation
            template = await self.test_template_creation()
            
            # Test workflow instance creation
            workflow = await self.test_workflow_instance_creation(template)
            
            # Test flow definition retrieval
            await self.test_flow_definition_retrieval(template)
            
            # Test listing operations
            await self.test_template_listing()
            await self.test_workflow_listing()
            
            log.info("✅ All tests completed!")
            
        except Exception as e:
            log.error(f"❌ Test suite failed: {str(e)}")
            raise
        finally:
            await self.cleanup()


async def main():
    """Main test function."""
    tester = RegistryTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())