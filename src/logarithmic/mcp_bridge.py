"""MCP Bridge - Thread-safe intermediary between LogManager and MCP Server."""

import logging
import threading
from typing import Any
from typing import Callable

from logarithmic.log_manager import LogManager
from logarithmic.log_manager import LogSubscriber
from logarithmic.settings import Settings

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
                log_metadata: dict[str, str] | None = self._settings.get_log_metadata(log_id)
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
