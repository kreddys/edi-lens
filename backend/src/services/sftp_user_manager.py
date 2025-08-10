# FILE: backend/src/services/sftp_user_manager.py

import logging
import requests
import os
from base64 import b64encode
from typing import Optional, Dict, Any, List

from src.core.config import settings

logger = logging.getLogger(__name__)

SFTPGO_API_URL = "http://sftpgo:8080/api/v2"
SFTPGO_ADMIN_USER = os.getenv("SFTPGO_ADMIN_USER", "admin")
SFTPGO_ADMIN_PASSWORD = os.getenv("SFTPGO_ADMIN_PASSWORD", "admin123")

class SftpUserManager:
    """Service for securely managing SFTP users in SFTPGo via its Admin API."""
    
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
        
    def authenticate(self) -> bool:
        if self.auth_token: return True
        try:
            logger.debug("Authenticating with SFTPGo Admin API...")
            credentials = f"{SFTPGO_ADMIN_USER}:{SFTPGO_ADMIN_PASSWORD}"
            encoded_credentials = b64encode(credentials.encode()).decode()
            headers = {"Authorization": f"Basic {encoded_credentials}"}
            
            response = self.session.get(f"{SFTPGO_API_URL}/token", headers=headers, timeout=10)
            response.raise_for_status()
            
            self.auth_token = response.json().get("access_token")
            if not self.auth_token:
                logger.error("SFTPGo authentication succeeded but no access token was returned.")
                return False

            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
            logger.info("Successfully authenticated with SFTPGo Admin API.")
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to connect to SFTPGo API for authentication: {e}")
            return False

    def user_exists(self, username: str) -> bool:
        if not self.authenticate(): return False
        try:
            response = self.session.get(f"{SFTPGO_API_URL}/users/{username}", timeout=10)
            return response.status_code == 200
        except requests.RequestException as e:
            logger.error(f"Error checking if SFTPGo user '{username}' exists: {e}")
            return False

    def _create_virtual_folder(self, folder_name: str, tenant_id: str, partner_identifier: str, path_type: str) -> bool:
        """Creates a virtual folder configuration in SFTPGo."""
        if not self.authenticate(): return False

        # This payload matches the BaseVirtualFolder schema from the OpenAPI spec
        folder_payload = {
            "name": folder_name,
            "mapped_path": "/", # Mapped path is required but not used for S3
            "description": f"EDI Lens {path_type} for partner {partner_identifier}",
            "filesystem": {
                "provider": 1, # S3
                "s3config": {
                    "bucket": settings.STORAGE_BUCKET,
                    "region": settings.STORAGE_REGION,
                    "access_key": settings.STORAGE_ACCESS_KEY,
                    "access_secret": {"status": "Plain", "payload": settings.STORAGE_SECRET_KEY},
                    "endpoint": settings.STORAGE_ENDPOINT_URL,
                    "key_prefix": f"tenants/{tenant_id}/partners/{partner_identifier}/{path_type}/",
                    "force_path_style": True,
                }
            }
        }
        
        try:
            # --- THIS IS THE FIX ---
            # The correct endpoint is `/folders`
            response = self.session.post(f"{SFTPGO_API_URL}/folders", json=folder_payload, timeout=15)
            # --- END OF FIX ---
            
            if response.status_code == 201:
                logger.info(f"Successfully created SFTPGo virtual folder '{folder_name}'.")
                return True
            elif response.status_code == 409:
                logger.warning(f"SFTPGo virtual folder '{folder_name}' already exists. Skipping.")
                return True
            else:
                logger.error(f"Failed to create virtual folder '{folder_name}': {response.status_code} - {response.text}")
                return False
        except requests.RequestException as e:
            logger.error(f"Error creating virtual folder '{folder_name}': {e}")
            return False

    def create_user(self, username: str, tenant_id: str, partner_name: str, partner_id: str = None) -> bool:
        """Creates a new, jailed SFTP user."""
        if not self.authenticate(): return False

        # Use partner_id for directory structure, fallback to username for backward compatibility
        folder_identifier = partner_id if partner_id else username
        in_folder_name = f"{username}-in"
        out_folder_name = f"{username}-out"

        if not self._create_virtual_folder(in_folder_name, tenant_id, folder_identifier, "in"):
            return False
        if not self._create_virtual_folder(out_folder_name, tenant_id, folder_identifier, "out"):
            return False

        # This payload matches the User schema from the OpenAPI spec
        user_payload = {
            "username": username,
            "status": 1,
            "description": f"EDI Lens Partner: {partner_name} (Tenant: {tenant_id})",
            "home_dir": "/home",  # Set to a safe directory that will be overridden by virtual folders
            "permissions": {
                "/": ["list"],  # Minimal permission to list root directory
                "/in": ["*"],   # Full access to in directory
                "/out": ["*"]   # Full access to out directory
            },
            "filesystem": {"provider": 0},
            "virtual_folders": [
                { "name": in_folder_name, "virtual_path": "/in" },
                { "name": out_folder_name, "virtual_path": "/out" }
            ]
        }
        
        try:
            response = self.session.post(f"{SFTPGO_API_URL}/users", json=user_payload, timeout=15)
            if response.status_code == 201:
                logger.info(f"Successfully created SFTPGo user '{username}'.")
                return True
            elif response.status_code == 409:
                logger.warning(f"SFTPGo user '{username}' already exists. Attempting to update...")
                update_response = self.session.put(f"{SFTPGO_API_URL}/users/{username}", json=user_payload, timeout=15)
                if update_response.status_code == 200:
                    logger.info(f"Successfully updated existing SFTPGo user '{username}'.")
                    return True
                else:
                    logger.error(f"Failed to update existing SFTPGo user '{username}': {update_response.status_code} - {update_response.text}")
                    return False
            else:
                logger.error(f"Failed to create SFTPGo user '{username}': {response.status_code} - {response.text}")
                return False
        except requests.RequestException as e:
            logger.error(f"Error creating/updating SFTPGo user '{username}': {e}")
            return False