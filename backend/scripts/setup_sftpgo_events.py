#!/usr/bin/env python3
"""
SFTPGo Event Manager Setup Script

Sets up SFTPGo event actions and rules for real-time EDI file processing.
This script is called during application startup to configure webhooks automatically.
"""

import os
import sys
import time
import requests
import json
import logging
from base64 import b64encode
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration from environment
SFTPGO_API_URL = os.getenv("SFTPGO_API_URL", "http://sftpgo:8080/api/v2")
SFTPGO_ADMIN_USER = os.getenv("SFTPGO_ADMIN_USER", "admin")
SFTPGO_ADMIN_PASSWORD = os.getenv("SFTPGO_ADMIN_PASSWORD", "admin123")
BACKEND_WEBHOOK_URL = os.getenv("BACKEND_WEBHOOK_URL", "http://backend:8000/api/v1/sftp/hooks/upload")

class SFTPGoEventSetup:
    """Setup SFTPGo event actions and rules for EDI processing."""
    
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
        self.max_retries = 30
        self.retry_delay = 2
    
    def wait_for_sftpgo(self) -> bool:
        """Wait for SFTPGo to be ready."""
        logger.info("Waiting for SFTPGo to be ready...")
        
        for attempt in range(self.max_retries):
            try:
                response = requests.get(f"{SFTPGO_API_URL.replace('/api/v2', '')}/healthz", timeout=5)
                if response.status_code == 200:
                    logger.info("SFTPGo is ready!")
                    return True
            except requests.RequestException as e:
                logger.debug(f"SFTPGo not ready yet (attempt {attempt + 1}/{self.max_retries}): {e}")
                
            time.sleep(self.retry_delay)
        
        logger.error("SFTPGo failed to become ready within timeout period")
        return False
    
    def authenticate(self) -> bool:
        """Authenticate with SFTPGo Admin API."""
        if self.auth_token:
            return True
            
        try:
            logger.info("Authenticating with SFTPGo Admin API...")
            credentials = f"{SFTPGO_ADMIN_USER}:{SFTPGO_ADMIN_PASSWORD}"
            encoded_credentials = b64encode(credentials.encode()).decode()
            headers = {"Authorization": f"Basic {encoded_credentials}"}
            
            response = self.session.get(f"{SFTPGO_API_URL}/token", headers=headers, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            self.auth_token = token_data.get("access_token")
            
            if not self.auth_token:
                logger.error("Authentication succeeded but no access token returned")
                return False
            
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
            logger.info("Successfully authenticated with SFTPGo Admin API")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to authenticate with SFTPGo: {e}")
            return False
    
    def event_action_exists(self, name: str) -> bool:
        """Check if event action already exists."""
        try:
            response = self.session.get(f"{SFTPGO_API_URL}/eventactions/{name}")
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def event_rule_exists(self, name: str) -> bool:
        """Check if event rule already exists."""
        try:
            response = self.session.get(f"{SFTPGO_API_URL}/eventrules/{name}")
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def create_upload_webhook_action(self) -> bool:
        """Create HTTP webhook action for file uploads."""
        action_name = "edi_lens_upload_webhook"
        
        if self.event_action_exists(action_name):
            logger.info(f"Event action '{action_name}' already exists, skipping creation")
            return True
        
        # Event action configuration with SFTPGo placeholders
        action_config = {
            "name": action_name,
            "description": "EDI Lens webhook for real-time file processing",
            "type": 1,  # HTTP action type
            "options": {
                "http_config": {
                    "endpoint": BACKEND_WEBHOOK_URL,
                    "timeout": 30,
                    "method": "POST",
                    "headers": [
                        {
                            "key": "Content-Type", 
                            "value": "application/json"
                        }
                    ],
                    # JSON body with SFTPGo placeholders
                    "body": json.dumps({
                        "name": "{{ObjectName}}",
                        "size": "{{FileSize}}",
                        "username": "{{Name}}",
                        "path": "{{VirtualPath}}",
                        "action": "{{Event}}",
                        "fs_provider": 1,
                        "bucket": "edi-lens",
                        "object_name": "{{FsPath}}"
                    }, separators=(',', ':'))  # Compact JSON
                }
            }
        }
        
        try:
            logger.info(f"Creating event action: {action_name}")
            response = self.session.post(f"{SFTPGO_API_URL}/eventactions", json=action_config)
            response.raise_for_status()
            
            logger.info(f"Successfully created event action: {action_name}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to create event action '{action_name}': {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return False
    
    def create_upload_trigger_rule(self) -> bool:
        """Create event rule to trigger webhook on EDI file uploads."""
        rule_name = "edi_lens_upload_rule"
        
        if self.event_rule_exists(rule_name):
            logger.info(f"Event rule '{rule_name}' already exists, skipping creation")
            return True
        
        # Event rule configuration
        rule_config = {
            "name": rule_name,
            "description": "Trigger EDI processing webhook on file upload", 
            "trigger": 1,  # Filesystem event trigger
            "conditions": {
                "fs_events": ["upload"],
                "options": {
                    "names": [
                        {"pattern": "*.edi", "inverse_match": False},
                        {"pattern": "*.x12", "inverse_match": False},
                        {"pattern": "*.txt", "inverse_match": False}
                    ]
                }
            },
            "actions": [
                {
                    "name": "edi_lens_upload_webhook",
                    "order": 1
                }
            ]
        }
        
        try:
            logger.info(f"Creating event rule: {rule_name}")
            response = self.session.post(f"{SFTPGO_API_URL}/eventrules", json=rule_config)
            response.raise_for_status()
            
            logger.info(f"Successfully created event rule: {rule_name}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to create event rule '{rule_name}': {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return False
    
    def setup_events(self) -> bool:
        """Main setup method."""
        logger.info("🚀 Setting up SFTPGo event configuration for EDI Lens")
        
        # Wait for SFTPGo to be ready
        if not self.wait_for_sftpgo():
            return False
        
        # Authenticate
        if not self.authenticate():
            return False
        
        # Create event action
        if not self.create_upload_webhook_action():
            return False
        
        # Create event rule
        if not self.create_upload_trigger_rule():
            return False
        
        logger.info("✅ SFTPGo event configuration completed successfully!")
        logger.info(f"Webhook endpoint: {BACKEND_WEBHOOK_URL}")
        logger.info("Real-time EDI file processing is now active")
        
        return True


def main():
    """Main entry point."""
    setup = SFTPGoEventSetup()
    
    try:
        success = setup.setup_events()
        if success:
            logger.info("SFTPGo event setup completed successfully")
            sys.exit(0)
        else:
            logger.error("SFTPGo event setup failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during setup: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()