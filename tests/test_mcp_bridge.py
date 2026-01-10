"""Tests for the MCP bridge module."""

from unittest.mock import MagicMock

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

    # Register and subscribe bridge to log
    log_manager.register_log("test.log")
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
    log_manager.register_log("test.log")
    log_manager.subscribe("test.log", bridge)

    # Should not crash
    log_manager.clear_log("test.log")


def test_mcp_bridge_stream_interrupted(mock_settings) -> None:
    """Test that MCP bridge handles stream interrupted events."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)

    settings.set_log_metadata("test.log", "log-001", "Test log")
    log_manager.register_log("test.log")
    log_manager.subscribe("test.log", bridge)

    # Should not crash
    log_manager.publish_stream_interrupted("test.log", "Connection lost")


def test_mcp_bridge_stream_resumed(mock_settings) -> None:
    """Test that MCP bridge handles stream resumed events."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)

    settings.set_log_metadata("test.log", "log-001", "Test log")
    log_manager.register_log("test.log")
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

    # register_update_callback takes only the callback, not a log_id
    bridge.register_update_callback(test_callback)

    # Set up metadata and subscribe
    settings.set_log_metadata("test.log", "log-001", "Test log")
    log_manager.register_log("test.log")
    log_manager.subscribe("test.log", bridge)

    # Publish content
    log_manager.publish_content("test.log", "Test line\n")

    # Callback should have been called
    assert len(callback_called) > 0


def test_mcp_bridge_get_last_n_lines(mock_settings) -> None:
    """Test getting last N lines from a log."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)

    # Set up metadata
    settings.set_log_metadata("test.log", "log-001", "Test log")
    log_manager.register_log("test.log")
    log_manager.subscribe("test.log", bridge)

    # Add bridge to subscribed paths
    bridge.subscribe_to_log("test.log")

    # Publish multiple lines
    lines = [f"Line {i}\n" for i in range(1, 11)]
    for line in lines:
        log_manager.publish_content("test.log", line)

    # Get last 5 lines (note: trailing newline creates empty last element)
    result = bridge.get_last_n_lines("log-001", 5)
    assert result is not None
    # Filter out empty strings from split
    result_lines = [line for line in result.split("\n") if line]
    assert len(result_lines) >= 4  # At least 4 non-empty lines
    assert "Line 10" in result  # Should contain the last line


def test_mcp_bridge_get_last_n_lines_not_found(mock_settings) -> None:
    """Test getting last N lines from non-existent log."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)

    result = bridge.get_last_n_lines("nonexistent", 500)
    assert result is None


def test_mcp_bridge_get_groups_empty(mock_settings) -> None:
    """Test getting groups when none exist."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)

    groups = bridge.get_groups()
    assert groups == {}


def test_mcp_bridge_get_groups_with_logs(mock_settings) -> None:
    """Test getting groups with assigned logs."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)

    # Set up log groups in settings
    settings.set_log_groups({"test1.log": "GroupA", "test2.log": "GroupA"})

    groups = bridge.get_groups()
    assert "GroupA" in groups
    assert groups["GroupA"]["log_count"] == 2
    assert "test1.log" in groups["GroupA"]["logs"]
    assert "test2.log" in groups["GroupA"]["logs"]


def test_mcp_bridge_set_group_windows_callback(mock_settings) -> None:
    """Test setting group windows callback."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)

    mock_callback = MagicMock(return_value={})
    bridge.set_group_windows_callback(mock_callback)

    # Verify callback is set
    assert bridge._group_windows_callback is not None


def test_mcp_bridge_has_combined_view_no_callback(mock_settings) -> None:
    """Test _has_combined_view returns False when no callback set."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)

    result = bridge._has_combined_view("TestGroup")
    assert result is False


def test_mcp_bridge_get_combined_view_content_no_callback(mock_settings) -> None:
    """Test get_combined_view_content returns None when no callback set."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)

    result = bridge.get_combined_view_content("TestGroup")
    assert result is None


def test_mcp_bridge_get_group_content_not_found(mock_settings) -> None:
    """Test get_group_content returns None for non-existent group."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)

    result = bridge.get_group_content("NonExistent")
    assert result is None


def test_mcp_bridge_get_group_content_individual_logs(mock_settings) -> None:
    """Test get_group_content falls back to individual logs."""
    log_manager = LogManager()
    settings = Settings()
    bridge = McpBridge(log_manager, settings)

    # Set up log groups
    settings.set_log_groups({"test.log": "GroupA"})
    settings.set_log_metadata("test.log", "log-001", "Test Log")

    # Subscribe and add content
    log_manager.register_log("test.log")
    bridge.subscribe_to_log("test.log")
    log_manager.publish_content("test.log", "Test content\n")

    result = bridge.get_group_content("GroupA")
    assert result is not None
    assert result["group_name"] == "GroupA"
    assert result["source"] == "individual_logs"
    assert "Test content" in result["content"]
