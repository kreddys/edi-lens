#!/usr/bin/env python3
"""
Migration script to transition from old workflow template model to Registry-first architecture.

This script:
1. Migrates existing WorkflowTemplate records to NiFi Registry
2. Creates RegistryTemplate references in the new model
3. Migrates existing Workflow records to WorkflowInstance model
4. Preserves all metadata and relationships

Usage:
    python migrate_to_registry.py [--dry-run] [--batch-size=50]
"""

import asyncio
import argparse
import logging
import sys
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4

# Add the backend src directory to the path
sys.path.insert(0, '/app/backend/src')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from src.core.config import settings
from src.models.workflow_template import WorkflowTemplate, Workflow  # Old models
from src.models.registry_models import RegistryTemplate, WorkflowInstance, RegistryBucket  # New models
from src.services.registry_service import RegistryService
from src.nifi.clients.registry_client import NiFiRegistryClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)


class RegistryMigrationError(Exception):
    """Exception raised during migration."""
    pass


class RegistryMigrator:
    """Handles migration from old model to Registry-first architecture."""
    
    def __init__(self, dry_run: bool = True, batch_size: int = 50):
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.engine = None
        self.session_factory = None
        
        # Migration statistics
        self.stats = {
            "templates_processed": 0,
            "templates_migrated": 0,
            "templates_failed": 0,
            "workflows_processed": 0,
            "workflows_migrated": 0,
            "workflows_failed": 0,
            "errors": []
        }
    
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
    
    async def migrate_all(self):
        """Run complete migration process."""
        log.info(f"Starting Registry migration (dry_run={self.dry_run})")
        
        try:
            await self.initialize()
            
            # Step 1: Migrate templates
            log.info("=== Step 1: Migrating Templates ===")
            await self.migrate_templates()
            
            # Step 2: Migrate workflows
            log.info("=== Step 2: Migrating Workflows ===")
            await self.migrate_workflows()
            
            # Step 3: Print summary
            self.print_migration_summary()
            
        except Exception as e:
            log.error(f"Migration failed: {str(e)}")
            raise
        finally:
            await self.cleanup()
    
    async def migrate_templates(self):
        """Migrate WorkflowTemplate records to Registry and RegistryTemplate."""
        async with self.session_factory() as session:
            # Get all active templates
            query = select(WorkflowTemplate).where(WorkflowTemplate.status == 'ACTIVE')
            result = await session.execute(query)
            old_templates = result.scalars().all()
            
            log.info(f"Found {len(old_templates)} templates to migrate")
            
            for template in old_templates:
                try:
                    await self.migrate_single_template(template, session)
                    self.stats["templates_processed"] += 1
                    
                    if not self.dry_run and self.stats["templates_processed"] % self.batch_size == 0:
                        await session.commit()
                        log.info(f"Committed batch of {self.batch_size} templates")
                        
                except Exception as e:
                    error_msg = f"Failed to migrate template {template.template_id}: {str(e)}"
                    log.error(error_msg)
                    self.stats["errors"].append(error_msg)
                    self.stats["templates_failed"] += 1
                    
                    if not self.dry_run:
                        await session.rollback()
            
            if not self.dry_run:
                await session.commit()
                log.info("Final template migration commit completed")
    
    async def migrate_single_template(self, old_template: WorkflowTemplate, session: AsyncSession):
        """Migrate a single template to Registry."""
        log.info(f"Migrating template: {old_template.name} ({old_template.template_id})")
        
        if self.dry_run:
            log.info(f"[DRY RUN] Would migrate template {old_template.name}")
            self.stats["templates_migrated"] += 1
            return
        
        try:
            # Create template in Registry using RegistryService
            registry_service = RegistryService(session)
            
            # Convert old template to Registry format
            new_template = await registry_service.create_template(
                name=old_template.name,
                description=old_template.description,
                flow_definition=old_template.flow_definition,
                scope=old_template.scope,
                tenant_id=old_template.tenant_id,
                created_by=old_template.maintainer
            )
            
            log.info(f"Created Registry template {new_template.template_id} for {old_template.name}")
            
            # Store mapping for workflow migration
            self.template_id_mapping = getattr(self, 'template_id_mapping', {})
            self.template_id_mapping[old_template.template_id] = str(new_template.template_id)
            
            self.stats["templates_migrated"] += 1
            
        except Exception as e:
            log.error(f"Failed to migrate template {old_template.template_id}: {str(e)}")
            raise
    
    async def migrate_workflows(self):
        """Migrate Workflow records to WorkflowInstance."""
        async with self.session_factory() as session:
            # Get all workflows
            query = select(Workflow).where(Workflow.status != 'DELETED')
            result = await session.execute(query)
            old_workflows = result.scalars().all()
            
            log.info(f"Found {len(old_workflows)} workflows to migrate")
            
            for workflow in old_workflows:
                try:
                    await self.migrate_single_workflow(workflow, session)
                    self.stats["workflows_processed"] += 1
                    
                    if not self.dry_run and self.stats["workflows_processed"] % self.batch_size == 0:
                        await session.commit()
                        log.info(f"Committed batch of {self.batch_size} workflows")
                        
                except Exception as e:
                    error_msg = f"Failed to migrate workflow {workflow.workflow_id}: {str(e)}"
                    log.error(error_msg)
                    self.stats["errors"].append(error_msg)
                    self.stats["workflows_failed"] += 1
                    
                    if not self.dry_run:
                        await session.rollback()
            
            if not self.dry_run:
                await session.commit()
                log.info("Final workflow migration commit completed")
    
    async def migrate_single_workflow(self, old_workflow: Workflow, session: AsyncSession):
        """Migrate a single workflow to WorkflowInstance."""
        log.info(f"Migrating workflow: {old_workflow.name} ({old_workflow.workflow_id})")
        
        if self.dry_run:
            log.info(f"[DRY RUN] Would migrate workflow {old_workflow.name}")
            self.stats["workflows_migrated"] += 1
            return
        
        try:
            # Get the new template ID from mapping
            template_id_mapping = getattr(self, 'template_id_mapping', {})
            new_template_id = template_id_mapping.get(old_workflow.template_id)
            
            if not new_template_id:
                raise ValueError(f"No Registry template found for old template {old_workflow.template_id}")
            
            # Create WorkflowInstance
            new_workflow = WorkflowInstance(
                workflow_id=old_workflow.workflow_id,  # Keep same ID
                name=old_workflow.name,
                description=old_workflow.description,
                tenant_id=old_workflow.tenant_id,
                template_id=UUID(new_template_id),
                template_version=1,  # Start with version 1
                configuration=old_workflow.configuration,
                nifi_process_group_id=UUID(old_workflow.nifi_process_group_id) if old_workflow.nifi_process_group_id else None,
                nifi_parameter_context_id=UUID(old_workflow.nifi_parameter_context_id) if old_workflow.nifi_parameter_context_id else None,
                status=self.map_workflow_status(old_workflow.status),
                created_by=old_workflow.created_by,
                created_at=old_workflow.created_at,
                updated_at=old_workflow.updated_at
            )
            
            # Set deployment timestamp if deployed
            if old_workflow.nifi_process_group_id:
                new_workflow.deployed_at = old_workflow.created_at  # Approximate
            
            session.add(new_workflow)
            
            log.info(f"Created WorkflowInstance {new_workflow.workflow_id} for {old_workflow.name}")
            self.stats["workflows_migrated"] += 1
            
        except Exception as e:
            log.error(f"Failed to migrate workflow {old_workflow.workflow_id}: {str(e)}")
            raise
    
    def map_workflow_status(self, old_status: str) -> str:
        """Map old workflow status to new status."""
        status_mapping = {
            "ACTIVE": "RUNNING",
            "PAUSED": "STOPPED", 
            "ERROR": "ERROR",
            "DELETED": "DELETED"
        }
        return status_mapping.get(old_status, "CREATED")
    
    def print_migration_summary(self):
        """Print migration summary."""
        log.info("=== Migration Summary ===")
        log.info(f"Templates processed: {self.stats['templates_processed']}")
        log.info(f"Templates migrated: {self.stats['templates_migrated']}")
        log.info(f"Templates failed: {self.stats['templates_failed']}")
        log.info(f"Workflows processed: {self.stats['workflows_processed']}")
        log.info(f"Workflows migrated: {self.stats['workflows_migrated']}")
        log.info(f"Workflows failed: {self.stats['workflows_failed']}")
        
        if self.stats["errors"]:
            log.error(f"Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats["errors"][:10]:  # Show first 10 errors
                log.error(f"  - {error}")
            if len(self.stats["errors"]) > 10:
                log.error(f"  ... and {len(self.stats['errors']) - 10} more errors")
        
        if self.dry_run:
            log.info("This was a DRY RUN - no changes were made to the database")
        else:
            log.info("Migration completed successfully!")


async def main():
    """Main migration function."""
    parser = argparse.ArgumentParser(description="Migrate to Registry-first architecture")
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        default=True,
        help="Perform a dry run without making changes (default: True)"
    )
    parser.add_argument(
        "--execute", 
        action="store_true", 
        help="Actually execute the migration (overrides --dry-run)"
    )
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=50,
        help="Number of records to process in each batch (default: 50)"
    )
    
    args = parser.parse_args()
    
    # Determine if this is a dry run
    dry_run = not args.execute
    
    if dry_run:
        log.info("Running in DRY RUN mode - no changes will be made")
        log.info("Use --execute flag to actually perform the migration")
    else:
        log.warning("EXECUTING MIGRATION - this will make permanent changes!")
        response = input("Are you sure you want to proceed? (yes/no): ")
        if response.lower() != "yes":
            log.info("Migration cancelled")
            return
    
    # Run migration
    migrator = RegistryMigrator(dry_run=dry_run, batch_size=args.batch_size)
    await migrator.migrate_all()


if __name__ == "__main__":
    asyncio.run(main())