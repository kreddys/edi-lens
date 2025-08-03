"""
SFTP User Management Service
Handles creation, update, and deletion of SFTP users in SFTPGo.
"""

import logging
import requests
from base64 import b64encode
from typing import Optional, Dict, Any, List
from src.core.config import settings

logger = logging.getLogger(__name__)


class SftpUserManager:
    """Service for managing SFTP users in SFTPGo."""
    
    def __init__(self, 
                 sftpgo_base_url: Optional[str] = None,
                 admin_username: str = "admin",
                 admin_password: str = "admin123"):
        """
        Initialize SFTP user manager.
        
        Args:
            sftpgo_base_url: Base URL for SFTPGo API (auto-detects container vs localhost)
            admin_username: SFTPGo admin username
            admin_password: SFTPGo admin password
        """
        # Auto-detect container vs localhost
        if sftpgo_base_url is None:
            try:
                # Check if we're running in a container by looking for sftpgo hostname
                import socket
                socket.gethostbyname('sftpgo')
                sftpgo_base_url = "http://sftpgo:8080"
                logger.info("Detected container environment, using sftpgo:8080")
            except (socket.gaierror, OSError):
                # Fall back to localhost
                sftpgo_base_url = "http://localhost:8080"
                logger.info("Using localhost:8080 for SFTPGo API")
        
        self.base_url = sftpgo_base_url
        self.api_base = f"{sftpgo_base_url}/api/v2"
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.session = requests.Session()
        self.auth_token = None
        
    def authenticate(self) -> bool:
        """Authenticate with SFTPGo admin API."""
        try:
            logger.info("🔐 Authenticating with SFTPGo...")
            
            # Create Basic Auth header
            credentials = f"{self.admin_username}:{self.admin_password}"
            encoded_credentials = b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/json"
            }
            
            # Get JWT token using /api/v2/token endpoint
            response = self.session.get(
                f"{self.api_base}/token",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.auth_token = token_data.get("access_token")
                
                # Set Bearer token for subsequent requests
                self.session.headers.update({
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json"
                })
                
                logger.info("✅ Successfully authenticated with SFTPGo API")
                return True
            else:
                logger.error(f"❌ Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Authentication error: {str(e)}")
            return False
    
    def create_virtual_folder(self, folder_name: str, tenant_id: str, username: str, path_type: str) -> bool:
        """Create a virtual folder for SFTP user."""
        try:
            logger.info(f"📁 Creating virtual folder: {folder_name}")
            
            folder_config = {
                "name": folder_name,
                "mapped_path": "/tmp",  # Required but not used for S3
                "description": f"EDI Lens {path_type} folder for {username} (Tenant: {tenant_id})",
                "filesystem": {
                    "provider": 1,  # S3 Compatible Object Storage
                    "s3config": {
                        "bucket": settings.STORAGE_BUCKET,
                        "region": "us-east-1",
                        "access_key": settings.STORAGE_ACCESS_KEY,
                        "access_secret": {
                            "status": "Plain",
                            "payload": settings.STORAGE_SECRET_KEY
                        },
                        "endpoint": settings.STORAGE_ENDPOINT_URL,
                        "key_prefix": f"sftp/{tenant_id}/{username}/{path_type}/",
                        "force_path_style": True,
                        "upload_part_size": 5,
                        "upload_concurrency": 2,
                        "download_part_size": 5,
                        "download_concurrency": 2
                    }
                }
            }
            
            response = self.session.post(
                f"{self.api_base}/folders",
                json=folder_config,
                timeout=30
            )
            
            if response.status_code == 201:
                logger.info(f"✅ Created virtual folder: {folder_name}")
                return True
            elif response.status_code == 409:
                logger.info(f"⚠️ Virtual folder already exists: {folder_name}")
                return True
            else:
                logger.error(f"❌ Failed to create virtual folder {folder_name}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error creating virtual folder {folder_name}: {str(e)}")
            return False
    
    def create_user(self, username: str, password: str, tenant_id: str, partner_name: str) -> bool:
        """
        Create SFTP user with MinIO S3 backend.
        
        Args:
            username: SFTP username (format: tenant-id_partner-slug)
            password: Plain text password
            tenant_id: Tenant ID for multi-tenancy
            partner_name: Human-readable partner name
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.auth_token:
                if not self.authenticate():
                    return False
            
            # Create virtual folders first
            in_folder = f"{username}-in"
            out_folder = f"{username}-out"
            
            if not self.create_virtual_folder(in_folder, tenant_id, username, "in"):
                return False
            if not self.create_virtual_folder(out_folder, tenant_id, username, "out"):
                return False
            
            # Create user configuration
            user_config = {
                "username": username,
                "password": password,
                "status": 1,  # Active
                "email": f"{username}@edilens.com",
                "description": f"EDI Lens Trading Partner - {partner_name} (Tenant: {tenant_id})",
                "home_dir": f"/{tenant_id}/{username}",
                "uid": 1000,
                "gid": 1000,
                "max_sessions": 5,
                "quota_size": 0,  # Unlimited
                "quota_files": 0,  # Unlimited
                "permissions": {
                    "/": ["*"]  # All permissions
                },
                "upload_bandwidth": 0,  # Unlimited
                "download_bandwidth": 0,  # Unlimited
                "upload_data_transfer": 0,  # Unlimited
                "download_data_transfer": 0,  # Unlimited
                "expires_at": 0,  # Never expires
                "filesystem": {
                    "provider": 1,  # S3 Compatible
                    "s3config": {
                        "bucket": settings.STORAGE_BUCKET,
                        "region": "us-east-1",
                        "access_key": settings.STORAGE_ACCESS_KEY,
                        "access_secret": {
                            "status": "Plain",
                            "payload": settings.STORAGE_SECRET_KEY
                        },
                        "endpoint": settings.STORAGE_ENDPOINT_URL,
                        "key_prefix": f"sftp/{tenant_id}/{username}/",
                        "force_path_style": True,
                        "upload_part_size": 5,
                        "upload_concurrency": 2,
                        "download_part_size": 5,
                        "download_concurrency": 2
                    }
                },
                "virtual_folders": [
                    {
                        "name": in_folder,
                        "virtual_path": "/in",
                        "quota_size": 0,
                        "quota_files": 0
                    },
                    {
                        "name": out_folder,
                        "virtual_path": "/out",
                        "quota_size": 0,
                        "quota_files": 0
                    }
                ]
            }
            
            logger.info(f"📝 Creating SFTPGo user: {username} ({partner_name})")
            
            response = self.session.post(
                f"{self.api_base}/users",
                json=user_config,
                timeout=30
            )
            
            if response.status_code == 201:
                logger.info(f"✅ Successfully created user: {username}")
                return True
            elif response.status_code == 409:
                logger.info(f"⚠️ User already exists: {username}")
                # Try to update existing user
                return self.update_user(username, user_config)
            else:
                logger.error(f"❌ Failed to create user {username}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error creating user {username}: {str(e)}")
            return False
    
    def update_user(self, username: str, user_config: Dict[str, Any]) -> bool:
        """Update existing SFTP user."""
        try:
            logger.info(f"🔄 Updating existing user: {username}")
            
            response = self.session.put(
                f"{self.api_base}/users/{username}",
                json=user_config,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Successfully updated user: {username}")
                return True
            else:
                logger.error(f"❌ Failed to update user {username}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error updating user {username}: {str(e)}")
            return False
    
    def delete_user(self, username: str) -> bool:
        """Delete SFTP user."""
        try:
            if not self.auth_token:
                if not self.authenticate():
                    return False
            
            logger.info(f"🗑️ Deleting user: {username}")
            
            response = self.session.delete(
                f"{self.api_base}/users/{username}",
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Successfully deleted user: {username}")
                return True
            elif response.status_code == 404:
                logger.info(f"⚠️ User not found: {username}")
                return True  # Consider this success
            else:
                logger.error(f"❌ Failed to delete user {username}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error deleting user {username}: {str(e)}")
            return False
    
    def list_users(self) -> List[Dict[str, Any]]:
        """List all SFTP users."""
        try:
            if not self.auth_token:
                if not self.authenticate():
                    return []
            
            response = self.session.get(f"{self.api_base}/users", timeout=30)
            
            if response.status_code == 200:
                users = response.json()
                logger.info(f"📋 Found {len(users)} SFTPGo users")
                return users
            else:
                logger.error(f"❌ Failed to list users: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error listing users: {str(e)}")
            return []
    
    def user_exists(self, username: str) -> bool:
        """Check if SFTP user exists."""
        try:
            if not self.auth_token:
                if not self.authenticate():
                    return False
            
            response = self.session.get(f"{self.api_base}/users/{username}", timeout=30)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"❌ Error checking user existence {username}: {str(e)}")
            return False