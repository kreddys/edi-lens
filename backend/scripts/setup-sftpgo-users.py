#!/usr/bin/env python3
"""
Setup SFTPGo users with MinIO backend storage for trading partners.
"""

import asyncio
import json
import requests
import sys
from pathlib import Path

# Add backend to path for imports  
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from src.core.config import settings
from src.models.trading_partner import TradingPartner
from src.models.sftp_configuration import SftpConfiguration

# SFTPGo configuration
SFTPGO_BASE_URL = "http://sftpgo:8080"
SFTPGO_ADMIN_USER = "admin"
SFTPGO_ADMIN_PASSWORD = "admin123"

# MinIO configuration (from environment)
MINIO_ENDPOINT = settings.STORAGE_ENDPOINT_URL
MINIO_ACCESS_KEY = settings.STORAGE_ACCESS_KEY
MINIO_SECRET_KEY = settings.STORAGE_SECRET_KEY
MINIO_BUCKET = settings.STORAGE_BUCKET

class SFTPGoManager:
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
        
    def authenticate(self):
        """Authenticate with SFTPGo admin via web login"""
        print("🔐 Authenticating with SFTPGo...")
        
        # First, get the login page to extract CSRF token
        login_page_response = self.session.get(f"{SFTPGO_BASE_URL}/web/admin/login")
        
        # Extract CSRF token from the login page
        import re
        csrf_token = None
        csrf_match = re.search(r'name="_form_token" value="([^"]+)"', login_page_response.text)
        if csrf_match:
            csrf_token = csrf_match.group(1)
        
        # Login via web form with CSRF token
        login_data = {
            "username": SFTPGO_ADMIN_USER,
            "password": SFTPGO_ADMIN_PASSWORD
        }
        
        if csrf_token:
            login_data["_form_token"] = csrf_token
        
        response = self.session.post(
            f"{SFTPGO_BASE_URL}/web/admin/login",
            data=login_data,
            allow_redirects=False
        )
        
        # Check if login was successful (should redirect)
        if response.status_code == 302:
            print(f"🔄 Login redirected to: {response.headers.get('Location', 'unknown')}")
            
            # Follow the redirect manually to get the final page
            redirect_response = self.session.get(
                f"{SFTPGO_BASE_URL}{response.headers.get('Location', '')}"
            )
            print(f"📍 Redirect response: {redirect_response.status_code}")
            
            # Test authentication by calling an API endpoint
            test_response = self.session.get(f"{SFTPGO_BASE_URL}/api/v2/version")
            print(f"🧪 API test response: {test_response.status_code}")
            
            if test_response.status_code == 200:
                print("✅ Successfully authenticated with SFTPGo")
                return True
        
        print(f"❌ Failed to authenticate: {response.status_code}")
        if response.status_code == 200:
            print("❌ Login form returned without redirect (authentication failed)")
        return False
    
    def create_user(self, username, password, tenant_id, partner_name, partner_id):
        """Create SFTPGo user with MinIO backend storage"""
        
        # Create user with MinIO S3 filesystem
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
                "provider": "s3",
                "s3config": {
                    "bucket": MINIO_BUCKET,
                    "region": "us-east-1",
                    "access_key": MINIO_ACCESS_KEY,
                    "access_secret": MINIO_SECRET_KEY,
                    "endpoint": MINIO_ENDPOINT,
                    "storage_class": "",
                    "acl": "",
                    "upload_part_size": 5,
                    "upload_concurrency": 2,
                    "download_part_size": 5,
                    "download_concurrency": 2,
                    "download_part_max_time": 60,
                    "upload_part_max_time": 60,
                    "use_list_objects_v1": False,
                    "skip_folder_creation": False,
                    "key_prefix": f"sftp/{tenant_id}/{username}/",
                    "force_path_style": True  # Required for MinIO
                }
            },
            "virtual_folders": [
                {
                    "name": f"{username}-in",
                    "mapped_path": "/in",
                    "filesystem": {
                        "provider": "s3",
                        "s3config": {
                            "bucket": MINIO_BUCKET,
                            "region": "us-east-1",
                            "access_key": MINIO_ACCESS_KEY,
                            "access_secret": MINIO_SECRET_KEY,
                            "endpoint": MINIO_ENDPOINT,
                            "key_prefix": f"sftp/{tenant_id}/{username}/in/",
                            "force_path_style": True
                        }
                    }
                },
                {
                    "name": f"{username}-out",
                    "mapped_path": "/out",
                    "filesystem": {
                        "provider": "s3",
                        "s3config": {
                            "bucket": MINIO_BUCKET,
                            "region": "us-east-1",
                            "access_key": MINIO_ACCESS_KEY,
                            "access_secret": MINIO_SECRET_KEY,
                            "endpoint": MINIO_ENDPOINT,
                            "key_prefix": f"sftp/{tenant_id}/{username}/out/",
                            "force_path_style": True
                        }
                    }
                }
            ]
        }
        
        print(f"📝 Creating SFTPGo user: {username} ({partner_name})")
        
        response = self.session.post(
            f"{SFTPGO_BASE_URL}/api/v2/users",
            json=user_config
        )
        
        if response.status_code == 201:
            print(f"✅ Successfully created user: {username}")
            return True
        elif response.status_code == 409:
            print(f"⚠️  User already exists: {username}")
            # Update existing user
            return self.update_user(username, user_config)
        else:
            print(f"❌ Failed to create user {username}: {response.status_code} - {response.text}")
            return False
    
    def update_user(self, username, user_config):
        """Update existing SFTPGo user"""
        print(f"🔄 Updating existing user: {username}")
        
        response = self.session.put(
            f"{SFTPGO_BASE_URL}/api/v2/users/{username}",
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
        response = self.session.get(f"{SFTPGO_BASE_URL}/api/v2/users")
        
        if response.status_code == 200:
            users = response.json()
            print(f"\n📋 Current SFTPGo users ({len(users)}):")
            for user in users:
                print(f"  - {user['username']} ({user.get('description', 'No description')})")
            return users
        else:
            print(f"❌ Failed to list users: {response.status_code} - {response.text}")
            return []

async def get_sftp_configurations():
    """Get SFTP configurations from database"""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SftpConfiguration, TradingPartner)
            .join(TradingPartner, SftpConfiguration.partner_id == TradingPartner.id)
        )
        
        configs = []
        for sftp_config, partner in result.fetchall():
            configs.append({
                'sftp_config': sftp_config,
                'partner': partner
            })
        
        return configs

async def main():
    print("🚀 Starting SFTPGo user setup for EDI Lens trading partners...")
    
    # Get SFTP configurations from database
    print("📊 Fetching SFTP configurations from database...")
    configs = await get_sftp_configurations()
    
    if not configs:
        print("⚠️  No SFTP configurations found in database")
        return
    
    print(f"📋 Found {len(configs)} SFTP configurations")
    
    # Initialize SFTPGo manager
    sftpgo = SFTPGoManager()
    
    if not sftpgo.authenticate():
        print("❌ Failed to authenticate with SFTPGo")
        return
    
    # Create users for each configuration
    success_count = 0
    for config_data in configs:
        sftp_config = config_data['sftp_config']
        partner = config_data['partner']
        
        username = sftp_config.sftp_username
        password = sftp_config.password_hash  # TODO: This should be plaintext for SFTPGo
        tenant_id = sftp_config.tenant_id
        partner_name = partner.name
        partner_id = partner.id
        
        if sftpgo.create_user(username, password, tenant_id, partner_name, partner_id):
            success_count += 1
    
    print(f"\n✅ Successfully created/updated {success_count}/{len(configs)} SFTPGo users")
    
    # List all users
    sftpgo.list_users()
    
    print(f"\n🌐 SFTPGo Web Admin: http://localhost:8080/web/admin/")
    print(f"🔑 Admin credentials: {SFTPGO_ADMIN_USER} / {SFTPGO_ADMIN_PASSWORD}")
    print(f"📡 SFTP Connection: localhost:2022")
    print(f"💾 Storage Backend: MinIO S3 ({MINIO_ENDPOINT})")

if __name__ == "__main__":
    asyncio.run(main())