"""
Logging configuration for EDI Lens CLI.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(debug: bool = False):
    """Setup logging configuration for the CLI."""
    # Create logs directory
    logs_dir = Path(__file__).parent.parent.parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Configure logging level
    level = logging.DEBUG if debug else logging.INFO
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup file handler
    log_file = logs_dir / f"edi-lens-cli-{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Setup console handler (only for errors and warnings)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str):
    """Get a logger instance for a specific module."""
    return logging.getLogger(name)