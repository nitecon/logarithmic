"""Structured logging configuration for Logarithmic.

This module provides JSON-formatted structured logging for production use,
with fallback to human-readable text format for development.
"""

import json
import logging
import sys
from datetime import datetime
from datetime import timezone
from typing import Any

from logarithmic.config import get_config


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging.
    
    Outputs log records as JSON objects with consistent fields for
    observability tools like Datadog, Splunk, or OpenTelemetry.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON.
        
        Args:
            record: The log record to format
            
        Returns:
            JSON-formatted log string
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from the 'extra' parameter
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add any custom attributes added via 'extra' in logging calls
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "extra_fields",
            ]:
                log_data[key] = value

        return json.dumps(log_data)


def configure_logging() -> None:
    """Configure application-wide logging based on config settings.
    
    Sets up either JSON structured logging or human-readable text logging
    based on the LOG_FORMAT configuration value.
    """
    config = get_config()

    # Determine log level
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Set formatter based on config
    if config.log_format.lower() == "json":
        formatter = JsonFormatter()
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "log_level": config.log_level,
            "log_format": config.log_format,
        },
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.
    
    This is a convenience wrapper around logging.getLogger that ensures
    logging is configured before returning the logger.
    
    Args:
        name: The name for the logger (typically __name__)
        
    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)
