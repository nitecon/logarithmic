"""Tests for the MCP bridge module."""

from unittest.mock import Mock

import pytest

from logarithmic.log_manager import LogManager
from logarithmic.mcp_bridge import McpBridge
from logarithmic.settings import Settings


def test_mcp_bridge_initialization(mock_settings) -> None:
    """Test MCP bridge initialization."""
    log_manager = LogManager()
    settings = Settings()
    
    bridge = McpBridge(log_manager, settings)
    
    assert bridge is not None


def test_mcp_bridge_log_content(mock_settings) -> None:
    """Test that MCP bridge receives log content."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)
    
    # Set up metadata
    settings.set_log_metadata("test.log", "log-001", "Test log")
    
    # Subscribe bridge to log
    log_manager.subscribe("test.log", bridge)
    
    # Publish content
    log_manager.publish_content("test.log", "Test content line 1\n")
    
    # Bridge should have received the content
    # (We can't easily test the internal state without exposing it,
    # but we can verify it doesn't crash)


def test_mcp_bridge_log_cleared(mock_settings) -> None:
    """Test that MCP bridge handles log cleared events."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)
    
    settings.set_log_metadata("test.log", "log-001", "Test log")
    log_manager.subscribe("test.log", bridge)
    
    # Should not crash
    log_manager.publish_cleared("test.log")


def test_mcp_bridge_stream_interrupted(mock_settings) -> None:
    """Test that MCP bridge handles stream interrupted events."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)
    
    settings.set_log_metadata("test.log", "log-001", "Test log")
    log_manager.subscribe("test.log", bridge)
    
    # Should not crash
    log_manager.publish_stream_interrupted("test.log", "Connection lost")


def test_mcp_bridge_stream_resumed(mock_settings) -> None:
    """Test that MCP bridge handles stream resumed events."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)
    
    settings.set_log_metadata("test.log", "log-001", "Test log")
    log_manager.subscribe("test.log", bridge)
    
    # Should not crash
    log_manager.publish_stream_resumed("test.log")


def test_mcp_bridge_register_callback(mock_settings) -> None:
    """Test registering update callbacks."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)
    
    callback_called = []
    
    def test_callback(path: str, content: str) -> None:
        callback_called.append((path, content))
    
    bridge.register_update_callback("log-001", test_callback)
    
    # Set up metadata and subscribe
    settings.set_log_metadata("test.log", "log-001", "Test log")
    log_manager.subscribe("test.log", bridge)
    
    # Publish content
    log_manager.publish_content("test.log", "Test line\n")
    
    # Callback should have been called
    assert len(callback_called) > 0
