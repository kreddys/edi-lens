#!/usr/bin/env python3
"""
Registry-First Template Seeding CLI for EDI Lens.

This script seeds templates using the new Registry-first architecture where
templates are stored in NiFi Registry and the database contains only references.
"""

import argparse
import asyncio
import logging
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, List
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.core.config import settings
from src.services.registry_service import RegistryService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s'
)
logger = logging.getLogger(__name__)


class RegistryTemplateSeeder:
    """Registry-first template seeding service."""
    
    def __init__(self):
        self.builtin_templates_dir = Path("/home/appuser/app/data/templates/builtin")
        
    async def seed_builtin_templates(self, force: bool = False) -> Dict[str, Any]:
        """Seed built-in templates using Registry-first architecture."""
        results = {
            "seeded": [],
            "skipped": [],
            "errors": [],
            "total_processed": 0
        }
        
        # Setup database connection
        database_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(database_url, echo=False)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        try:
            async with session_factory() as session:
                registry_service = RegistryService(session)
                
                # Find all template YAML files
                template_files = list(self.builtin_templates_dir.glob("*.yaml")) + list(self.builtin_templates_dir.glob("*.yml"))
                logger.info(f"Found {len(template_files)} template files in {self.builtin_templates_dir}")
                
                for template_file in template_files:
                    results["total_processed"] += 1
                    try:
                        # Load template from YAML
                        template_data = self._load_template_from_yaml(template_file)
                        logger.info(f"Loaded template '{template_data['name']}' from {template_file}")
                        
                        # Check if template already exists (by name for now)
                        existing_templates = await registry_service.list_templates(scope=template_data.get("scope", "GLOBAL"))
                        existing_template = next(
                            (t for t in existing_templates if t.name == template_data["name"]), 
                            None
                        )
                        
                        if existing_template and not force:
                            results["skipped"].append({
                                "name": template_data["name"],
                                "file": str(template_file),
                                "reason": "Template already exists (use --force to overwrite)"
                            })
                            logger.info(f"Skipped '{template_data['name']}' - already exists")
                            continue
                        
                        # Create template in Registry
                        if existing_template and force:
                            # Update existing template
                            updated_template = await registry_service.update_template(
                                template_id=existing_template.template_id,
                                flow_definition=template_data["flow_definition"],
                                comments=f"Updated from {template_file.name}",
                                updated_by="template-seeder"
                            )
                            results["seeded"].append({
                                "name": template_data["name"],
                                "template_id": str(updated_template.template_id),
                                "version": updated_template.current_version,
                                "action": "updated"
                            })
                            logger.info(f"Updated template '{template_data['name']}' to version {updated_template.current_version}")
                        else:
                            # Create new template
                            new_template = await registry_service.create_template(
                                name=template_data["name"],
                                description=template_data["description"],
                                flow_definition=template_data["flow_definition"],
                                scope=template_data.get("scope", "GLOBAL"),
                                tenant_id=template_data.get("tenant_id"),
                                created_by="template-seeder"
                            )
                            results["seeded"].append({
                                "name": template_data["name"],
                                "template_id": str(new_template.template_id),
                                "version": new_template.current_version,
                                "action": "created"
                            })
                            logger.info(f"Created template '{template_data['name']}' with ID {new_template.template_id}")
                        
                    except Exception as e:
                        error_msg = f"Failed to seed template from {template_file}: {str(e)}"
                        logger.error(error_msg)
                        results["errors"].append({
                            "file": str(template_file),
                            "error": str(e)
                        })
                        
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            results["errors"].append({
                "file": "database",
                "error": str(e)
            })
        finally:
            await engine.dispose()
        
        return results
    
    def _load_template_from_yaml(self, file_path: Path) -> Dict[str, Any]:
        """Load template definition from YAML file."""
        with open(file_path, 'r') as f:
            raw_data = yaml.safe_load(f)
        
        # Handle nested structure - extract metadata and flow_definition
        if "metadata" in raw_data and "flow_definition" in raw_data:
            # New format with metadata section
            template_data = {
                "name": raw_data["metadata"]["name"],
                "description": raw_data["metadata"]["description"],
                "scope": raw_data["metadata"].get("scope", "GLOBAL"),
                "tenant_id": raw_data["metadata"].get("tenant_id"),
                "flow_definition": raw_data["flow_definition"]
            }
        else:
            # Old format with fields at root level
            template_data = raw_data
        
        # Validate required fields
        required_fields = ["name", "description", "flow_definition"]
        for field in required_fields:
            if field not in template_data:
                raise ValueError(f"Missing required field '{field}' in {file_path}")
        
        return template_data
    
    async def list_registry_templates(self) -> Dict[str, Any]:
        """List all templates in the Registry-first system."""
        results = {
            "global_templates": [],
            "tenant_templates": [],
            "total_count": 0
        }
        
        # Setup database connection
        database_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(database_url, echo=False)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        try:
            async with session_factory() as session:
                registry_service = RegistryService(session)
                
                # Get global templates
                global_templates = await registry_service.list_templates(scope="GLOBAL")
                for template in global_templates:
                    results["global_templates"].append({
                        "name": template.name,
                        "template_id": str(template.template_id),
                        "version": template.current_version,
                        "status": template.status,
                        "created_at": template.created_at.isoformat()
                    })
                
                # Get tenant templates
                tenant_templates = await registry_service.list_templates(scope="TENANT")
                for template in tenant_templates:
                    results["tenant_templates"].append({
                        "name": template.name,
                        "template_id": str(template.template_id),
                        "version": template.current_version,
                        "tenant_id": template.tenant_id,
                        "status": template.status,
                        "created_at": template.created_at.isoformat()
                    })
                
                results["total_count"] = len(global_templates) + len(tenant_templates)
                
        except Exception as e:
            logger.error(f"Failed to list templates: {str(e)}")
            raise
        finally:
            await engine.dispose()
        
        return results


async def main():
    """Main entry point for Registry-first template seeding."""
    parser = argparse.ArgumentParser(
        description="Registry-First Template Seeding CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Seed built-in templates using Registry-first architecture
  python scripts/seed_registry_templates.py seed --builtin
  
  # Force re-seed (overwrite existing templates)
  python scripts/seed_registry_templates.py seed --builtin --force
  
  # List all templates in Registry system
  python scripts/seed_registry_templates.py list
        """
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)
    
    # Seed command
    seed_parser = subparsers.add_parser("seed", help="Seed templates")
    seed_parser.add_argument("--builtin", action="store_true", help="Seed built-in templates")
    seed_parser.add_argument("--force", "-f", action="store_true", help="Force overwrite existing templates")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all Registry templates")
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize seeder
    seeder = RegistryTemplateSeeder()
    
    try:
        if args.command == "seed":
            if args.builtin:
                logger.info("Seeding built-in templates using Registry-first architecture...")
                results = await seeder.seed_builtin_templates(force=args.force)
                
                # Print results
                logger.info(f"Seeding completed:")
                logger.info(f"  Processed: {results['total_processed']} files")
                logger.info(f"  Seeded: {len(results['seeded'])} templates")
                logger.info(f"  Skipped: {len(results['skipped'])} templates")
                logger.info(f"  Errors: {len(results['errors'])} templates")
                
                if results["seeded"]:
                    logger.info("Successfully seeded templates:")
                    for result in results["seeded"]:
                        logger.info(f"  - {result['name']} ({result['template_id']}) v{result['version']} [{result['action']}]")
                
                if results["skipped"]:
                    logger.info("Skipped templates:")
                    for result in results["skipped"]:
                        logger.info(f"  - {result['name']}: {result['reason']}")
                
                if results["errors"]:
                    logger.error("Errors:")
                    for error in results["errors"]:
                        logger.error(f"  - {error['file']}: {error['error']}")
                
                sys.exit(len(results["errors"]))
            else:
                logger.error("Please specify --builtin to seed built-in templates")
                sys.exit(1)
                
        elif args.command == "list":
            logger.info("Listing Registry templates...")
            results = await seeder.list_registry_templates()
            
            logger.info(f"Total templates: {results['total_count']}")
            
            if results["global_templates"]:
                logger.info(f"Global templates ({len(results['global_templates'])}):")
                for template in results["global_templates"]:
                    logger.info(f"  - {template['name']} ({template['template_id']}) v{template['version']}")
            
            if results["tenant_templates"]:
                logger.info(f"Tenant templates ({len(results['tenant_templates'])}):")
                for template in results["tenant_templates"]:
                    logger.info(f"  - {template['name']} ({template['template_id']}) v{template['version']} [tenant: {template['tenant_id']}]")
            
            if not results["global_templates"] and not results["tenant_templates"]:
                logger.info("No templates found in Registry system")
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())