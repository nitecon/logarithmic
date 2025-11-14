"""Log Manager - Central hub for log content and event publishing."""

import logging
import threading
from collections import deque
from typing import Protocol

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal

logger = logging.getLogger(__name__)


class LogSubscriber(Protocol):
    """Protocol for log event subscribers."""

    def on_log_content(self, path: str, content: str) -> None:
        """Called when new log content is available.

        Args:
            path: Log file path
            content: New content to append
        """
        ...

    def on_log_cleared(self, path: str) -> None:
        """Called when log buffer is cleared.

        Args:
            path: Log file path
        """
        ...

    def on_stream_interrupted(self, path: str, reason: str) -> None:
        """Called when the log stream is interrupted (file deleted/truncated).

        Args:
            path: Log file path
            reason: Reason for interruption (e.g., "File deleted", "File truncated")
        """
        ...

    def on_stream_resumed(self, path: str) -> None:
        """Called when the log stream resumes (file recreated).

        Args:
            path: Log file path
        """
        ...


class LogBuffer:
    """Maintains a circular buffer of log lines for a single file.

    This buffer stores the most recent N lines and provides the full
    content on demand for new subscribers.
    """

    def __init__(self, max_lines: int = 10000) -> None:
        """Initialize the log buffer.

        Args:
            max_lines: Maximum number of lines to retain
        """
        self._max_lines = max_lines
        self._lines: deque[str] = deque(maxlen=max_lines)
        self._total_lines_received = 0

    def append(self, content: str) -> None:
        """Append new content to the buffer.

        Args:
            content: New content (may contain multiple lines)
        """
        lines = content.splitlines(keepends=True)
        self._lines.extend(lines)
        self._total_lines_received += len(lines)
        logger.debug(
            f"Buffer now has {len(self._lines)} lines (total received: {self._total_lines_received})"
        )

    def get_content(self) -> str:
        """Get the full buffered content.

        Returns:
            All buffered lines as a single string
        """
        return "".join(self._lines)

    def clear(self) -> None:
        """Clear the buffer."""
        self._lines.clear()
        logger.debug("Buffer cleared")

    def __len__(self) -> int:
        """Get the number of lines in the buffer.

        Returns:
            Number of buffered lines
        """
        return len(self._lines)


class LogManager(QObject):
    """Central manager for log content and event distribution.

    This class maintains buffers for all tracked log files and publishes
    events to registered subscribers using a publisher-subscriber pattern.

    Signals:
        log_content_available: Emitted when new content is available (path, content)
        log_cleared: Emitted when a log buffer is cleared (path)
        log_file_created: Emitted when a watched file is created (path)
        log_file_deleted: Emitted when a watched file is deleted (path)
    """

    # Qt signals for cross-thread communication
    log_content_available = Signal(str, str)  # path, content
    log_cleared = Signal(str)  # path
    log_file_created = Signal(str)  # path
    log_file_deleted = Signal(str)  # path
    stream_interrupted = Signal(str, str)  # path, reason
    stream_resumed = Signal(str)  # path

    def __init__(self) -> None:
        """Initialize the log manager."""
        super().__init__()
        self._buffers: dict[str, LogBuffer] = {}
        self._subscribers: dict[str, list[LogSubscriber]] = {}
        self._lock = threading.RLock()  # Protect dict access

        # Connect signals to internal handlers
        self.log_content_available.connect(self._on_content_available)
        self.log_cleared.connect(self._on_cleared)
        self.stream_interrupted.connect(self._on_stream_interrupted)
        self.stream_resumed.connect(self._on_stream_resumed)

    def register_log(self, path: str, max_lines: int = 10000) -> None:
        """Register a new log file for tracking.

        Args:
            path: Log file path
            max_lines: Maximum lines to buffer
        """
        with self._lock:
            if path not in self._buffers:
                self._buffers[path] = LogBuffer(max_lines)
                self._subscribers[path] = []
                logger.info(f"Registered log: {path}")
                logger.debug(f"Buffer keys: {list(self._buffers.keys())}")

    def unregister_log(self, path: str) -> None:
        """Unregister a log file.

        Args:
            path: Log file path
        """
        if path in self._buffers:
            del self._buffers[path]
            del self._subscribers[path]
            logger.info(f"Unregistered log: {path}")

    def subscribe(self, path: str, subscriber: LogSubscriber) -> None:
        """Subscribe to log events for a specific file.

        The subscriber will immediately receive the current buffer content.

        Args:
            path: Log file path
            subscriber: Subscriber to register
        """
        if path not in self._subscribers:
            logger.warning(f"Cannot subscribe to unregistered log: {path}")
            return

        if subscriber not in self._subscribers[path]:
            self._subscribers[path].append(subscriber)
            logger.info(f"Added subscriber for: {path}")

            # Send current buffer content to new subscriber
            buffer = self._buffers.get(path)
            if buffer and len(buffer) > 0:
                content = buffer.get_content()
                subscriber.on_log_content(path, content)
                logger.debug(f"Sent {len(buffer)} buffered lines to new subscriber")

    def unsubscribe(self, path: str, subscriber: LogSubscriber) -> None:
        """Unsubscribe from log events.

        Args:
            path: Log file path
            subscriber: Subscriber to remove
        """
        if path in self._subscribers and subscriber in self._subscribers[path]:
            self._subscribers[path].remove(subscriber)
            logger.info(f"Removed subscriber for: {path}")

    def publish_content(self, path: str, content: str) -> None:
        """Publish new log content (thread-safe via signal).

        Args:
            path: Log file path
            content: New content to publish
        """
        self.log_content_available.emit(path, content)

    def publish_file_created(self, path: str) -> None:
        """Publish file creation event.

        Args:
            path: Log file path
        """
        self.log_file_created.emit(path)
        logger.info(f"Published file created event: {path}")

    def publish_file_deleted(self, path: str) -> None:
        """Publish file deletion event.

        Args:
            path: Log file path
        """
        self.log_file_deleted.emit(path)
        logger.info(f"Published file deleted event: {path}")

    def publish_stream_interrupted(self, path: str, reason: str) -> None:
        """Publish stream interruption event.

        Args:
            path: Log file path
            reason: Reason for interruption
        """
        self.stream_interrupted.emit(path, reason)
        logger.info(f"Published stream interrupted event: {path} - {reason}")

    def publish_stream_resumed(self, path: str) -> None:
        """Publish stream resumed event.

        Args:
            path: Log file path
        """
        self.stream_resumed.emit(path)
        logger.info(f"Published stream resumed event: {path}")

    def clear_buffer(self, path: str) -> None:
        """Clear the buffer for a log file.

        Args:
            path: Log file path
        """
        if path in self._buffers:
            self._buffers[path].clear()
            self.log_cleared.emit(path)

    def clear_log(self, path: str) -> None:
        """Clear the buffer for a log file (alias for clear_buffer).

        Args:
            path: Log file path
        """
        self.clear_buffer(path)

    def get_buffer_content(self, path: str) -> str:
        """Get the current buffer content for a log file.

        Args:
            path: Log file path

        Returns:
            Buffered content or empty string
        """
        buffer = self._buffers.get(path)
        return buffer.get_content() if buffer else ""

    def _on_content_available(self, path: str, content: str) -> None:
        """Internal handler for content available signal.

        Args:
            path: Log file path
            content: New content
        """
        # Add to buffer (with lock)
        with self._lock:
            buffer = self._buffers.get(path)
            if buffer is not None:
                buffer.append(content)
                logger.debug(
                    f"Added {len(content)} chars to buffer for {path}, buffer now has {len(buffer)} lines"
                )
            else:
                logger.error("No buffer found for path")
                logger.error(f"Incoming: {repr(path)}")
                if self._buffers:
                    first_key = list(self._buffers.keys())[0]
                    logger.error(f"First key: {repr(first_key)}")
                    logger.error(f"Are they equal? {path == first_key}")
                    logger.error(f"Trying direct access: {self._buffers[first_key]}")
                    logger.error(f"Trying get with incoming: {self._buffers.get(path)}")
                else:
                    logger.error("Dict is empty!")

            # Notify subscribers
            subscribers = self._subscribers.get(
                path, []
            ).copy()  # Copy to avoid modification during iteration

        logger.debug(f"Notifying {len(subscribers)} subscribers for {path}")
        for subscriber in subscribers:
            try:
                subscriber.on_log_content(path, content)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}", exc_info=True)

    def _on_cleared(self, path: str) -> None:
        """Internal handler for cleared signal.

        Args:
            path: Log file path
        """
        # Notify subscribers
        subscribers = self._subscribers.get(path, [])
        for subscriber in subscribers:
            try:
                subscriber.on_log_cleared(path)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}", exc_info=True)

    def _on_stream_interrupted(self, path: str, reason: str) -> None:
        """Internal handler for stream interrupted signal.

        Args:
            path: Log file path
            reason: Reason for interruption
        """
        with self._lock:
            subscribers = self._subscribers.get(path, []).copy()

        for subscriber in subscribers:
            try:
                subscriber.on_stream_interrupted(path, reason)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}", exc_info=True)

    def _on_stream_resumed(self, path: str) -> None:
        """Internal handler for stream resumed signal.

        Args:
            path: Log file path
        """
        with self._lock:
            subscribers = self._subscribers.get(path, []).copy()

        for subscriber in subscribers:
            try:
                subscriber.on_stream_resumed(path)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}", exc_info=True)
