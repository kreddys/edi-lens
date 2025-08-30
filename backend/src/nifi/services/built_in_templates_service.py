"""
Built-in Templates Service for EDI Lens.

This service manages the built-in workflow templates that provide
out-of-box functionality for common EDI processing patterns.
Templates are loaded from YAML files in the data/templates directory.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.registry_models import RegistryTemplate
from src.services.registry_service import RegistryService

logger = logging.getLogger(__name__)


class BuiltInTemplatesService:
    """Service for managing built-in workflow templates loaded from YAML files."""

    def __init__(self, registry_url: str, registry_auth_token: Optional[str] = None, templates_dir: Optional[str] = None, timeout: int = 30):
        self.registry_url = registry_url
        self.registry_auth_token = registry_auth_token
        self.timeout = timeout
        
        # Default to backend/data/templates/builtin directory
        if templates_dir is None:
            # Get the project root directory (assuming this file is in backend/src/nifi/services/)
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent.parent  # Go up 4 levels
            self.templates_dir = project_root / "data" / "templates" / "builtin"
        else:
            self.templates_dir = Path(templates_dir)
        
        logger.info(f"Built-in templates directory: {self.templates_dir}")

    # --- Template Loading Methods ---

    def _load_template_from_yaml(self, yaml_file: Path) -> Dict[str, Any]:
        """Load a template definition from a YAML file."""
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                template_data = yaml.safe_load(f)
            
            # Validate required sections
            if 'metadata' not in template_data:
                raise ValueError(f"Template {yaml_file} missing 'metadata' section")
            if 'flow_definition' not in template_data:
                raise ValueError(f"Template {yaml_file} missing 'flow_definition' section")
            if 'configuration_schema' not in template_data:
                raise ValueError(f"Template {yaml_file} missing 'configuration_schema' section")
            
            # Merge metadata into template structure
            template = template_data['metadata'].copy()
            template['flow_definition'] = template_data['flow_definition']
            template['configuration_schema'] = template_data['configuration_schema']
            
            # Add UI configuration if present
            if 'ui_configuration' in template_data:
                template['ui_configuration'] = template_data['ui_configuration']
            
            # Add processing capabilities if present
            if 'processing_capabilities' in template_data:
                template['processing_capabilities'] = template_data['processing_capabilities']
            
            # Add supported file types if present
            if 'supported_file_types' in template_data:
                template['supported_file_types'] = template_data['supported_file_types']
            
            # Add use cases if present
            if 'use_cases' in template_data:
                template['use_cases'] = template_data['use_cases']
            
            # Add industry tags if present
            if 'industry_tags' in template_data:
                template['industry_tags'] = template_data['industry_tags']
            
            # Add source file information
            template['_source_file'] = str(yaml_file)
            
            logger.info(f"Loaded template '{template['name']}' from {yaml_file}")
            return template
            
        except Exception as e:
            logger.error(f"Failed to load template from {yaml_file}: {str(e)}")
            raise

    def _discover_template_files(self) -> List[Path]:
        """Discover all YAML template files in the templates directory."""
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory does not exist: {self.templates_dir}")
            return []
        
        yaml_files = []
        for pattern in ['*.yaml', '*.yml']:
            yaml_files.extend(self.templates_dir.glob(pattern))
        
        # Filter out README files
        template_files = [f for f in yaml_files if not f.name.lower().startswith('readme')]
        
        logger.info(f"Discovered {len(template_files)} template files: {[f.name for f in template_files]}")
        return template_files

    def get_all_built_in_templates(self) -> List[Dict[str, Any]]:
        """Get all built-in template definitions from YAML files."""
        templates = []
        template_files = self._discover_template_files()
        
        for template_file in template_files:
            try:
                template = self._load_template_from_yaml(template_file)
                templates.append(template)
            except Exception as e:
                logger.error(f"Failed to load template from {template_file}: {str(e)}")
                # Continue loading other templates even if one fails
        
        logger.info(f"Loaded {len(templates)} built-in templates from YAML files")
        return templates

    def get_template_by_id(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific template by its ID."""
        templates = self.get_all_built_in_templates()
        for template in templates:
            if template.get('template_id') == template_id:
                return template
        return None

    def reload_templates(self) -> List[Dict[str, Any]]:
        """Reload all templates from YAML files (useful for development)."""
        logger.info("Reloading all templates from YAML files")
        return self.get_all_built_in_templates()

    # --- Template Seeding Methods ---

    async def seed_built_in_templates(self, session: AsyncSession) -> Dict[str, Any]:
        """Seed all built-in templates into the database."""
        results = {
            "seeded": [],
            "skipped": [],
            "errors": []
        }
        
        templates = self.get_all_built_in_templates()
        
        for template_data in templates:
            try:
                result = await self._seed_template(template_data, session)
                if result["status"] == "seeded":
                    results["seeded"].append(result)
                elif result["status"] == "skipped":
                    results["skipped"].append(result)
                elif result["status"] == "error":
                    results["errors"].append(result)
                else:
                    # Fallback for unknown status
                    results["skipped"].append(result)
            except Exception as e:
                results["errors"].append({
                    "template_id": template_data.get("template_id", "unknown"),
                    "name": template_data.get("name", "unknown"),
                    "error": str(e)
                })
        
        return results

    async def _seed_template(self, template_data: Dict[str, Any], session: AsyncSession) -> Dict[str, Any]:
        """Seed a single template into the database using Registry-first architecture."""
        try:
            registry_service = RegistryService(session)
            
            # Check if template already exists in database (for idempotency)
            existing_templates = await registry_service.list_templates(
                scope=template_data["scope"], 
                tenant_id=template_data.get("tenant_id")
            )
            
            for existing in existing_templates:
                if existing.name == template_data["name"]:
                    return {
                        "template_id": str(existing.template_id),
                        "status": "skipped",
                        "reason": "Template already exists",
                        "name": existing.name
                    }
            
            # Create template using Registry service (handles Registry idempotency internally)
            template = await registry_service.create_template(
                name=template_data["name"],
                description=template_data["description"],
                flow_definition=template_data["flow_definition"],
                scope=template_data["scope"],
                tenant_id=template_data.get("tenant_id"),
                created_by=template_data.get("maintainer", "system")
            )
        
            
            return {
                "template_id": str(template.template_id),
                "status": "seeded",
                "name": template.name
            }
            
        except Exception as e:
            logger.error(f"Failed to seed template {template_data.get('name')}: {str(e)}")
            return {
                "template_id": template_data.get("template_id", "unknown"),
                "name": template_data.get("name", "unknown"),
                "status": "error",
                "error": str(e)
            }

    async def register_template_in_registry(
        self,
        template: RegistryTemplate
    ) -> bool:
        """Register a template in NiFi Registry - already done during seeding in Registry-first architecture."""
        # In Registry-first architecture, templates are already registered in Registry during creation
        # This method is kept for backward compatibility but just returns True
        logger.info(f"Template {template.template_id} is already registered in Registry")
        return True