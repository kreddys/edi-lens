# FILE: backend/scripts/manual_sftp_processor_v2.py
# This script is now a simple entrypoint to the SftpFileProcessor service.

import asyncio
import argparse
import sys
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.core.config import settings
from src.services.sftp_file_processor import SftpFileProcessor

async def main():
    parser = argparse.ArgumentParser(description="Manual SFTP File Processor for EDI Lens")
    parser.add_argument("--run", action="store_true", help="Run the SFTP processor once.")
    args = parser.parse_args()

    if not args.run:
        print("Please specify --run to execute the processor.")
        sys.exit(1)
    
    print("🚀 EDI Lens Manual SFTP File Processor")
    print("=" * 60)
    
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as session:
        try:
            processor = SftpFileProcessor(session)
            await processor.process_all_sftp_partners()
            print("\n✅ Processing run completed successfully.")
        except Exception as e:
            print(f"\n❌ An unexpected error occurred: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())