#!/usr/bin/env python3
"""
EDI Lens CLI - Main Entry Point
Interactive CLI tool for managing NiFi flows and Registry operations.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add the project root to the path so we can import from the CLI modules
CLI_DIR = Path(__file__).parent
PROJECT_ROOT = CLI_DIR.parent.parent
sys.path.insert(0, str(CLI_DIR))

from cli_app import EDILensCLI
from utils.logger import setup_logging


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="EDI Lens CLI - Interactive NiFi Flow Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (default)
  python main.py

  # Non-interactive commands
  python main.py --command health-check
  python main.py --command deploy-flow --template simple-file-processing --params input_directory=/tmp/input output_directory=/tmp/output
  python main.py --command start-flow --process-group-id abc-123-def
  python main.py --command list-buckets
  python main.py --command flow-status --process-group-id abc-123-def

  # Batch operations
  python main.py --batch-file commands.txt

  # Quiet mode (minimal output)
  python main.py --command health-check --quiet
        """
    )
    
    parser.add_argument(
        "--command", "-c",
        help="Execute a specific command non-interactively",
        choices=[
            "health-check", "system-status", "deploy-flow", "start-flow", "stop-flow", 
            "delete-flow", "flow-status", "list-flows", "list-buckets", "list-flows-in-bucket",
            "commit-changes", "update-from-registry", "revert-changes", "check-modifications"
        ]
    )
    
    parser.add_argument(
        "--template", "-t",
        help="Flow template name for deploy-flow command"
    )
    
    parser.add_argument(
        "--process-group-id", "-p",
        help="Process Group ID for flow operations"
    )
    
    parser.add_argument(
        "--bucket-id", "-b",
        help="Registry bucket ID"
    )
    
    parser.add_argument(
        "--flow-id", "-f",
        help="Registry flow ID"
    )
    
    parser.add_argument(
        "--params",
        help="Flow parameters in format: key1=value1 key2=value2",
        nargs="*"
    )
    
    parser.add_argument(
        "--comments",
        help="Comments for version control operations",
        default="Automated operation"
    )
    
    parser.add_argument(
        "--auto-start",
        help="Auto-start flow after deployment",
        action="store_true"
    )
    
    parser.add_argument(
        "--remove-from-registry",
        help="Remove flow from registry when deleting",
        action="store_true"
    )
    
    parser.add_argument(
        "--batch-file",
        help="Execute commands from a batch file",
        type=Path
    )
    
    parser.add_argument(
        "--quiet", "-q",
        help="Minimal output mode",
        action="store_true"
    )
    
    parser.add_argument(
        "--output-format",
        help="Output format for data",
        choices=["table", "json", "yaml"],
        default="table"
    )
    
    parser.add_argument(
        "--backend-url",
        help="Override backend URL",
        default=None
    )
    
    parser.add_argument(
        "--debug",
        help="Enable debug mode",
        action="store_true"
    )
    
    return parser.parse_args()


async def main():
    """Main entry point for the CLI application."""
    args = parse_arguments()
    
    # Setup logging
    setup_logging(debug=args.debug)
    
    # Create CLI application
    app = EDILensCLI(
        non_interactive=bool(args.command or args.batch_file),
        quiet_mode=args.quiet,
        output_format=args.output_format,
        backend_url=args.backend_url
    )
    
    # Execute based on mode
    if args.batch_file:
        await app.run_batch_file(args.batch_file)
    elif args.command:
        await app.run_command(args.command, args)
    else:
        await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)