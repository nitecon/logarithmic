"""MCP Bridge - Thread-safe intermediary between LogManager and MCP Server."""

import logging
import threading
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable

from logarithmic.log_manager import LogManager
from logarithmic.log_manager import LogSubscriber
from logarithmic.settings import Settings

if TYPE_CHECKING:
    from logarithmic.log_group_window import LogGroupWindow

logger = logging.getLogger(__name__)


class McpBridge(LogSubscriber):
    """Thread-safe bridge between LogManager and MCP Server.

    This class subscribes to all tracked logs and maintains a thread-safe
    cache of log content that can be accessed by the MCP server running
    on a different thread/event loop.
    """

    def __init__(self, log_manager: LogManager, settings: Settings) -> None:
        """Initialize the MCP bridge.

        Args:
            log_manager: Central log manager instance
            settings: Settings manager for metadata
        """
        self._log_manager = log_manager
        self._settings = settings
        self._lock = threading.RLock()

        # Cache of log content: path_key -> content
        self._log_cache: dict[str, str] = {}

        # Track subscriptions
        self._subscribed_paths: set[str] = set()

        # Callbacks for MCP server to be notified of updates
        self._update_callbacks: list[Callable[[str, str], None]] = []

        # Reference to group windows for combined view access
        self._group_windows_callback: (
            Callable[[], dict[str, "LogGroupWindow"]] | None
        ) = None

    def subscribe_to_log(self, path_key: str) -> None:
        """Subscribe to a log source.

        Args:
            path_key: Unique identifier for the log source
        """
        if path_key in self._subscribed_paths:
            return

        with self._lock:
            self._subscribed_paths.add(path_key)
            self._log_cache[path_key] = ""

        # Subscribe to log manager
        self._log_manager.subscribe(path_key, self)
        logger.info(f"MCP Bridge subscribed to: {path_key}")

    def unsubscribe_from_log(self, path_key: str) -> None:
        """Unsubscribe from a log source.

        Args:
            path_key: Unique identifier for the log source
        """
        if path_key not in self._subscribed_paths:
            return

        with self._lock:
            self._subscribed_paths.discard(path_key)
            if path_key in self._log_cache:
                del self._log_cache[path_key]

        self._log_manager.unsubscribe(path_key, self)
        logger.info(f"MCP Bridge unsubscribed from: {path_key}")

    def subscribe_to_all_tracked_logs(self) -> None:
        """Subscribe to all currently tracked logs."""
        tracked_logs = self._settings.get_tracked_logs()
        for path_key in tracked_logs:
            self.subscribe_to_log(path_key)

    def get_log_content(self, path_key: str) -> str:
        """Get cached log content (thread-safe).

        Args:
            path_key: Unique identifier for the log source

        Returns:
            Cached log content or empty string
        """
        with self._lock:
            return self._log_cache.get(path_key, "")

    def get_all_logs(self) -> dict[str, dict[str, Any]]:
        """Get all tracked logs with metadata.

        Returns:
            Dictionary mapping path_key to log info (id, description, content)
        """
        with self._lock:
            result = {}
            for path_key in self._subscribed_paths:
                metadata = self._settings.get_log_metadata(path_key)
                result[path_key] = {
                    "id": metadata.get("id", path_key) if metadata else path_key,
                    "description": metadata.get("description", path_key)
                    if metadata
                    else path_key,
                    "content": self._log_cache.get(path_key, ""),
                    "path": path_key,
                }
            return result

    def get_log_info(self, log_id: str) -> dict[str, Any] | None:
        """Get information about a specific log by ID.

        Args:
            log_id: Log ID (from metadata) or path_key

        Returns:
            Log information dictionary or None if not found
        """
        with self._lock:
            # First try to find by ID in metadata
            all_metadata = self._settings.get_all_log_metadata()
            for path_key, metadata in all_metadata.items():
                if metadata.get("id") == log_id and path_key in self._subscribed_paths:
                    return {
                        "id": metadata["id"],
                        "description": metadata.get("description", path_key),
                        "content": self._log_cache.get(path_key, ""),
                        "path": path_key,
                    }

            # Fallback: try as path_key
            if log_id in self._subscribed_paths:
                log_metadata: dict[str, str] | None = self._settings.get_log_metadata(
                    log_id
                )
                return {
                    "id": log_metadata.get("id", log_id) if log_metadata else log_id,
                    "description": log_metadata.get("description", log_id)
                    if log_metadata
                    else log_id,
                    "content": self._log_cache.get(log_id, ""),
                    "path": log_id,
                }

            return None

    def register_update_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register a callback to be notified of log updates.

        Args:
            callback: Callable that takes (path_key, content) as arguments
        """
        with self._lock:
            if callback not in self._update_callbacks:
                self._update_callbacks.append(callback)

    def unregister_update_callback(self, callback: Callable[[str, str], None]) -> None:
        """Unregister an update callback.

        Args:
            callback: Callback to remove
        """
        with self._lock:
            if callback in self._update_callbacks:
                self._update_callbacks.remove(callback)

    # LogSubscriber Protocol Implementation

    def on_log_content(self, path: str, content: str) -> None:
        """Called when new log content is available.

        Args:
            path: Log file path
            content: New content to append
        """
        with self._lock:
            if path in self._log_cache:
                self._log_cache[path] += content
            else:
                self._log_cache[path] = content

            # Notify callbacks
            callbacks = self._update_callbacks.copy()

        for callback in callbacks:
            try:
                callback(path, content)
            except Exception as e:
                logger.error(f"Error in update callback: {e}", exc_info=True)

    def on_log_cleared(self, path: str) -> None:
        """Called when log buffer is cleared.

        Args:
            path: Log file path
        """
        with self._lock:
            if path in self._log_cache:
                self._log_cache[path] = ""
        logger.info(f"MCP Bridge cleared cache for: {path}")

    def on_stream_interrupted(self, path: str, reason: str) -> None:
        """Called when the log stream is interrupted.

        Args:
            path: Log file path
            reason: Reason for interruption
        """
        logger.info(f"MCP Bridge: Stream interrupted for {path} - {reason}")

    def on_stream_resumed(self, path: str) -> None:
        """Called when the log stream resumes.

        Args:
            path: Log file path
        """
        logger.info(f"MCP Bridge: Stream resumed for {path}")

    def set_group_windows_callback(
        self, callback: Callable[[], dict[str, "LogGroupWindow"]]
    ) -> None:
        """Set callback to get group windows for combined view access.

        Args:
            callback: Function that returns dict of group_name -> LogGroupWindow
        """
        self._group_windows_callback = callback

    def get_last_n_lines(self, log_id: str, num_lines: int) -> str | None:
        """Get the last N lines from a log.

        Args:
            log_id: Log ID or path_key
            num_lines: Number of lines to retrieve

        Returns:
            Last N lines as string, or None if log not found
        """
        log_info = self.get_log_info(log_id)
        if log_info is None:
            return None

        content = log_info["content"]
        lines = content.split("\n")
        last_lines = lines[-num_lines:] if len(lines) > num_lines else lines
        return "\n".join(last_lines)

    def get_groups(self) -> dict[str, dict[str, Any]]:
        """Get all log groups with their metadata.

        Returns:
            Dictionary mapping group_name to group info
        """
        with self._lock:
            result: dict[str, dict[str, Any]] = {}
            log_groups = self._settings.get_log_groups()

            # Group logs by their group name
            groups: dict[str, list[str]] = {}
            for path_key, group_name in log_groups.items():
                if group_name not in groups:
                    groups[group_name] = []
                groups[group_name].append(path_key)

            for group_name, paths in groups.items():
                result[group_name] = {
                    "name": group_name,
                    "log_count": len(paths),
                    "logs": paths,
                    "has_combined_view": self._has_combined_view(group_name),
                }

            return result

    def _has_combined_view(self, group_name: str) -> bool:
        """Check if a group has an active combined view with content.

        Args:
            group_name: Name of the group

        Returns:
            True if combined view exists and has content
        """
        if not self._group_windows_callback:
            return False

        try:
            group_windows = self._group_windows_callback()
            if group_name in group_windows:
                window = group_windows[group_name]
                if window._mode == "combined" and window._combined_controller:
                    content = window._combined_controller.get_text()
                    return bool(content and content.strip())
        except Exception as e:
            logger.warning(f"Error checking combined view for {group_name}: {e}")

        return False

    def get_combined_view_content(self, group_name: str) -> str | None:
        """Get the combined view content for a group.

        Args:
            group_name: Name of the group

        Returns:
            Combined view content or None if not available
        """
        if not self._group_windows_callback:
            return None

        try:
            group_windows = self._group_windows_callback()
            if group_name in group_windows:
                window = group_windows[group_name]
                if window._mode == "combined" and window._combined_controller:
                    return window._combined_controller.get_text()
        except Exception as e:
            logger.warning(f"Error getting combined view for {group_name}: {e}")

        return None

    def get_combined_view_last_n_lines(
        self, group_name: str, num_lines: int
    ) -> str | None:
        """Get the last N lines from a group's combined view.

        Args:
            group_name: Name of the group
            num_lines: Number of lines to retrieve

        Returns:
            Last N lines or None if not available
        """
        content = self.get_combined_view_content(group_name)
        if content is None:
            return None

        lines = content.split("\n")
        last_lines = lines[-num_lines:] if len(lines) > num_lines else lines
        return "\n".join(last_lines)

    def get_group_content(
        self, group_name: str, num_lines: int | None = None
    ) -> dict[str, Any] | None:
        """Get content for a group, prioritizing combined view if available.

        Args:
            group_name: Name of the group
            num_lines: Optional number of lines to limit (None for all)

        Returns:
            Dictionary with content info or None if group not found
        """
        groups = self.get_groups()
        if group_name not in groups:
            return None

        group_info = groups[group_name]

        # Check if combined view has content - prioritize it
        if group_info["has_combined_view"]:
            if num_lines:
                content = self.get_combined_view_last_n_lines(group_name, num_lines)
            else:
                content = self.get_combined_view_content(group_name)

            if content and content.strip():
                return {
                    "group_name": group_name,
                    "source": "combined_view",
                    "content": content,
                    "log_count": group_info["log_count"],
                }

        # Fall back to concatenating individual log content
        combined_content = []
        for path_key in group_info["logs"]:
            if num_lines:
                log_content = self.get_last_n_lines(path_key, num_lines)
            else:
                log_info = self.get_log_info(path_key)
                log_content = log_info["content"] if log_info else None

            if log_content:
                metadata = self._settings.get_log_metadata(path_key)
                desc = metadata.get("description", path_key) if metadata else path_key
                combined_content.append(f"=== {desc} ===\n{log_content}")

        return {
            "group_name": group_name,
            "source": "individual_logs",
            "content": "\n\n".join(combined_content),
            "log_count": group_info["log_count"],
        }
