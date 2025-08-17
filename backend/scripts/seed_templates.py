#!/usr/bin/env python3
"""
Template Seeding CLI for EDI Lens.

This script provides command-line interface for seeding workflow templates,
including built-in templates and custom tenant templates.
"""

import argparse
import asyncio
import logging
import sys
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.nifi.services.template_seeder_service import TemplateSeederService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s'
)
logger = logging.getLogger(__name__)


async def seed_built_in_templates(force: bool = False) -> int:
    """Seed built-in templates."""
    try:
        logger.info("Seeding built-in templates...")
        
        # Initialize template seeder service
        seeder_service = TemplateSeederService(
            registry_url=settings.NIFI_REGISTRY_URL,
            registry_auth_token=settings.NIFI_REGISTRY_AUTH_TOKEN
        )
        
        # Get database session
        async for session in get_db():
            results = await seeder_service.seed_built_in_templates(session)
            
            # Log results
            logger.info(f"Seeded {len(results['seeded'])} templates:")
            for result in results['seeded']:
                logger.info(f"  - {result['name']} ({result['template_id']})")
            
            if results['skipped']:
                logger.info(f"Skipped {len(results['skipped'])} templates:")
                for result in results['skipped']:
                    logger.info(f"  - {result['template_id']}: {result['reason']}")
            
            if results['errors']:
                logger.error(f"Errors seeding {len(results['errors'])} templates:")
                for error in results['errors']:
                    logger.error(f"  - {error['template_id']}: {error['error']}")
            
            return len(results['errors'])
            
    except Exception as e:
        logger.error(f"Failed to seed built-in templates: {str(e)}")
        logger.exception("Full traceback:")
        return 1


async def seed_all_templates(force: bool = False) -> int:
    """Seed all templates (built-in and custom)."""
    try:
        logger.info("Seeding all templates...")
        
        # Initialize template seeder service
        seeder_service = TemplateSeederService(
            registry_url=settings.NIFI_REGISTRY_URL,
            registry_auth_token=settings.NIFI_REGISTRY_AUTH_TOKEN
        )
        
        # Get database session
        async for session in get_db():
            results = await seeder_service.seed_all_templates(session)
            
            # Log results
            logger.info("Built-in template results:")
            logger.info(f"  Seeded: {len(results['built_in']['seeded'])}")
            logger.info(f"  Skipped: {len(results['built_in']['skipped'])}")
            logger.info(f"  Errors: {len(results['built_in']['errors'])}")
            
            if results['built_in']['seeded']:
                logger.info("Seeded built-in templates:")
                for result in results['built_in']['seeded']:
                    logger.info(f"  - {result['name']} ({result['template_id']})")
            
            return results['total_errors']
            
    except Exception as e:
        logger.error(f"Failed to seed all templates: {str(e)}")
        return 1


async def import_template_from_file(file_path: str) -> int:
    """Import template from JSON file."""
    try:
        logger.info(f"Importing template from {file_path}...")
        
        # Initialize template seeder service
        seeder_service = TemplateSeederService(
            registry_url=settings.NIFI_REGISTRY_URL,
            registry_auth_token=settings.NIFI_REGISTRY_AUTH_TOKEN
        )
        
        # Get database session
        async for session in get_db():
            result = await seeder_service.import_template_from_file(session, file_path)
            logger.info(f"Import result: {result}")
            return 0
            
    except NotImplementedError:
        logger.error("Template import from file not yet implemented")
        return 1
    except Exception as e:
        logger.error(f"Failed to import template from {file_path}: {str(e)}")
        return 1


async def export_template_to_file(template_id: str, file_path: str) -> int:
    """Export template to JSON file."""
    try:
        logger.info(f"Exporting template {template_id} to {file_path}...")
        
        # Initialize template seeder service
        seeder_service = TemplateSeederService(
            registry_url=settings.NIFI_REGISTRY_URL,
            registry_auth_token=settings.NIFI_REGISTRY_AUTH_TOKEN
        )
        
        # Get database session
        async for session in get_db():
            result = await seeder_service.export_template_to_file(session, template_id, file_path)
            logger.info(f"Export result: {result}")
            return 0 if result else 1
            
    except NotImplementedError:
        logger.error("Template export to file not yet implemented")
        return 1
    except Exception as e:
        logger.error(f"Failed to export template {template_id} to {file_path}: {str(e)}")
        return 1


async def register_templates_in_registry() -> int:
    """Register all templates in NiFi Registry."""
    try:
        logger.info("Registering templates in NiFi Registry...")
        
        # Initialize template seeder service
        seeder_service = TemplateSeederService(
            registry_url=settings.NIFI_REGISTRY_URL,
            registry_auth_token=settings.NIFI_REGISTRY_AUTH_TOKEN
        )
        
        # Get database session
        async for session in get_db():
            results = await seeder_service.register_all_templates_in_registry(session)
            
            # Log results
            logger.info(f"Registered {len(results['registered'])} templates in NiFi Registry")
            logger.info(f"Skipped {len(results['skipped'])} templates")
            logger.info(f"Errors registering {len(results['errors'])} templates")
            
            if results['registered']:
                logger.info("Successfully registered templates:")
                for result in results['registered']:
                    logger.info(f"  - {result['name']} ({result['template_id']})")
            
            if results['errors']:
                logger.error("Errors during registration:")
                for error in results['errors']:
                    logger.error(f"  - {error['name']} ({error['template_id']}): {error['error']}")
            
            return len(results['errors'])
            
    except Exception as e:
        logger.error(f"Failed to register templates in NiFi Registry: {str(e)}")
        return 1


def main():
    """Main entry point for the template seeding CLI."""
    parser = argparse.ArgumentParser(
        description="EDI Lens Template Seeding CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Seed all built-in templates
  python -m scripts.seed_templates built-in

  # Seed all templates (built-in and custom)
  python -m scripts.seed_templates all

  # Import template from file
  python -m scripts.seed_templates import --file /path/to/template.json

  # Export template to file
  python -m scripts.seed_templates export --template-id global-sftp-edi-processor-v1.0 --file /path/to/output.json

  # Register all templates in NiFi Registry
  python -m scripts.seed_templates register

  # Force re-seeding (overwrites existing templates)
  python -m scripts.seed_templates built-in --force
        """
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        required=True
    )
    
    # Built-in templates command
    built_in_parser = subparsers.add_parser(
        "built-in",
        help="Seed built-in templates"
    )
    built_in_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-seeding of existing templates"
    )
    
    # All templates command
    all_parser = subparsers.add_parser(
        "all",
        help="Seed all templates (built-in and custom)"
    )
    all_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-seeding of existing templates"
    )
    
    # Import template command
    import_parser = subparsers.add_parser(
        "import",
        help="Import template from file"
    )
    import_parser.add_argument(
        "--file", "-f",
        required=True,
        help="Path to template JSON file"
    )
    
    # Export template command
    export_parser = subparsers.add_parser(
        "export",
        help="Export template to file"
    )
    export_parser.add_argument(
        "--template-id", "-t",
        required=True,
        help="Template ID to export"
    )
    export_parser.add_argument(
        "--file", "-f",
        required=True,
        help="Output file path"
    )
    
    # Register templates command
    register_parser = subparsers.add_parser(
        "register",
        help="Register all templates in NiFi Registry"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Execute command
    try:
        if args.command == "built-in":
            error_count = asyncio.run(seed_built_in_templates(args.force))
            sys.exit(error_count)
        elif args.command == "all":
            error_count = asyncio.run(seed_all_templates(args.force))
            sys.exit(error_count)
        elif args.command == "import":
            error_count = asyncio.run(import_template_from_file(args.file))
            sys.exit(error_count)
        elif args.command == "export":
            error_count = asyncio.run(export_template_to_file(args.template_id, args.file))
            sys.exit(error_count)
        elif args.command == "register":
            error_count = asyncio.run(register_templates_in_registry())
            sys.exit(error_count)
        else:
            logger.error(f"Unknown command: {args.command}")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()