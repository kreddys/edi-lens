"""
Template Seeder Service for EDI Lens.

This service provides automated seeding of workflow templates,
including built-in templates and custom tenant templates.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models.workflow_template import WorkflowTemplate, TemplateVersion
from src.nifi.services.built_in_templates_service import BuiltInTemplatesService
from src.core.database import get_db

logger = logging.getLogger(__name__)


class TemplateSeederService:
    """Service for seeding workflow templates."""

    def __init__(
        self,
        registry_url: str,
        registry_auth_token: Optional[str] = None
    ):
        self.built_in_templates_service = BuiltInTemplatesService(
            registry_url, registry_auth_token
        )

    async def seed_all_templates(self, session: AsyncSession) -> Dict[str, Any]:
        """Seed all templates including built-in and custom."""
        results = {
            "built_in": await self.seed_built_in_templates(session),
            "custom": [],  # TODO: Implement custom template seeding
            "total_seeded": 0,
            "total_skipped": 0,
            "total_errors": 0
        }
        
        # Count results
        results["total_seeded"] = len(results["built_in"]["seeded"])
        results["total_skipped"] = len(results["built_in"]["skipped"])
        results["total_errors"] = len(results["built_in"]["errors"])
        
        return results

    async def seed_built_in_templates(self, session: AsyncSession) -> Dict[str, Any]:
        """Seed all built-in templates."""
        return await self.built_in_templates_service.seed_built_in_templates(session)

    async def seed_custom_templates(
        self,
        session: AsyncSession,
        template_definitions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Seed custom templates from definitions."""
        results = {
            "seeded": [],
            "skipped": [],
            "errors": []
        }
        
        for template_data in template_definitions:
            try:
                result = await self._seed_custom_template(template_data, session)
                if result["status"] == "seeded":
                    results["seeded"].append(result)
                else:
                    results["skipped"].append(result)
            except Exception as e:
                results["errors"].append({
                    "template_id": template_data.get("template_id", "unknown"),
                    "error": str(e)
                })
        
        return results

    async def _seed_custom_template(
        self,
        template_data: Dict[str, Any],
        session: AsyncSession
    ) -> Dict[str, Any]:
        """Seed a single custom template."""
        # Validate required fields
        required_fields = ["template_id", "name", "description", "category", "flow_definition"]
        for field in required_fields:
            if field not in template_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Check if template already exists
        existing_query = select(WorkflowTemplate).where(
            WorkflowTemplate.template_id == template_data["template_id"]
        )
        existing_result = await session.execute(existing_query)
        existing_template = existing_result.scalar_one_or_none()
        
        if existing_template:
            return {
                "template_id": template_data["template_id"],
                "status": "skipped",
                "reason": "Template already exists"
            }
        
        # Set default values for optional fields
        template_data.setdefault("scope", "GLOBAL")
        template_data.setdefault("tenant_id", None)
        template_data.setdefault("maintainer", "template-seeder")
        template_data.setdefault("based_on", None)
        template_data.setdefault("version", "1.0")
        template_data.setdefault("deployment_method", "registry")
        template_data.setdefault("tags", [])
        template_data.setdefault("features", [])
        template_data.setdefault("documentation", "")
        template_data.setdefault("examples", {})
        template_data.setdefault("is_featured", False)
        template_data.setdefault("status", "ACTIVE")
        template_data.setdefault("configuration_schema", {})
        
        # Create template
        template = WorkflowTemplate(
            template_id=template_data["template_id"],
            name=template_data["name"],
            description=template_data["description"],
            category=template_data["category"],
            scope=template_data["scope"],
            tenant_id=template_data["tenant_id"],
            maintainer=template_data["maintainer"],
            based_on=template_data["based_on"],
            version=template_data["version"],
            flow_definition=template_data["flow_definition"],
            configuration_schema=template_data["configuration_schema"],
            deployment_method=template_data["deployment_method"],
            tags=template_data["tags"],
            features=template_data["features"],
            documentation=template_data["documentation"],
            examples=template_data["examples"],
            is_featured=template_data["is_featured"],
            status=template_data["status"]
        )
        
        session.add(template)
        
        # Create initial version
        initial_version = TemplateVersion(
            template_id=template_data["template_id"],
            version=template_data["version"],
            flow_definition=template_data["flow_definition"],
            configuration_schema=template_data["configuration_schema"],
            changes="Initial template version",
            created_by=template_data["maintainer"],
            is_current=True
        )
        
        session.add(initial_version)
        await session.commit()
        await session.refresh(template)
        
        return {
            "template_id": template_data["template_id"],
            "status": "seeded",
            "name": template_data["name"]
        }

    async def import_template_from_file(
        self,
        session: AsyncSession,
        file_path: str
    ) -> Dict[str, Any]:
        """Import a template from a JSON file."""
        # TODO: Implement template import from file
        raise NotImplementedError("Template import from file not yet implemented")

    async def export_template_to_file(
        self,
        session: AsyncSession,
        template_id: str,
        file_path: str
    ) -> bool:
        """Export a template to a JSON file."""
        # TODO: Implement template export to file
        raise NotImplementedError("Template export to file not yet implemented")

    async def register_all_templates_in_registry(self, session: AsyncSession) -> Dict[str, Any]:
        """Register all templates in NiFi Registry."""
        results = {
            "registered": [],
            "skipped": [],
            "errors": []
        }
        
        # Get all active templates
        query = select(WorkflowTemplate).where(
            WorkflowTemplate.status == "ACTIVE"
        )
        result = await session.execute(query)
        templates = result.scalars().all()
        
        for template in templates:
            try:
                success = await self.built_in_templates_service.register_template_in_registry(template)
                if success:
                    results["registered"].append({
                        "template_id": template.template_id,
                        "name": template.name
                    })
                else:
                    results["skipped"].append({
                        "template_id": template.template_id,
                        "name": template.name,
                        "reason": "Registration failed"
                    })
            except Exception as e:
                results["errors"].append({
                    "template_id": template.template_id,
                    "name": template.name,
                    "error": str(e)
                })
        
        return results

    async def seed_templates_from_directory(
        self,
        session: AsyncSession,
        templates_directory: str,
        include_patterns: List[str] = ["*.yaml", "*.yml"],
        exclude_patterns: Optional[List[str]] = None,
        continue_on_error: bool = True,
    ) -> Dict[str, Any]:
        """Seed templates from a directory of YAML files."""
        results = {
            "seeded": [],
            "skipped": [],
            "errors": [],
            "total_processed": 0,
        }

        template_files = []
        for pattern in include_patterns:
            template_files.extend(Path(templates_directory).rglob(pattern))

        for file_path in template_files:
            results["total_processed"] += 1
            try:
                template_data = self._load_template_from_file(file_path)
                result = await self._seed_custom_template(template_data, session)
                if result["status"] == "seeded":
                    results["seeded"].append(result)
                else:
                    results["skipped"].append(result)
            except Exception as e:
                logger.error(f"Failed to seed template from {file_path}: {e}")
                results["errors"].append({"file": str(file_path), "error": str(e)})
                if not continue_on_error:
                    break
        return results

    def _load_template_from_file(self, file_path: Path) -> Dict[str, Any]:
        """Load a template from a YAML file."""
        with open(file_path, "r") as f:
            return yaml.safe_load(f)