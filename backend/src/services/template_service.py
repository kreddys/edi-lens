"""
Template Service for NiFi Registry integration and template management.

This service implements the Registry-first architecture where NiFi Registry
is the source of truth for flow definitions, and the database stores only
references and metadata. Handles all template operations including built-in template seeding.
"""

import logging
import uuid
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.models.registry_models import RegistryTemplate, RegistryBucket
from src.nifi.clients.registry_client import NiFiRegistryClient

log = logging.getLogger(__name__)


class TemplateServiceError(Exception):
    """Exception raised for Template service errors."""
    pass


class TemplateService:
    """Service for managing templates and NiFi Registry integration."""

    def __init__(self, session: AsyncSession, templates_dir: Optional[str] = None):
        self.session = session
        # Set up built-in templates directory
        if templates_dir is None:
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            self.templates_dir = project_root / "data" / "templates" / "builtin"
        else:
            self.templates_dir = Path(templates_dir)

    # === Template CRUD Operations ===

    async def create_template(
        self,
        name: str,
        description: str,
        flow_definition: Dict[str, Any],
        scope: str = "GLOBAL",
        tenant_id: Optional[str] = None,
        category: str = "GENERAL",
        version: str = "1.0.0",
        configuration_schema: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None
    ) -> RegistryTemplate:
        """Create a new template in both database and NiFi Registry."""
        try:
            # Create bucket if needed
            bucket = await self._ensure_bucket_exists(scope, tenant_id)
            
            # Create template in NiFi Registry first
            async with NiFiRegistryClient(
                settings.NIFI_REGISTRY_URL, 
                settings.NIFI_REGISTRY_AUTH_TOKEN
            ) as registry_client:
                # Create flow in Registry
                registry_flow = await registry_client.create_flow(
                    bucket_id=str(bucket.bucket_id),
                    flow_name=name,
                    flow_description=description
                )
                
                registry_flow_id = registry_flow["identifier"]
                
                # Upload flow definition as first version
                await registry_client.create_flow_version(
                    bucket_id=str(bucket.bucket_id),
                    flow_id=registry_flow_id,
                    version_data=flow_definition,
                    comments=f"Initial version {version}"
                )
            
            # Create template record in database using the Registry flow ID
            template = RegistryTemplate(
                template_id=UUID(registry_flow_id),
                name=name,
                description=description,
                bucket_id=bucket.bucket_id,
                current_version=1,  # First version 
                scope=scope,
                tenant_id=tenant_id,
                status="ACTIVE",
                usage_count=0,
                created_by=created_by
            )
            
            self.session.add(template)
            await self.session.commit()
            await self.session.refresh(template)
            
            log.info(f"Created template {name} ({registry_flow_id}) in Registry and database")
            return template
            
        except Exception as e:
            await self.session.rollback()
            log.error(f"Failed to create template {name}: {str(e)}")
            log.error(f"Exception type: {type(e).__name__}")
            log.error(f"Exception details: {repr(e)}")
            
            # Preserve detailed error information from NiFi Registry
            error_msg = str(e)
            if hasattr(e, 'response'):
                try:
                    response_text = e.response.text if hasattr(e.response, 'text') else str(e.response)
                    error_msg = f"{error_msg} - Response: {response_text}"
                except:
                    pass
            
            raise TemplateServiceError(f"Failed to create template: {error_msg}")

    async def update_template(
        self,
        template_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        flow_definition: Optional[Dict[str, Any]] = None,
        configuration_schema: Optional[Dict[str, Any]] = None,
        comments: Optional[str] = None
    ) -> RegistryTemplate:
        """Update an existing template and create new version in Registry if flow changed."""
        try:
            template = await self.get_template(template_id)
            if not template:
                raise TemplateServiceError(f"Template {template_id} not found")
            
            # Update basic fields
            if name is not None:
                template.name = name
            if description is not None:
                template.description = description
            if configuration_schema is not None:
                template.configuration_schema = configuration_schema
            
            # If flow definition changed, create new version in Registry
            if flow_definition is not None:
                # Increment version number
                new_version = template.current_version + 1
                
                bucket = await self._get_bucket_by_id(template.bucket_id)
                
                async with NiFiRegistryClient(
                    settings.NIFI_REGISTRY_URL,
                    settings.NIFI_REGISTRY_AUTH_TOKEN
                ) as registry_client:
                    # Create new version in Registry
                    await registry_client.create_flow_version(
                        bucket_id=str(bucket.bucket_id),
                        flow_id=str(template.template_id),
                        version_data=flow_definition,
                        comments=comments or f"Updated to version {new_version}"
                    )
                
                template.flow_definition = flow_definition
                template.current_version = new_version
            
            await self.session.commit()
            await self.session.refresh(template)
            
            return template
            
        except Exception as e:
            await self.session.rollback()
            log.error(f"Failed to update template {template_id}: {str(e)}")
            raise TemplateServiceError(f"Failed to update template: {str(e)}")

    async def get_template(self, template_id: UUID) -> Optional[RegistryTemplate]:
        """Get a template by ID."""
        query = select(RegistryTemplate).where(RegistryTemplate.template_id == template_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_templates(
        self,
        tenant_id: Optional[str] = None,
        scope: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[RegistryTemplate]:
        """List templates with optional filtering."""
        query = select(RegistryTemplate).options(selectinload(RegistryTemplate.bucket))
        
        if tenant_id:
            query = query.where(
                (RegistryTemplate.tenant_id == tenant_id) | 
                (RegistryTemplate.scope == "GLOBAL")
            )
        
        if scope:
            query = query.where(RegistryTemplate.scope == scope)
            
        if category:
            query = query.where(RegistryTemplate.category == category)
        
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def delete_template(self, template_id: UUID) -> bool:
        """Soft delete a template (mark as inactive)."""
        template = await self.get_template(template_id)
        if not template:
            return False
        
        template.status = "INACTIVE"
        await self.session.commit()
        return True

    async def get_template_flow_definition(
        self, 
        template_id: UUID, 
        version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get flow definition for a template from Registry."""
        try:
            template = await self.get_template(template_id)
            if not template:
                return None
            
            target_version = version or template.current_version
            bucket = await self._get_bucket_by_id(template.bucket_id)
            
            async with NiFiRegistryClient(
                settings.NIFI_REGISTRY_URL,
                settings.NIFI_REGISTRY_AUTH_TOKEN
            ) as registry_client:
                flow_version = await registry_client.get_flow_version(
                    bucket_id=str(bucket.bucket_id),
                    flow_id=str(template.template_id),
                    version=target_version
                )
                return flow_version.get("flowContents", {})
                
        except Exception as e:
            log.error(f"Failed to get flow definition for template {template_id}: {str(e)}")
            return None

    # === Built-in Template Management ===

    def _load_template_from_yaml(self, yaml_file: Path) -> Dict[str, Any]:
        """Load a template definition from a YAML file."""
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                template_data = yaml.safe_load(f)

            required_sections = ['metadata', 'flow_definition', 'configuration_schema']
            for section in required_sections:
                if section not in template_data:
                    raise ValueError(f"Template {yaml_file} missing '{section}' section")

            template = template_data['metadata'].copy()
            template['flow_definition'] = template_data['flow_definition']
            template['configuration_schema'] = template_data['configuration_schema']

            return template
        except Exception as e:
            log.error(f"Failed to load template from {yaml_file}: {e}")
            raise TemplateServiceError(f"Failed to load template: {str(e)}")

    def _discover_template_files(self) -> List[Path]:
        """Discover all YAML template files in the templates directory."""
        if not self.templates_dir.exists():
            log.warning(f"Templates directory {self.templates_dir} does not exist")
            return []

        return list(self.templates_dir.glob("*.yml")) + list(self.templates_dir.glob("*.yaml"))

    def get_all_templates(self) -> List[Dict[str, Any]]:
        """Get all template definitions from YAML files."""
        templates = []
        for yaml_file in self._discover_template_files():
            try:
                template_data = self._load_template_from_yaml(yaml_file)
                templates.append(template_data)
            except Exception as e:
                log.error(f"Failed to load template from {yaml_file}: {e}")
        return templates

    def get_template_by_id(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get specific template definition by ID."""
        for template in self.get_all_templates():
            if template.get('template_id') == template_id:
                return template
        return None

    async def seed_templates(self) -> Dict[str, Any]:
        """Seed built-in templates into the database and Registry."""
        results = {"seeded": [], "skipped": [], "errors": []}
        
        templates = self.get_all_templates()
        log.info(f"Found {len(templates)} built-in templates to seed")
        
        for template_data in templates:
            result = await self._seed_single_template(template_data)
            results[result["status"]].append(result)
        
        return results

    async def _seed_single_template(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Seed a single template into database and Registry."""
        template_id = template_data.get("template_id")
        name = template_data.get("name", "Unknown")
        
        try:
            # Check if template already exists
            existing = await self.get_template(UUID(template_id))
            if existing:
                return {
                    "status": "skipped",
                    "template_id": template_id,
                    "name": name,
                    "reason": "Template already exists"
                }
            
            # Create new template
            template = await self.create_template(
                name=template_data["name"],
                description=template_data.get("description", ""),
                flow_definition=template_data["flow_definition"],
                scope=template_data.get("scope", "GLOBAL"),
                tenant_id=template_data.get("tenant_id"),
                category=template_data.get("category", "GENERAL"),
                version=template_data.get("version", "1.0.0"),
                configuration_schema=template_data.get("configuration_schema", {})
            )
            
            return {
                "status": "seeded",
                "template_id": str(template.template_id),
                "name": template.name
            }
            
        except Exception as e:
            log.error(f"Failed to seed template {template_id}: {str(e)}")
            return {
                "status": "errors",
                "template_id": template_id,
                "name": name,
                "error": str(e)
            }

    # === Private Helper Methods ===

    async def _ensure_bucket_exists(self, scope: str, tenant_id: Optional[str] = None) -> RegistryBucket:
        """Ensure a bucket exists for the given scope and tenant."""
        if scope == "GLOBAL":
            bucket_name = "global-templates"
        else:
            bucket_name = f"{tenant_id}-templates" if tenant_id else "tenant-templates"
        
        # Check if bucket exists in database
        query = select(RegistryBucket).where(RegistryBucket.name == bucket_name)
        result = await self.session.execute(query)
        bucket = result.scalar_one_or_none()
        
        if bucket:
            return bucket
        
        # Create bucket in Registry and database
        try:
            async with NiFiRegistryClient(
                settings.NIFI_REGISTRY_URL,
                settings.NIFI_REGISTRY_AUTH_TOKEN
            ) as registry_client:
                # Try to create bucket in Registry
                try:
                    registry_bucket = await registry_client.create_bucket(
                        name=bucket_name,
                        description=f"Templates for {scope.lower()} scope"
                    )
                except Exception as registry_error:
                    # If bucket exists, find it
                    if "409" in str(registry_error) or "Conflict" in str(registry_error):
                        buckets = await registry_client.list_buckets()
                        registry_bucket = None
                        for b in buckets:
                            if b["name"] == bucket_name:
                                registry_bucket = b
                                break
                        
                        if not registry_bucket:
                            raise TemplateServiceError(f"Bucket {bucket_name} exists in Registry but cannot be found")
                    else:
                        raise registry_error
                
                bucket = RegistryBucket(
                    bucket_id=UUID(registry_bucket["identifier"]),
                    name=bucket_name,
                    description=f"Templates for {scope.lower()} scope",
                    scope=scope,
                    tenant_id=tenant_id if scope != "GLOBAL" else None
                )
                
                self.session.add(bucket)
                await self.session.commit()
                await self.session.refresh(bucket)
                
                return bucket
                
        except Exception as e:
            log.error(f"Failed to create bucket {bucket_name}: {str(e)}")
            raise TemplateServiceError(f"Failed to create bucket: {str(e)}")

    async def _get_bucket_by_id(self, bucket_id: UUID) -> Optional[RegistryBucket]:
        """Get bucket by ID."""
        query = select(RegistryBucket).where(RegistryBucket.bucket_id == bucket_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()