#!/usr/bin/env python3
"""
Automated SFTPGo setup using REST API v2.6 for EDI Lens trading partners.
This script uses the proper authentication method based on the OpenAPI specification.
"""

import json
import requests
import sys
import time
from base64 import b64encode

# SFTPGo configuration
SFTPGO_BASE_URL = "http://localhost:8080"
SFTPGO_API_BASE = f"{SFTPGO_BASE_URL}/api/v2"
SFTPGO_ADMIN_USER = "admin"
SFTPGO_ADMIN_PASSWORD = "admin123"

# MinIO configuration
MINIO_ENDPOINT = "http://minio:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
MINIO_BUCKET = "edi-lens-schemas"

class SFTPGoAPIClient:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        
    def authenticate(self):
        """Get JWT token using Basic Auth as per OpenAPI spec"""
        print("🔐 Authenticating with SFTPGo admin...")
        
        # Create Basic Auth header
        credentials = f"{SFTPGO_ADMIN_USER}:{SFTPGO_ADMIN_PASSWORD}"
        encoded_credentials = b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }
        
        # Get JWT token using /api/v2/token endpoint
        response = self.session.get(
            f"{SFTPGO_API_BASE}/token",
            headers=headers
        )
        
        if response.status_code == 200:
            token_data = response.json()
            self.token = token_data.get("access_token")
            
            # Set Bearer token for subsequent requests
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            })
            
            print("✅ Successfully authenticated with SFTPGo API")
            return True
        else:
            print(f"❌ Authentication failed: {response.status_code} - {response.text}")
            return False
    
    def create_virtual_folder(self, folder_name, tenant_id, username, path_type):
        """Create virtual folder using /api/v2/folders endpoint"""
        print(f"📁 Creating virtual folder: {folder_name}")
        
        folder_config = {
            "name": folder_name,
            "mapped_path": "/tmp",  # Required but not used for S3
            "description": f"EDI Lens {path_type} folder for {username} (Tenant: {tenant_id})",
            "filesystem": {
                "provider": 1,  # S3 Compatible Object Storage
                "s3config": {
                    "bucket": MINIO_BUCKET,
                    "region": "us-east-1",
                    "access_key": MINIO_ACCESS_KEY,
                    "access_secret": {
                        "status": "Plain",
                        "payload": MINIO_SECRET_KEY
                    },
                    "endpoint": MINIO_ENDPOINT,
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
            f"{SFTPGO_API_BASE}/folders",
            json=folder_config
        )
        
        if response.status_code == 201:
            print(f"✅ Created virtual folder: {folder_name}")
            return True
        elif response.status_code == 409:
            print(f"⚠️  Virtual folder already exists: {folder_name}")
            return True
        else:
            print(f"❌ Failed to create virtual folder {folder_name}: {response.status_code} - {response.text}")
            return False
    
    def create_user(self, username, password, tenant_id, partner_name):
        """Create SFTPGo user using /api/v2/users endpoint"""
        print(f"👤 Creating SFTPGo user: {username} ({partner_name})")
        
        # Create virtual folders first
        in_folder = f"{username}-in"
        out_folder = f"{username}-out"
        
        if not self.create_virtual_folder(in_folder, tenant_id, username, "in"):
            return False
        if not self.create_virtual_folder(out_folder, tenant_id, username, "out"):
            return False
        
        # Wait a moment for folders to be created
        time.sleep(1)
        
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
            "total_data_transfer": 0,  # Unlimited
            "filesystem": {
                "provider": 1,  # S3 Compatible Object Storage
                "s3config": {
                    "bucket": MINIO_BUCKET,
                    "region": "us-east-1",
                    "access_key": MINIO_ACCESS_KEY,
                    "access_secret": {
                        "status": "Plain",
                        "payload": MINIO_SECRET_KEY
                    },
                    "endpoint": MINIO_ENDPOINT,
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
        
        response = self.session.post(
            f"{SFTPGO_API_BASE}/users",
            json=user_config
        )
        
        if response.status_code == 201:
            print(f"✅ Successfully created user: {username}")
            return True
        elif response.status_code == 409:
            print(f"⚠️  User already exists: {username}")
            # Try to update existing user
            return self.update_user(username, user_config)
        else:
            print(f"❌ Failed to create user {username}: {response.status_code} - {response.text}")
            return False
    
    def update_user(self, username, user_config):
        """Update existing SFTPGo user"""
        print(f"🔄 Updating existing user: {username}")
        
        response = self.session.put(
            f"{SFTPGO_API_BASE}/users/{username}",
            json=user_config
        )
        
        if response.status_code == 200:
            print(f"✅ Successfully updated user: {username}")
            return True
        else:
            print(f"❌ Failed to update user {username}: {response.status_code} - {response.text}")
            return False
    
    def list_users(self):
        """List all SFTPGo users"""
        response = self.session.get(f"{SFTPGO_API_BASE}/users")
        
        if response.status_code == 200:
            users = response.json()
            print(f"\n📋 Current SFTPGo users ({len(users)}):")
            for user in users:
                print(f"  - {user['username']} ({user.get('description', 'No description')})")
            return users
        else:
            print(f"❌ Failed to list users: {response.status_code} - {response.text}")
            return []
    
    def get_version(self):
        """Get SFTPGo version info"""
        response = self.session.get(f"{SFTPGO_API_BASE}/version")
        
        if response.status_code == 200:
            version_info = response.json()
            print(f"📊 SFTPGo Version: {version_info.get('version', 'unknown')}")
            print(f"📅 Build Date: {version_info.get('build_date', 'unknown')}")
            return version_info
        else:
            print(f"❌ Failed to get version: {response.status_code}")
            return None

def main():
    print("🚀 Starting automated SFTPGo setup for EDI Lens trading partners...")
    
    # Trading partner configuration (based on seeded data)
    trading_partners = [
        {
            "username": "tenant-a_uhg-pro",
            "password": "uhg_secure_pass_123", 
            "tenant_id": "tenant-a",
            "partner_name": "United Health Group (Professional)"
        },
        {
            "username": "tenant-a_chc",
            "password": "chc_secure_pass_456",
            "tenant_id": "tenant-a", 
            "partner_name": "Change Healthcare (Clearinghouse)"
        },
        {
            "username": "tenant-b_medicaid",
            "password": "medicaid_pass_789",
            "tenant_id": "tenant-b",
            "partner_name": "State Medicaid"
        }
    ]
    
    # Initialize API client
    client = SFTPGoAPIClient()
    
    # Authenticate
    if not client.authenticate():
        print("❌ Failed to authenticate with SFTPGo")
        sys.exit(1)
    
    # Get version info
    client.get_version()
    
    # Create users
    success_count = 0
    for partner in trading_partners:
        if client.create_user(
            partner["username"],
            partner["password"], 
            partner["tenant_id"],
            partner["partner_name"]
        ):
            success_count += 1
    
    print(f"\n✅ Successfully created/updated {success_count}/{len(trading_partners)} SFTPGo users")
    
    # List all users
    client.list_users()
    
    print(f"\n🌐 SFTPGo Web Admin: {SFTPGO_BASE_URL}/web/admin/")
    print(f"🔑 Admin credentials: {SFTPGO_ADMIN_USER} / {SFTPGO_ADMIN_PASSWORD}")
    print(f"📡 SFTP Connection: localhost:2022")
    print(f"💾 Storage Backend: MinIO S3 ({MINIO_ENDPOINT})")
    
    print(f"\n📋 Trading Partner Connections:")
    for partner in trading_partners:
        print(f"  - {partner['username']}:{partner['password']} ({partner['partner_name']})")
    
    print(f"\n📁 Virtual Folders:")
    print(f"  - /in  -> sftp/{{tenant}}/{{username}}/in/")
    print(f"  - /out -> sftp/{{tenant}}/{{username}}/out/")

if __name__ == "__main__":
    main()