"""Comprehensive logging configuration for the EDI Lens backend."""

import logging
import logging.config
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import json
from pathlib import Path

from .config import Settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread_id": record.thread,
            "process_id": record.process,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from the record
        for key, value in record.__dict__.items():
            if key not in [
                "name", "levelno", "levelname", "pathname", "filename",
                "module", "lineno", "funcName", "created", "msecs",
                "relativeCreated", "thread", "threadName", "processName",
                "process", "getMessage", "exc_info", "exc_text", "stack_info",
                "args", "msg"
            ]:
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        """Format with colors for console output."""
        color = self.COLORS.get(record.levelname, '')
        reset = self.RESET
        
        # Color the level name
        original_levelname = record.levelname
        record.levelname = f"{color}{record.levelname}{reset}"
        
        formatted = super().format(record)
        record.levelname = original_levelname  # Restore original
        
        return formatted


def setup_logging(settings: Settings) -> None:
    """Configure comprehensive logging for the application."""

    # Determine log levels from environment variables
    console_log_level = settings.LOG_LEVEL_CONSOLE or ("DEBUG" if settings.DEBUG else "INFO")
    file_log_level = settings.LOG_LEVEL_FILE or "DEBUG"
    client_log_level = settings.LOG_LEVEL_CLIENTS or "INFO"
    service_log_level = settings.LOG_LEVEL_SERVICES or "INFO"
    api_log_level = settings.LOG_LEVEL_API or "INFO"
    
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Logging configuration
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "%(asctime)s | %(levelname)-8s | %(name)-30s | %(funcName)-20s:%(lineno)-4d | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "simple": {
                "format": "%(levelname)-8s | %(name)-20s | %(message)s"
            },
            "json": {
                "()": JSONFormatter,
            },
            "colored": {
                "()": ColoredFormatter,
                "format": "%(asctime)s | %(levelname)-8s | %(name)-30s | %(funcName)-20s:%(lineno)-4d | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": console_log_level,
                "formatter": "colored" if sys.stdout.isatty() else "simple",
                "stream": "ext://sys.stdout"
            },
            "file_all": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": file_log_level,
                "formatter": "detailed",
                "filename": "logs/edi_lens.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
            "file_error": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": "logs/edi_lens_errors.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
            "file_json": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": "logs/edi_lens.jsonl",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
            "audit": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": "logs/audit.jsonl",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
                "encoding": "utf8"
            }
        },
        "loggers": {
            # Root logger
            "": {
                "level": console_log_level,
                "handlers": ["console", "file_all", "file_error", "file_json"],
                "propagate": False
            },

            # Application loggers
            "src": {
                "level": "DEBUG",
                "handlers": ["console", "file_all", "file_error", "file_json"],
                "propagate": False
            },
            "src.clients": {
                "level": client_log_level,
                "handlers": ["console", "file_all", "file_error", "file_json"],
                "propagate": False
            },
            "src.services": {
                "level": service_log_level,
                "handlers": ["console", "file_all", "file_error", "file_json"],
                "propagate": False
            },
            "src.api": {
                "level": api_log_level,
                "handlers": ["console", "file_all", "file_error", "file_json"],
                "propagate": False
            },
            "src.core": {
                "level": "DEBUG",
                "handlers": ["console", "file_all", "file_error", "file_json"],
                "propagate": False
            },
            
            # Special audit logger
            "audit": {
                "level": "INFO",
                "handlers": ["audit"],
                "propagate": False
            },
            
            # Third-party loggers
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console", "file_all"],
                "propagate": False
            },
            "uvicorn.access": {
                "level": "INFO" if settings.DEBUG else "WARNING",
                "handlers": ["file_all"],
                "propagate": False
            },
            "fastapi": {
                "level": "INFO",
                "handlers": ["console", "file_all"],
                "propagate": False
            },
            "aiohttp": {
                "level": "WARNING",
                "handlers": ["file_all"],
                "propagate": False
            },
            "aiohttp.access": {
                "level": "WARNING",
                "handlers": ["file_all"],
                "propagate": False
            },
            "sqlalchemy": {
                "level": "WARNING",
                "handlers": ["file_all"],
                "propagate": False
            },
            "sqlalchemy.engine": {
                "level": "INFO" if settings.DEBUG else "WARNING",
                "handlers": ["file_all"],
                "propagate": False
            }
        }
    }
    
    # Apply the configuration
    logging.config.dictConfig(config)
    
    # Log the successful setup
    logger = logging.getLogger(__name__)
    logger.info("Logging system initialized - Console: %s, File: %s, Clients: %s, Services: %s, API: %s",
                console_log_level, file_log_level, client_log_level, service_log_level, api_log_level)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with consistent configuration."""
    return logging.getLogger(name)


def get_audit_logger() -> logging.Logger:
    """Get the dedicated audit logger."""
    return logging.getLogger("audit")


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""
    
    @property
    def logger(self) -> logging.Logger:
        """Get a logger for this class."""
        return get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")


class AuditLogger:
    """Dedicated audit logging utility."""
    
    def __init__(self):
        self.logger = get_audit_logger()
    
    def log_api_call(self, method: str, endpoint: str, user_id: Optional[str] = None, 
                    request_data: Optional[Dict[str, Any]] = None, 
                    response_status: Optional[int] = None,
                    execution_time_ms: Optional[float] = None) -> None:
        """Log API call for audit purposes."""
        self.logger.info(
            "API call audit",
            extra={
                "event_type": "api_call",
                "method": method,
                "endpoint": endpoint,
                "user_id": user_id,
                "request_data": request_data,
                "response_status": response_status,
                "execution_time_ms": execution_time_ms
            }
        )
    
    def log_flow_operation(self, operation: str, bucket_id: str, flow_id: str,
                          user_id: Optional[str] = None, 
                          details: Optional[Dict[str, Any]] = None) -> None:
        """Log flow operations for audit purposes."""
        self.logger.info(
            "Flow operation audit",
            extra={
                "event_type": "flow_operation",
                "operation": operation,
                "bucket_id": bucket_id,
                "flow_id": flow_id,
                "user_id": user_id,
                "details": details
            }
        )
    
    def log_system_event(self, event: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log system events for audit purposes."""
        self.logger.info(
            "System event audit",
            extra={
                "event_type": "system_event",
                "event": event,
                "details": details
            }
        )


# Global audit logger instance
audit_logger = AuditLogger()