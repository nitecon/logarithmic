"""Tests for the configuration module."""

import pytest

from logarithmic.config import LogarithmicConfig
from logarithmic.config import get_config
from logarithmic.config import reload_config


def test_default_config() -> None:
    """Test that default configuration values are set correctly."""
    config = LogarithmicConfig()

    assert config.log_level == "INFO"
    assert config.log_format == "json"
    assert config.mcp_server_enabled is False
    assert config.mcp_server_host == "127.0.0.1"
    assert config.mcp_server_port == 3000
    assert config.default_window_width == 1000
    assert config.default_window_height == 800


def test_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that configuration can be loaded from environment variables."""
    monkeypatch.setenv("LOGARITHMIC_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOGARITHMIC_MCP_SERVER_ENABLED", "true")
    monkeypatch.setenv("LOGARITHMIC_MCP_SERVER_PORT", "4000")

    config = LogarithmicConfig()

    assert config.log_level == "DEBUG"
    assert config.mcp_server_enabled is True
    assert config.mcp_server_port == 4000


def test_get_config_singleton() -> None:
    """Test that get_config returns a singleton instance."""
    config1 = get_config()
    config2 = get_config()

    assert config1 is config2


def test_reload_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that reload_config creates a new instance."""
    config1 = get_config()

    monkeypatch.setenv("LOGARITHMIC_LOG_LEVEL", "DEBUG")
    config2 = reload_config()

    assert config1 is not config2
    assert config2.log_level == "DEBUG"
