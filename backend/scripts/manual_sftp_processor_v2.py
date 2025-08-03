#!/usr/bin/env python3
"""
Multi-Tenant Manual SFTP File Processor
=======================================

This script provides proper multi-tenant SFTP file processing with explicit tenant+partner addressing.

Usage Examples:
    # Process files for specific tenant+partner
    python scripts/manual_sftp_processor_v2.py --tenant tenant-a --partner "United Health Group (Professional)"
    
    # Process all partners for a specific tenant
    python scripts/manual_sftp_processor_v2.py --tenant tenant-a --all-partners
    
    # Process all partners for all tenants
    python scripts/manual_sftp_processor_v2.py --all-tenants --all-partners
    
    # List all tenants
    python scripts/manual_sftp_processor_v2.py --list-tenants
    
    # List partners for specific tenant
    python scripts/manual_sftp_processor_v2.py --tenant tenant-a --list-partners
    
    # Process specific file
    python scripts/manual_sftp_processor_v2.py --file-key sftp/tenant-a/tenant-a_uhg-pro/in/test.edi

Architecture:
    - Explicit tenant+partner addressing
    - Multi-tenant database queries
    - Proper isolation and security
    - Clear audit trails
"""

import asyncio
import argparse
import boto3
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

# Add backend to path for imports
backend_path = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_path))

try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    from src.core.config import settings
    from src.models.sftp_configuration import SftpConfiguration
    from src.models.trading_partner import TradingPartner
    from src.services.validation_service import ValidationService
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Make sure you're running this from the project root directory")
    print("💡 And that backend services are running: ./run.sh dev:start")
    sys.exit(1)


class MultiTenantSftpProcessor:
    """Multi-tenant SFTP file processor with proper tenant+partner addressing."""
    
    def __init__(self):
        self.s3_client = None
        self.db_session = None
        self.validation_service = None
        
    async def initialize(self):
        """Initialize database and S3 connections."""
        print("🔧 Initializing multi-tenant SFTP processor...")
        
        # Setup S3 client
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.STORAGE_ENDPOINT_URL,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY,
            aws_secret_access_key=settings.STORAGE_SECRET_KEY
        )
        
        # Setup database
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        self.db_session = AsyncSessionLocal()
        
        # Initialize validation service
        self.validation_service = ValidationService(self.db_session)
        
        print("✅ Initialization complete")
    
    async def list_tenants(self) -> List[str]:
        """List all tenants with SFTP configurations."""
        result = await self.db_session.execute(
            select(SftpConfiguration.tenant_id).distinct()
        )
        return [row[0] for row in result.fetchall()]
    
    async def list_partners_for_tenant(self, tenant_id: str) -> List[Dict[str, Any]]:
        """List all partners for a specific tenant."""
        result = await self.db_session.execute(
            select(TradingPartner, SftpConfiguration)
            .join(SftpConfiguration, TradingPartner.id == SftpConfiguration.partner_id)
            .where(TradingPartner.tenant_id == tenant_id)
            .where(SftpConfiguration.sftp_enabled == True)
        )
        
        partners = []
        for partner, sftp_config in result.fetchall():
            partners.append({
                'partner': partner,
                'sftp_config': sftp_config,
                'partner_name': partner.name,
                'partner_id': partner.id,
                'sftp_username': sftp_config.sftp_username,
                'tenant_id': tenant_id
            })
        
        return partners
    
    async def get_partner_by_name(self, tenant_id: str, partner_name: str) -> Optional[Dict[str, Any]]:
        """Get specific partner by tenant+name combination."""
        result = await self.db_session.execute(
            select(TradingPartner, SftpConfiguration)
            .join(SftpConfiguration, TradingPartner.id == SftpConfiguration.partner_id)
            .where(TradingPartner.tenant_id == tenant_id)
            .where(TradingPartner.name == partner_name)
            .where(SftpConfiguration.sftp_enabled == True)
        )
        
        row = result.first()
        if not row:
            return None
        
        partner, sftp_config = row
        return {
            'partner': partner,
            'sftp_config': sftp_config,
            'partner_name': partner.name,
            'partner_id': partner.id,
            'sftp_username': sftp_config.sftp_username,
            'tenant_id': tenant_id
        }
    
    async def get_s3_paths(self, tenant_id: str, sftp_username: str) -> Dict[str, str]:
        """Generate S3 paths for tenant+partner combination."""
        return {
            'inbound': f'sftp/{tenant_id}/{sftp_username}/in/',
            'outbound': f'sftp/{tenant_id}/{sftp_username}/out/',
            'archive': f'sftp/{tenant_id}/.archive/{sftp_username}/'
        }
    
    async def discover_files(self, inbound_path: str) -> List[str]:
        """Discover files in partner's inbound directory."""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=settings.STORAGE_BUCKET,
                Prefix=inbound_path
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    if not obj['Key'].endswith('/'):
                        files.append(obj['Key'])
            
            return files
        except Exception as e:
            print(f"❌ Error discovering files in {inbound_path}: {e}")
            return []
    
    async def process_file(self, file_key: str, partner_info: Dict[str, Any]) -> bool:
        """Process a single EDI file through the complete workflow."""
        file_name = file_key.split('/')[-1]
        partner = partner_info['partner']
        tenant_id = partner_info['tenant_id']
        
        print(f"\n🔄 Processing: {file_name}")
        print(f"🏢 Tenant: {tenant_id}")
        print(f"📂 Partner: {partner.name}")
        print(f"👤 SFTP User: {partner_info['sftp_username']}")
        print("-" * 60)
        
        try:
            # Step 1: Download file content
            response = self.s3_client.get_object(Bucket=settings.STORAGE_BUCKET, Key=file_key)
            edi_content = response['Body'].read().decode('utf-8')
            
            print(f"📊 File size: {len(edi_content)} characters")
            print(f"📋 ISA segment: {edi_content.split('~')[0] if '~' in edi_content else 'Invalid format'}")
            
            # Step 2: Process through validation service
            print("🔍 Starting EDI validation...")
            validation_result = await self.validation_service.process_edi_file(
                edi_data=edi_content,
                file_name=file_name,
                tenant_id=tenant_id,
                user_id=f'sftp-processor-{tenant_id}',
                username=f'multi-tenant-processor'
            )
            
            print(f"✅ Validation completed!")
            print(f"📊 Status: {validation_result.status}")
            print(f"📋 Findings: {len(validation_result.findings)} items")
            
            # Show sample findings
            if validation_result.findings:
                print("\n📝 Sample Validation Findings:")
                for i, finding in enumerate(validation_result.findings[:3]):
                    print(f"  {i+1}. [{finding.level.upper()}] {finding.message}")
                    if hasattr(finding, 'location') and finding.location:
                        loc = finding.location
                        print(f"      → Segment: {loc.segment_id}, Element: {loc.element_position}")
                
                if len(validation_result.findings) > 3:
                    print(f"  ... and {len(validation_result.findings) - 3} more findings")
            
            # Step 3: Generate S3 paths
            s3_paths = await self.get_s3_paths(tenant_id, partner_info['sftp_username'])
            
            # Step 4: Handle acknowledgments
            response_files_created = 0
            
            # TA1 Acknowledgment
            if validation_result.ta1_acknowledgement:
                ta1_key = file_key.replace('/in/', '/out/').replace('.edi', '_TA1.txt')
                self.s3_client.put_object(
                    Bucket=settings.STORAGE_BUCKET,
                    Key=ta1_key,
                    Body=validation_result.ta1_acknowledgement.encode('utf-8'),
                    ContentType='text/plain'
                )
                print(f"📤 TA1 delivered: {ta1_key}")
                print(f"📋 TA1 content: {validation_result.ta1_acknowledgement}")
                response_files_created += 1
            
            # 999 Acknowledgment (if available)
            if hasattr(validation_result, 'ack999_acknowledgement') and validation_result.ack999_acknowledgement:
                ack999_key = file_key.replace('/in/', '/out/').replace('.edi', '_999.txt')
                self.s3_client.put_object(
                    Bucket=settings.STORAGE_BUCKET,
                    Key=ack999_key,
                    Body=validation_result.ack999_acknowledgement.encode('utf-8'),
                    ContentType='text/plain'
                )
                print(f"📤 999 delivered: {ack999_key}")
                response_files_created += 1
            
            # Step 5: Archive original file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_key = f"{s3_paths['archive']}{file_name.replace('.edi', f'_{timestamp}.edi')}"
            self.s3_client.copy_object(
                Bucket=settings.STORAGE_BUCKET,
                CopySource={'Bucket': settings.STORAGE_BUCKET, 'Key': file_key},
                Key=archive_key
            )
            print(f"📦 File archived: {archive_key}")
            
            # Step 6: Remove from inbound directory
            self.s3_client.delete_object(
                Bucket=settings.STORAGE_BUCKET,
                Key=file_key
            )
            print(f"🧹 Removed from inbound: {file_name}")
            
            # Step 7: Commit database changes
            await self.db_session.commit()
            
            print(f"\n🎉 Processing completed successfully!")
            print(f"🏢 Tenant: {tenant_id}")
            print(f"📂 Partner: {partner.name}")
            print(f"📤 Response files created: {response_files_created}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error processing {file_name}: {str(e)}")
            import traceback
            print("📋 Full error details:")
            traceback.print_exc()
            return False
    
    async def process_tenant_partner(self, tenant_id: str, partner_name: str) -> Dict[str, Any]:
        """Process files for specific tenant+partner combination."""
        print(f"\n🏢 Processing Tenant: {tenant_id}")
        print(f"📂 Partner: {partner_name}")
        print("=" * 80)
        
        # Get partner information
        partner_info = await self.get_partner_by_name(tenant_id, partner_name)
        if not partner_info:
            print(f"❌ Partner '{partner_name}' not found in tenant '{tenant_id}'")
            return {'success': False, 'error': 'Partner not found'}
        
        # Get S3 paths
        s3_paths = await self.get_s3_paths(tenant_id, partner_info['sftp_username'])
        
        # Discover files
        files = await self.discover_files(s3_paths['inbound'])
        if not files:
            print(f"📂 No files found in {s3_paths['inbound']}")
            return {'success': True, 'files_processed': 0, 'message': 'No files to process'}
        
        print(f"📁 Found {len(files)} file(s) to process:")
        for file_key in files:
            file_name = file_key.split('/')[-1]
            print(f"  - {file_name}")
        
        # Process each file
        results = {
            'success': True,
            'tenant_id': tenant_id,
            'partner_name': partner_name,
            'files_processed': 0,
            'files_failed': 0,
            'details': []
        }
        
        for file_key in files:
            file_name = file_key.split('/')[-1]
            success = await self.process_file(file_key, partner_info)
            
            if success:
                results['files_processed'] += 1
                results['details'].append({'file': file_name, 'status': 'success'})
            else:
                results['files_failed'] += 1
                results['details'].append({'file': file_name, 'status': 'failed'})
        
        return results
    
    async def process_tenant_all_partners(self, tenant_id: str) -> Dict[str, Any]:
        """Process files for all partners in a specific tenant."""
        print(f"\n🏢 Processing all partners for tenant: {tenant_id}")
        print("=" * 80)
        
        partners = await self.list_partners_for_tenant(tenant_id)
        if not partners:
            print(f"❌ No SFTP-enabled partners found for tenant '{tenant_id}'")
            return {'success': False, 'error': 'No partners found'}
        
        overall_results = {
            'success': True,
            'tenant_id': tenant_id,
            'partners_processed': 0,
            'total_files_processed': 0,
            'total_files_failed': 0,
            'partner_details': []
        }
        
        for partner_info in partners:
            partner_results = await self.process_tenant_partner(tenant_id, partner_info['partner_name'])
            
            overall_results['partners_processed'] += 1
            overall_results['total_files_processed'] += partner_results.get('files_processed', 0)
            overall_results['total_files_failed'] += partner_results.get('files_failed', 0)
            overall_results['partner_details'].append({
                'partner': partner_info['partner_name'],
                'results': partner_results
            })
        
        return overall_results
    
    async def process_all_tenants_all_partners(self) -> Dict[str, Any]:
        """Process files for all partners across all tenants."""
        print("\n🌐 Processing all partners for all tenants")
        print("=" * 80)
        
        tenants = await self.list_tenants()
        if not tenants:
            print("❌ No tenants found")
            return {'success': False, 'error': 'No tenants found'}
        
        overall_results = {
            'success': True,
            'tenants_processed': 0,
            'total_partners_processed': 0,
            'total_files_processed': 0,
            'total_files_failed': 0,
            'tenant_details': []
        }
        
        for tenant_id in tenants:
            tenant_results = await self.process_tenant_all_partners(tenant_id)
            
            overall_results['tenants_processed'] += 1
            overall_results['total_partners_processed'] += tenant_results.get('partners_processed', 0)
            overall_results['total_files_processed'] += tenant_results.get('total_files_processed', 0)
            overall_results['total_files_failed'] += tenant_results.get('total_files_failed', 0)
            overall_results['tenant_details'].append({
                'tenant': tenant_id,
                'results': tenant_results
            })
        
        return overall_results
    
    async def cleanup(self):
        """Clean up resources."""
        if self.db_session:
            await self.db_session.close()


async def main():
    """Main function with proper multi-tenant command line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Multi-Tenant SFTP File Processor for EDI Lens",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Multi-Tenant Usage Examples:
  # Process files for specific tenant+partner
  python scripts/manual_sftp_processor_v2.py --tenant tenant-a --partner "United Health Group (Professional)"
  
  # Process all partners for a specific tenant
  python scripts/manual_sftp_processor_v2.py --tenant tenant-a --all-partners
  
  # Process all partners for all tenants
  python scripts/manual_sftp_processor_v2.py --all-tenants --all-partners
  
  # List all tenants
  python scripts/manual_sftp_processor_v2.py --list-tenants
  
  # List partners for specific tenant
  python scripts/manual_sftp_processor_v2.py --tenant tenant-a --list-partners
  
  # Process specific file by S3 key
  python scripts/manual_sftp_processor_v2.py --file-key sftp/tenant-a/tenant-a_uhg-pro/in/test.edi
        """
    )
    
    # Tenant specification
    parser.add_argument('--tenant', help='Specify tenant ID (e.g., tenant-a)')
    parser.add_argument('--all-tenants', action='store_true', help='Process all tenants')
    
    # Partner specification
    parser.add_argument('--partner', help='Specify partner name (e.g., "United Health Group (Professional)")')
    parser.add_argument('--all-partners', action='store_true', help='Process all partners (requires --tenant or --all-tenants)')
    
    # Information commands
    parser.add_argument('--list-tenants', action='store_true', help='List all available tenants')
    parser.add_argument('--list-partners', action='store_true', help='List partners for specified tenant (requires --tenant)')
    
    # Direct file processing
    parser.add_argument('--file-key', help='Process specific file by S3 key')
    
    args = parser.parse_args()
    
    # Validation
    if not any([args.tenant, args.all_tenants, args.list_tenants, args.file_key]):
        parser.error("Must specify --tenant, --all-tenants, --list-tenants, or --file-key")
    
    if args.list_partners and not args.tenant:
        parser.error("--list-partners requires --tenant")
    
    if args.all_partners and not (args.tenant or args.all_tenants):
        parser.error("--all-partners requires --tenant or --all-tenants")
    
    if args.partner and not args.tenant:
        parser.error("--partner requires --tenant")
    
    print("🚀 EDI Lens Multi-Tenant SFTP File Processor")
    print("=" * 60)
    
    processor = MultiTenantSftpProcessor()
    
    try:
        await processor.initialize()
        
        if args.list_tenants:
            tenants = await processor.list_tenants()
            print(f"\n📋 Available Tenants ({len(tenants)}):")
            for tenant_id in tenants:
                partners = await processor.list_partners_for_tenant(tenant_id)
                print(f"  🏢 {tenant_id} ({len(partners)} SFTP partners)")
        
        elif args.list_partners:
            partners = await processor.list_partners_for_tenant(args.tenant)
            print(f"\n📋 SFTP Partners for Tenant '{args.tenant}' ({len(partners)}):")
            for partner_info in partners:
                print(f"  📂 {partner_info['partner_name']}")
                print(f"     SFTP User: {partner_info['sftp_username']}")
                print(f"     Partner ID: {partner_info['partner_id']}")
                print()
        
        elif args.file_key:
            # Extract tenant info from file key for proper processing
            key_parts = args.file_key.split('/')
            if len(key_parts) >= 4 and key_parts[0] == 'sftp':
                tenant_id = key_parts[1]
                sftp_username = key_parts[2]
                
                # Find partner by SFTP username
                partners = await processor.list_partners_for_tenant(tenant_id)
                partner_info = None
                for p in partners:
                    if p['sftp_username'] == sftp_username:
                        partner_info = p
                        break
                
                if partner_info:
                    success = await processor.process_file(args.file_key, partner_info)
                    print(f"\n📊 Result: {'✅ Success' if success else '❌ Failed'}")
                else:
                    print(f"❌ Partner not found for SFTP username: {sftp_username}")
            else:
                print(f"❌ Invalid file key format: {args.file_key}")
        
        elif args.tenant and args.partner:
            results = await processor.process_tenant_partner(args.tenant, args.partner)
            print(f"\n📊 Final Results:")
            print(f"🏢 Tenant: {results.get('tenant_id', 'N/A')}")
            print(f"📂 Partner: {results.get('partner_name', 'N/A')}")
            print(f"✅ Files processed: {results.get('files_processed', 0)}")
            print(f"❌ Files failed: {results.get('files_failed', 0)}")
        
        elif args.tenant and args.all_partners:
            results = await processor.process_tenant_all_partners(args.tenant)
            print(f"\n📊 Tenant Results:")
            print(f"🏢 Tenant: {results['tenant_id']}")
            print(f"📂 Partners processed: {results['partners_processed']}")
            print(f"✅ Total files processed: {results['total_files_processed']}")
            print(f"❌ Total files failed: {results['total_files_failed']}")
        
        elif args.all_tenants and args.all_partners:
            results = await processor.process_all_tenants_all_partners()
            print(f"\n📊 Overall Results:")
            print(f"🏢 Tenants processed: {results['tenants_processed']}")
            print(f"📂 Total partners processed: {results['total_partners_processed']}")
            print(f"✅ Total files processed: {results['total_files_processed']}")
            print(f"❌ Total files failed: {results['total_files_failed']}")
    
    except KeyboardInterrupt:
        print("\n⏹️  Processing interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await processor.cleanup()


if __name__ == "__main__":
    asyncio.run(main())