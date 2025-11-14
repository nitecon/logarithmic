"""Application configuration using pydantic-settings.

This module provides environment-based configuration for the Logarithmic application.
Configuration values are loaded from environment variables with sensible defaults.
"""

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class LogarithmicConfig(BaseSettings):
    """Application configuration loaded from environment variables.
    
    All configuration values can be overridden via environment variables
    prefixed with LOGARITHMIC_ (e.g., LOGARITHMIC_LOG_LEVEL=DEBUG).
    """

    model_config = SettingsConfigDict(
        env_prefix="LOGARITHMIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    log_format: str = Field(
        default="json",
        description="Log format: 'json' for structured logging or 'text' for human-readable",
    )

    # MCP Server Configuration
    mcp_server_enabled: bool = Field(
        default=False,
        description="Enable MCP server on startup",
    )
    mcp_server_host: str = Field(
        default="127.0.0.1",
        description="MCP server binding address",
    )
    mcp_server_port: int = Field(
        default=3000,
        description="MCP server port",
    )

    # Application Settings
    settings_dir: str = Field(
        default="~/.logarithmic",
        description="Directory for storing application settings",
    )
    default_session: str = Field(
        default="default",
        description="Default session name",
    )

    # UI Settings
    default_window_width: int = Field(
        default=1000,
        description="Default window width in pixels",
    )
    default_window_height: int = Field(
        default=800,
        description="Default window height in pixels",
    )
    default_font_size: int = Field(
        default=9,
        description="Default font size for log content",
    )

    # Performance Settings
    max_buffer_size: int = Field(
        default=10000,
        description="Maximum number of lines to buffer in memory per log",
    )
    file_check_interval_ms: int = Field(
        default=100,
        description="File change check interval in milliseconds",
    )


# Global configuration instance
_config: LogarithmicConfig | None = None


def get_config() -> LogarithmicConfig:
    """Get the global configuration instance.
    
    Returns:
        The application configuration singleton.
    """
    global _config
    if _config is None:
        _config = LogarithmicConfig()
    return _config


def reload_config() -> LogarithmicConfig:
    """Reload configuration from environment.
    
    Returns:
        The reloaded configuration instance.
    """
    global _config
    _config = LogarithmicConfig()
    return _config
