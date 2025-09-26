"""
Configuration management for EDI Lens CLI.
"""

import os
from pathlib import Path
from typing import Dict, Any


class Config:
    """Configuration manager for the CLI application."""
    
    def __init__(self):
        """Initialize configuration with default values and environment overrides."""
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.data_dir = self.project_root / "data"
        self.flows_dir = self.data_dir / "flows"
        self.test_data_dir = self.data_dir / "test-data"
        
        # Load environment variables
        self._load_env_config()
        
        # CLI-specific settings
        self.request_timeout = 30
        self.display_width = 80
        self.items_per_page = 10
        
    def _load_env_config(self):
        """Load configuration from environment variables."""
        # Backend API configuration
        self.backend_url = os.getenv("EDI_LENS_BACKEND_URL", "http://localhost:8000")
        
        # NiFi configuration
        self.nifi_url = os.getenv("NIFI_URL", "https://localhost:8443")
        self.nifi_username = os.getenv("NIFI_USERNAME", "admin")
        self.nifi_password = os.getenv("NIFI_PASSWORD", "adminadmin123")
        
        # Registry configuration
        self.registry_url = os.getenv("NIFI_REGISTRY_URL", "http://localhost:18080")
        
        # Environment detection
        self.environment = os.getenv("EDI_LENS_ENV", "development")
        self.debug_mode = os.getenv("EDI_LENS_DEBUG", "false").lower() in ("true", "1", "yes")
        
    def ensure_directories(self):
        """Ensure required directories exist."""
        directories = [
            self.data_dir,
            self.flows_dir,
            self.test_data_dir,
            self.flows_dir / "custom",
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            
    def get_flow_templates_dir(self) -> Path:
        """Get the directory containing flow templates."""
        return self.flows_dir
        
    def get_test_data_dir(self) -> Path:
        """Get the directory containing test data."""
        return self.test_data_dir
        
    def get_nifi_ui_url(self, process_group_id: str = None) -> str:
        """Get NiFi UI URL, optionally for a specific process group."""
        base_url = f"{self.nifi_url}/nifi"
        if process_group_id:
            return f"{base_url}/#/process-groups/{process_group_id}"
        return base_url
        
    def get_registry_ui_url(self, bucket_id: str = None, flow_id: str = None) -> str:
        """Get Registry UI URL, optionally for a specific bucket or flow."""
        base_url = f"{self.registry_url}/nifi-registry"
        if bucket_id and flow_id:
            return f"{base_url}/explorer/grid-list/buckets/{bucket_id}/flows/{flow_id}"
        elif bucket_id:
            return f"{base_url}/explorer/grid-list/buckets/{bucket_id}"
        return base_url
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for display."""
        return {
            "Backend URL": self.backend_url,
            "NiFi URL": self.nifi_url,
            "Registry URL": self.registry_url,
            "Environment": self.environment,
            "Debug Mode": self.debug_mode,
            "Data Directory": str(self.data_dir),
            "Flows Directory": str(self.flows_dir),
            "Test Data Directory": str(self.test_data_dir),
        }