"""Tests for the settings module."""

import json
import pytest
from pathlib import Path
from logarithmic.settings import Settings


def test_settings_initialization(mock_settings: Path) -> None:
    """Test that settings are initialized with default values."""
    settings = Settings()
    
    assert settings.get_current_session() == "default"
    assert settings.get_tracked_logs() == []
    assert settings.get_open_windows() == []
    assert settings.get_groups() == []


def test_add_tracked_log(mock_settings: Path) -> None:
    """Test adding a tracked log."""
    settings = Settings()
    
    settings.add_tracked_log("/path/to/log1.log")
    settings.add_tracked_log("/path/to/log2.log")
    
    tracked = settings.get_tracked_logs()
    assert len(tracked) == 2
    assert "/path/to/log1.log" in tracked
    assert "/path/to/log2.log" in tracked


def test_remove_tracked_log(mock_settings: Path) -> None:
    """Test removing a tracked log."""
    settings = Settings()
    
    settings.add_tracked_log("/path/to/log1.log")
    settings.add_tracked_log("/path/to/log2.log")
    settings.remove_tracked_log("/path/to/log1.log")
    
    tracked = settings.get_tracked_logs()
    assert len(tracked) == 1
    assert "/path/to/log2.log" in tracked


def test_window_position(mock_settings: Path) -> None:
    """Test setting and getting window position."""
    settings = Settings()
    
    settings.set_window_position("/path/to/log.log", 100, 200, 800, 600)
    position = settings.get_window_position("/path/to/log.log")
    
    assert position is not None
    assert position["x"] == 100
    assert position["y"] == 200
    assert position["width"] == 800
    assert position["height"] == 600


def test_session_management(mock_settings: Path) -> None:
    """Test session creation and switching."""
    settings = Settings()
    
    # Add some data to current session
    settings.add_tracked_log("/path/to/log1.log")
    
    # Save as new session
    settings.save_session_as("test_session")
    
    # Switch to new session (should be empty)
    settings.switch_session("test_session")
    assert settings.get_tracked_logs() == []
    
    # Switch back to default
    settings.switch_session("default")
    assert len(settings.get_tracked_logs()) == 1


def test_mcp_server_settings(mock_settings: Path) -> None:
    """Test MCP server settings."""
    settings = Settings()
    
    mcp_settings = settings.get_mcp_server_settings()
    assert mcp_settings["enabled"] is False
    assert mcp_settings["binding_address"] == "127.0.0.1"
    assert mcp_settings["port"] == 3000
    
    settings.set_mcp_server_enabled(True)
    settings.set_mcp_server_port(4000)
    
    mcp_settings = settings.get_mcp_server_settings()
    assert mcp_settings["enabled"] is True
    assert mcp_settings["port"] == 4000


def test_log_metadata(mock_settings: Path) -> None:
    """Test log metadata management."""
    settings = Settings()
    
    settings.set_log_metadata("log1", "id123", "Test log description")
    
    metadata = settings.get_log_metadata("log1")
    assert metadata is not None
    assert metadata["id"] == "id123"
    assert metadata["description"] == "Test log description"
    
    settings.remove_log_metadata("log1")
    assert settings.get_log_metadata("log1") is None
