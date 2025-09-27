"""Flow template management service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from ..core.config import settings
from ..core.logging import get_logger

log = get_logger(__name__)


class FlowTemplateService:
    """Service for managing flow templates from the configured directory."""

    def __init__(self):
        # Resolve path relative to the project root, not the backend directory
        from ..core.config import ROOT_DIR
        self.templates_dir = ROOT_DIR / settings.FLOW_TEMPLATES_DIR
        self.logger = log

    async def list_templates(self) -> List[Dict[str, Any]]:
        """List all available flow templates."""
        templates = []
        
        if not self.templates_dir.exists():
            self.logger.warning("Templates directory does not exist: %s", self.templates_dir)
            return templates

        try:
            for template_file in self.templates_dir.glob("*.json"):
                try:
                    template_info = await self._get_template_info(template_file)
                    if template_info:
                        templates.append(template_info)
                except Exception as exc:
                    self.logger.warning("Failed to load template %s: %s", template_file.name, exc)
                    continue

            self.logger.debug("Found %d templates in %s", len(templates), self.templates_dir)
            return sorted(templates, key=lambda t: t.get("name", ""))

        except Exception as exc:
            self.logger.error("Failed to list templates: %s", exc)
            return []

    async def get_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific template by name."""
        template_file = self.templates_dir / f"{template_name}.json"
        
        if not template_file.exists():
            # Try with exact filename if it doesn't end with .json
            if not template_name.endswith('.json'):
                template_file = self.templates_dir / template_name
                if not template_file.exists():
                    self.logger.warning("Template not found: %s", template_name)
                    return None

        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            
            self.logger.debug("Loaded template: %s", template_name)
            return template_data

        except json.JSONDecodeError as exc:
            self.logger.error("Invalid JSON in template %s: %s", template_name, exc)
            return None
        except Exception as exc:
            self.logger.error("Failed to load template %s: %s", template_name, exc)
            return None

    async def _get_template_info(self, template_file: Path) -> Optional[Dict[str, Any]]:
        """Extract template metadata without loading full content."""
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                template_data = json.load(f)

            # Extract key information
            template_name = template_file.stem
            flow_name = template_data.get("name", template_name)
            description = template_data.get("description", "No description available")
            
            # Count components
            processors = template_data.get("processors", [])
            connections = template_data.get("connections", [])
            parameters = template_data.get("parameters", {})

            return {
                "id": template_name,
                "name": flow_name,
                "description": description,
                "filename": template_file.name,
                "processor_count": len(processors),
                "connection_count": len(connections),
                "parameter_count": len(parameters),
                "has_parameters": len(parameters) > 0,
                "processors": [p.get("name", "Unnamed") for p in processors[:3]],  # First 3 for preview
            }

        except Exception as exc:
            self.logger.warning("Failed to extract info from %s: %s", template_file.name, exc)
            return None

    async def validate_template(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a template structure."""
        errors = []
        warnings = []

        # Required fields
        if not template_data.get("name"):
            errors.append("Template must have a 'name' field")

        if not template_data.get("processors"):
            errors.append("Template must have a 'processors' array")
        elif not isinstance(template_data["processors"], list):
            errors.append("Template 'processors' must be an array")

        if not template_data.get("connections"):
            warnings.append("Template has no connections defined")
        elif not isinstance(template_data["connections"], list):
            errors.append("Template 'connections' must be an array")

        # Validate processor structure
        processors = template_data.get("processors", [])
        for i, processor in enumerate(processors):
            if not isinstance(processor, dict):
                errors.append(f"Processor {i} must be an object")
                continue

            if not processor.get("identifier") and not processor.get("name"):
                errors.append(f"Processor {i} must have either 'identifier' or 'name'")

            if not processor.get("type"):
                errors.append(f"Processor {i} must have a 'type' field")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "processor_count": len(processors),
            "connection_count": len(template_data.get("connections", [])),
        }