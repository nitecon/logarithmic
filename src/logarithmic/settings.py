"""Settings management for persisting application state."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Settings:
    """Manages application settings persistence.

    Settings are stored in a JSON file in the user's home directory.
    """

    def __init__(self) -> None:
        """Initialize settings manager."""
        self.settings_dir = Path.home() / ".logarithmic"
        self.sessions_dir = self.settings_dir / "sessions"
        self.app_settings_file = self.settings_dir / "app_settings.json"
        self._current_session = "default"
        self._data: dict[str, Any] = {}
        self._ensure_directories()
        self._load_last_session()
        self._load()

    def _ensure_directories(self) -> None:
        """Ensure settings directories exist."""
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _load_last_session(self) -> None:
        """Load the last used session name."""
        if self.app_settings_file.exists():
            try:
                with open(self.app_settings_file, "r", encoding="utf-8") as f:
                    app_settings = json.load(f)
                    self._current_session = app_settings.get("last_session", "default")
                    logger.info(f"Loading last session: {self._current_session}")
            except Exception as e:
                logger.error(f"Failed to load app settings: {e}")
                self._current_session = "default"

    def _save_last_session(self) -> None:
        """Save the current session as the last used."""
        try:
            app_settings = {"last_session": self._current_session}
            with open(self.app_settings_file, "w", encoding="utf-8") as f:
                json.dump(app_settings, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save app settings: {e}")

    def _load(self) -> None:
        """Load settings from disk (loads current session)."""
        session_file = self.sessions_dir / f"{self._current_session}.json"

        if not session_file.exists():
            logger.info(f"No session file found for '{self._current_session}', using defaults")
            self._data = {
                "tracked_logs": [],
                "open_windows": [],
                "window_positions": {},
                "default_window_width": 1000,
                "default_window_height": 800,  # ~40 lines with controls
                "groups": [],  # List of group names
                "log_groups": {},  # path_key -> group_name mapping
                "main_window_position": None,  # Main window position/size
                "font_sizes": {  # Font size settings
                    "log_content": 9,
                    "ui_elements": 10,
                    "status_bar": 9
                },
                "theme": {  # Theme/color settings
                    "error_color": "#FF4444",      # Red for errors
                    "warning_color": "#FFA500",    # Orange for warnings
                    "verbose_color": "#888888",    # Gray for verbose
                    "default_color": "#CCCCCC"     # Default text color
                },
                "mcp_server": {  # MCP server settings
                    "enabled": False,
                    "binding_address": "127.0.0.1",
                    "port": 3000
                },
                "log_metadata": {}  # path_key -> {id, description} mapping
            }
            return

        try:
            with open(session_file, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            logger.info(f"Loaded session '{self._current_session}' from: {session_file}")

            # Ensure all keys exist
            if "open_windows" not in self._data:
                self._data["open_windows"] = []
            if "window_positions" not in self._data:
                self._data["window_positions"] = {}
            if "default_window_width" not in self._data:
                self._data["default_window_width"] = 1000
            if "default_window_height" not in self._data:
                self._data["default_window_height"] = 800
            if "groups" not in self._data:
                self._data["groups"] = []
            if "log_groups" not in self._data:
                self._data["log_groups"] = {}

        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            self._data = {
                "open_windows": [],
                "window_positions": {}
            }

    def _save(self) -> None:
        """Save settings to disk (saves to current session)."""
        session_file = self.sessions_dir / f"{self._current_session}.json"

        try:
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save session '{self._current_session}': {e}")

    def get_tracked_logs(self) -> list[str]:
        """Get list of tracked log file paths.
        Returns:
            List of file paths as strings
        """
        return self._data.get("tracked_logs", [])

    def set_tracked_logs(self, paths: list[str]) -> None:
        """Set list of tracked log file paths.

        Args:
            paths: List of file paths as strings
        """
        self._data["tracked_logs"] = paths
        self._save()

    def add_tracked_log(self, path: str) -> None:
        """Add a log file path to tracked logs.

        Args:
            path: File path as string
        """
        tracked = self.get_tracked_logs()
        if path not in tracked:
            tracked.append(path)
            self.set_tracked_logs(tracked)

    def remove_tracked_log(self, path: str) -> None:
        """Remove a log file path from tracked logs.

        Args:
            path: File path as string
        """
        tracked = self.get_tracked_logs()
        if path in tracked:
            tracked.remove(path)
            self.set_tracked_logs(tracked)

    def clear_tracked_logs(self) -> None:
        """Clear all tracked log file paths."""
        self.set_tracked_logs([])

    def get_open_windows(self) -> list[str]:
        """Get list of log paths that should have open windows.

        Returns:
            List of file paths as strings
        """
        return self._data.get("open_windows", [])

    def set_open_windows(self, paths: list[str]) -> None:
        """Set list of log paths that have open windows.

        Args:
            paths: List of file paths as strings
        """
        self._data["open_windows"] = paths
        self._save()

    def get_window_position(self, path: str) -> dict[str, int] | None:
        """Get window position and size for a log file.

        Args:
            path: File path as string

        Returns:
            Dict with x, y, width, height or None
        """
        return self._data.get("window_positions", {}).get(path)

    def set_window_position(self, path: str, x: int, y: int, width: int, height: int) -> None:
        """Set window position and size for a log file.

        Args:
            path: File path as string
            x: X position
            y: Y position
            width: Window width
            height: Window height
        """
        if "window_positions" not in self._data:
            self._data["window_positions"] = {}
        self._data["window_positions"][path] = {
            "x": x,
            "y": y,
            "width": width,
            "height": height
        }
        self._save()

    def get_default_window_size(self) -> tuple[int, int]:
        """Get default window size.

        Returns:
            Tuple of (width, height)
        """
        width = self._data.get("default_window_width", 1000)
        height = self._data.get("default_window_height", 800)
        return (width, height)

    def set_default_window_size(self, width: int, height: int) -> None:
        """Set default window size.

        Args:
            width: Window width
            height: Window height
        """
        self._data["default_window_width"] = width
        self._data["default_window_height"] = height
        self._save()
        logger.info(f"Set default window size to {width}x{height}")

    def get_groups(self) -> list[str]:
        """Get list of group names.

        Returns:
            List of group names
        """
        return self._data.get("groups", [])

    def set_groups(self, groups: list[str]) -> None:
        """Set list of group names.

        Args:
            groups: List of group names
        """
        self._data["groups"] = groups
        self._save()

    def get_log_groups(self) -> dict[str, str]:
        """Get log-to-group assignments.

        Returns:
            Dictionary mapping path_key to group_name
        """
        return self._data.get("log_groups", {})

    def set_log_groups(self, log_groups: dict[str, str]) -> None:
        """Set log-to-group assignments.

        Args:
            log_groups: Dictionary mapping path_key to group_name
        """
        self._data["log_groups"] = log_groups
        self._save()

    # Session Management

    def get_current_session(self) -> str:
        """Get the name of the current session.

        Returns:
            Current session name
        """
        return self._current_session

    def get_available_sessions(self) -> list[str]:
        """Get list of available session names.

        Returns:
            List of session names
        """
        if not self.sessions_dir.exists():
            return ["default"]

        sessions = []
        for file in self.sessions_dir.glob("*.json"):
            sessions.append(file.stem)

        return sorted(sessions) if sessions else ["default"]

    def switch_session(self, session_name: str) -> None:
        """Switch to a different session.

        Args:
            session_name: Name of the session to switch to
        """
        logger.info(f"Switching from session '{self._current_session}' to '{session_name}'")
        self._current_session = session_name
        self._save_last_session()
        self._load()

    def save_session_as(self, session_name: str) -> None:
        """Save current settings as a new session.

        Args:
            session_name: Name for the new session
        """
        old_session = self._current_session
        self._current_session = session_name
        self._save()
        logger.info(f"Saved session as '{session_name}'")
        self._current_session = old_session  # Restore current session

    def delete_session(self, session_name: str) -> bool:
        """Delete a session.

        Args:
            session_name: Name of the session to delete

        Returns:
            True if deleted, False if it was the current session or doesn't exist
        """
        if session_name == self._current_session:
            logger.warning(f"Cannot delete current session '{session_name}'")
            return False

        session_file = self.sessions_dir / f"{session_name}.json"
        if session_file.exists():
            session_file.unlink()
            logger.info(f"Deleted session '{session_name}'")
            return True

        return False

    def get_main_window_position(self) -> dict | None:
        """Get main window position and size.

        Returns:
            Dictionary with x, y, width, height or None
        """
        return self._data.get("main_window_position")

    def set_main_window_position(self, x: int, y: int, width: int, height: int) -> None:
        """Set main window position and size.

        Args:
            x: X coordinate
            y: Y coordinate
            width: Window width
            height: Window height
        """
        self._data["main_window_position"] = {
            "x": x,
            "y": y,
            "width": width,
            "height": height
        }
        self._save()

    def get_font_sizes(self) -> dict:
        """Get font size settings.

        Returns:
            Dictionary with font sizes for different elements
        """
        return self._data.get("font_sizes", {
            "log_content": 9,
            "ui_elements": 10,
            "status_bar": 9
        })

    def set_font_size(self, element: str, size: int) -> None:
        """Set font size for a specific element.

        Args:
            element: Element name (log_content, ui_elements, status_bar)
            size: Font size in points
        """
        if "font_sizes" not in self._data:
            self._data["font_sizes"] = {}
        self._data["font_sizes"][element] = size
        self._save()

    def get_theme_colors(self) -> dict:
        """Get theme color settings.

        Returns:
            Dictionary with color settings
        """
        return self._data.get("theme", {
            "error_color": "#FF4444",
            "warning_color": "#FFA500",
            "verbose_color": "#888888",
            "default_color": "#CCCCCC"
        })

    def set_theme_color(self, color_type: str, color: str) -> None:
        """Set a theme color.

        Args:
            color_type: Type of color (error_color, warning_color, etc.)
            color: Hex color string
        """
        if "theme" not in self._data:
            self._data["theme"] = {}
        self._data["theme"][color_type] = color
        self._save()

    # MCP Server Settings

    def get_mcp_server_settings(self) -> dict[str, Any]:
        """Get MCP server settings.

        Returns:
            Dictionary with MCP server configuration
        """
        return self._data.get("mcp_server", {
            "enabled": False,
            "binding_address": "127.0.0.1",
            "port": 3000
        })

    def set_mcp_server_enabled(self, enabled: bool) -> None:
        """Enable or disable the MCP server.

        Args:
            enabled: Whether MCP server should be enabled
        """
        if "mcp_server" not in self._data:
            self._data["mcp_server"] = {}
        self._data["mcp_server"]["enabled"] = enabled
        self._save()

    def set_mcp_server_binding_address(self, address: str) -> None:
        """Set MCP server binding address.

        Args:
            address: IP address to bind to (e.g., "127.0.0.1")
        """
        if "mcp_server" not in self._data:
            self._data["mcp_server"] = {}
        self._data["mcp_server"]["binding_address"] = address
        self._save()

    def set_mcp_server_port(self, port: int) -> None:
        """Set MCP server port.

        Args:
            port: Port number to bind to
        """
        if "mcp_server" not in self._data:
            self._data["mcp_server"] = {}
        self._data["mcp_server"]["port"] = port
        self._save()

    # Log Metadata Management

    def get_log_metadata(self, path_key: str) -> dict[str, str] | None:
        """Get metadata for a log source.

        Args:
            path_key: Unique identifier for the log source

        Returns:
            Dictionary with id and description, or None if not set
        """
        return self._data.get("log_metadata", {}).get(path_key)

    def set_log_metadata(self, path_key: str, log_id: str, description: str) -> None:
        """Set metadata for a log source.

        Args:
            path_key: Unique identifier for the log source
            log_id: Stable ID for the log source
            description: Human-readable description
        """
        if "log_metadata" not in self._data:
            self._data["log_metadata"] = {}
        self._data["log_metadata"][path_key] = {
            "id": log_id,
            "description": description
        }
        self._save()

    def remove_log_metadata(self, path_key: str) -> None:
        """Remove metadata for a log source.

        Args:
            path_key: Unique identifier for the log source
        """
        if "log_metadata" in self._data and path_key in self._data["log_metadata"]:
            del self._data["log_metadata"][path_key]
            self._save()

    def get_all_log_metadata(self) -> dict[str, dict[str, str]]:
        """Get all log metadata.

        Returns:
            Dictionary mapping path_key to metadata dict
        """
        return self._data.get("log_metadata", {})
