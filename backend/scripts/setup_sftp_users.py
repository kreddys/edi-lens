#!/usr/bin/env python3
"""
Setup SFTPGo users from database SFTP configurations.
This script reads SFTP configurations from the database and creates corresponding SFTPGo users.
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.core.config import settings
from src.models.trading_partner import TradingPartner
from src.models.sftp_configuration import SftpConfiguration
from src.services.sftp_user_manager import SftpUserManager


async def get_sftp_configurations():
    """Get SFTP configurations from database."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SftpConfiguration, TradingPartner)
            .join(TradingPartner, SftpConfiguration.partner_id == TradingPartner.id)
            .where(SftpConfiguration.sftp_enabled == True)
        )
        
        configs = []
        for sftp_config, partner in result.fetchall():
            configs.append({
                'sftp_config': sftp_config,
                'partner': partner
            })
        
        await engine.dispose()
        return configs


async def main():
    """Main function to setup SFTP users."""
    print("🚀 Starting SFTPGo user setup for EDI Lens trading partners...")
    
    # Get SFTP configurations from database
    print("📊 Fetching SFTP configurations from database...")
    configs = await get_sftp_configurations()
    
    if not configs:
        print("⚠️  No SFTP configurations found in database")
        print("💡 Run the seed script first: python scripts/seed.py --create-sftp")
        return
    
    print(f"📋 Found {len(configs)} SFTP configurations")
    
    # Initialize SFTP user manager
    sftp_manager = SftpUserManager()
    
    if not sftp_manager.authenticate():
        print("❌ Failed to authenticate with SFTPGo")
        return
    
    # Create users for each configuration
    success_count = 0
    for config_data in configs:
        sftp_config = config_data['sftp_config']
        partner = config_data['partner']
        
        username = sftp_config.sftp_username
        # For production, you'd want to get this from a secure source
        # For now, using a default pattern
        password = f"{username.replace('-', '_')}_secure_pass_123"
        tenant_id = sftp_config.tenant_id
        partner_name = partner.name
        
        if sftp_manager.create_user(username, password, tenant_id, partner_name):
            success_count += 1
        else:
            print(f"❌ Failed to create user for {partner_name}")
    
    print(f"\n✅ Successfully created/updated {success_count}/{len(configs)} SFTPGo users")
    
    # List all users
    users = sftp_manager.list_users()
    if users:
        print(f"\n📋 Current SFTPGo users:")
        for user in users:
            print(f"  - {user['username']} ({user.get('description', 'No description')})")
    
    print(f"\n🌐 SFTPGo Web Admin: http://localhost:8080/web/admin/")
    print(f"🔑 Admin credentials: admin / admin123")
    print(f"📡 SFTP Connection: localhost:2022")
    print(f"💾 Storage Backend: MinIO S3 ({settings.STORAGE_ENDPOINT_URL})")
    
    print(f"\n📋 SFTP Connection Details:")
    for config_data in configs:
        sftp_config = config_data['sftp_config']
        partner = config_data['partner']
        username = sftp_config.sftp_username
        password = f"{username.replace('-', '_')}_secure_pass_123"
        print(f"  - {username}:{password} ({partner.name})")


if __name__ == "__main__":
    asyncio.run(main())