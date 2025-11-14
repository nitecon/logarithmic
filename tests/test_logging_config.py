"""Tests for the logging configuration module."""

import json
import logging
from io import StringIO

import pytest

from logarithmic.config import LogarithmicConfig
from logarithmic.logging_config import JsonFormatter
from logarithmic.logging_config import configure_logging
from logarithmic.logging_config import get_logger


def test_json_formatter() -> None:
    """Test that JsonFormatter produces valid JSON output."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="/path/to/file.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    
    output = formatter.format(record)
    
    # Should be valid JSON
    data = json.loads(output)
    
    assert data["level"] == "INFO"
    assert data["logger"] == "test.logger"
    assert data["message"] == "Test message"
    assert data["line"] == 42
    assert "timestamp" in data


def test_json_formatter_with_exception() -> None:
    """Test that JsonFormatter includes exception info."""
    formatter = JsonFormatter()
    
    try:
        raise ValueError("Test error")
    except ValueError:
        import sys
        exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert data["level"] == "ERROR"
        assert "exception" in data
        assert "ValueError" in data["exception"]
        assert "Test error" in data["exception"]


def test_configure_logging_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test logging configuration with JSON format."""
    monkeypatch.setenv("LOGARITHMIC_LOG_FORMAT", "json")
    monkeypatch.setenv("LOGARITHMIC_LOG_LEVEL", "DEBUG")
    
    # Force config reload
    from logarithmic.config import reload_config
    reload_config()
    
    configure_logging()
    
    # Get root logger and check it's configured
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) > 0
    
    # Check that the formatter is JsonFormatter
    handler = root_logger.handlers[0]
    assert isinstance(handler.formatter, JsonFormatter)


def test_configure_logging_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test logging configuration with text format."""
    monkeypatch.setenv("LOGARITHMIC_LOG_FORMAT", "text")
    monkeypatch.setenv("LOGARITHMIC_LOG_LEVEL", "INFO")
    
    # Force config reload
    from logarithmic.config import reload_config
    reload_config()
    
    configure_logging()
    
    # Get root logger and check it's configured
    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO
    assert len(root_logger.handlers) > 0
    
    # Check that the formatter is NOT JsonFormatter
    handler = root_logger.handlers[0]
    assert not isinstance(handler.formatter, JsonFormatter)


def test_get_logger() -> None:
    """Test that get_logger returns a logger instance."""
    logger = get_logger("test.module")
    
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test.module"
