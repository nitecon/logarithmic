"""File watcher for monitoring log files."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Callable
from typing import TextIO

from PySide6.QtCore import QThread
from PySide6.QtCore import Signal
from watchdog.events import FileSystemEvent
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer as WatchdogObserver
from watchdog.observers.api import BaseObserver

from logarithmic.exceptions import FileAccessError
from logarithmic.exceptions import InvalidPathError


@dataclass
class FileState:
    """Tracks file metadata for change detection.

    Attributes:
        mtime: Last modification time (seconds since epoch)
        size: File size in bytes
        inode: File inode number (for detecting file replacement)
    """

    mtime: float
    size: int
    inode: int

    @classmethod
    def from_path(cls, path: Path) -> "FileState | None":
        """Create FileState from a file path.

        Args:
            path: Path to the file

        Returns:
            FileState if file exists and is accessible, None otherwise
        """
        try:
            stat = path.stat()
            return cls(
                mtime=stat.st_mtime,
                size=stat.st_size,
                inode=stat.st_ino,
            )
        except (FileNotFoundError, PermissionError, OSError):
            return None


if TYPE_CHECKING:
    from logarithmic.log_manager import LogManager

logger = logging.getLogger(__name__)


class FileWatcherThread(QThread):
    """Thread that watches and tails a log file.

    This thread manages the three states of file watching:
    1. Non-existent: Watch parent directory for file creation
    2. Exists: Tail the file and watch for deletion/move
    3. Deleted/Moved: Close handles and return to state 1

    Signals:
        new_lines: Emitted when new lines are read from the file
        file_created: Emitted when a watched file is created
        file_deleted: Emitted when a watched file is deleted/moved
        error_occurred: Emitted when an error occurs
    """

    new_lines = Signal(str)
    file_created = Signal()
    file_deleted = Signal()
    error_occurred = Signal(str)

    def __init__(
        self,
        file_path: Path,
        log_manager: "LogManager",
        path_key: str,
        tail_only: bool = False,
        tail_lines: int = 200,
    ) -> None:
        """Initialize the watcher thread.

        Args:
            file_path: Path to the log file to watch
            log_manager: Central log manager for publishing events
            path_key: String key used to register this log with the manager
            tail_only: If True, only read last N lines instead of entire file
            tail_lines: Number of lines to read in tail-only mode
        """
        super().__init__()
        self.file_path = file_path.resolve()
        self._path_key = path_key  # Use this for all log manager calls
        self._log_manager = log_manager
        self._running = False
        self._paused = False
        self._buffer: list[str] = []
        self._file_handle: TextIO | None = None
        self._observer: BaseObserver | None = None
        self._tail_only = tail_only
        self._tail_lines = tail_lines
        self._last_file_state: FileState | None = None
        self._poll_counter = 0
        self._poll_interval = 10  # Check file state every 10 iterations (1 second)

    def run(self) -> None:
        """Main thread execution loop."""
        self._running = True
        logger.info(f"Starting watcher thread for: {self.file_path}")

        try:
            if self.file_path.exists():
                logger.info(f"File exists, starting tail: {self.file_path}")
                self._start_tailing()
            else:
                logger.info(
                    f"File does not exist, watching for creation: {self.file_path}"
                )
                self._watch_for_creation()

            # Keep thread alive and periodically validate file state
            while self._running:
                self.msleep(100)
                self._poll_counter += 1

                # Periodic file state validation (every ~1 second)
                if self._poll_counter >= self._poll_interval:
                    self._poll_counter = 0
                    self._validate_file_state()

        except Exception as e:
            logger.error(f"Error in watcher thread: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
        finally:
            logger.info(f"Cleaning up watcher thread: {self.file_path}")
            self._cleanup()

    def stop(self) -> None:
        """Stop the watcher thread."""
        self._running = False

    def pause(self) -> None:
        """Pause line emission (but continue buffering)."""
        self._paused = True

    def resume(self) -> None:
        """Resume line emission and flush buffer."""
        self._paused = False
        if self._buffer:
            buffered_content = "".join(self._buffer)
            self._buffer.clear()
            self.new_lines.emit(buffered_content)

    def _watch_for_creation(self) -> None:
        """Watch parent directory for file creation (State 1)."""
        parent_dir = self.file_path.parent

        if not parent_dir.exists():
            raise InvalidPathError(f"Parent directory does not exist: {parent_dir}")

        event_handler = _FileCreationHandler(self.file_path, self._on_file_created)
        self._observer = WatchdogObserver()
        self._observer.schedule(event_handler, str(parent_dir), recursive=False)
        self._observer.start()

    def _on_file_created(self) -> None:
        """Callback when watched file is created."""
        if self._observer:
            try:
                if self._observer.is_alive():
                    self._observer.stop()
            except Exception as e:
                logger.debug(f"Error stopping observer during file creation: {e}")
            self._observer = None

        # Publish to log manager
        self._log_manager.publish_file_created(self._path_key)
        self._log_manager.publish_stream_resumed(self._path_key)
        self.file_created.emit()
        self._start_tailing()

    def _start_tailing(self) -> None:
        """Start tailing the file (State 2)."""
        if not self.file_path.exists():
            return

        # Check read permissions
        if not os.access(self.file_path, os.R_OK):
            raise FileAccessError(f"Cannot read file: {self.file_path}")

        # Read file content based on mode
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                if self._tail_only:
                    # Tail-only mode: read last N lines
                    lines = f.readlines()
                    if len(lines) > self._tail_lines:
                        lines = lines[-self._tail_lines :]
                    initial_content = "".join(lines)
                    logger.info(
                        f"Tail-only mode: read last {len(lines)} lines from {self.file_path}"
                    )
                else:
                    # Full log mode: read entire file
                    initial_content = f.read()
                    logger.info(f"Full log mode: read entire file {self.file_path}")

                if initial_content:
                    self._log_manager.publish_content(self._path_key, initial_content)
                    if not self._paused:
                        self.new_lines.emit(initial_content)
        except Exception as e:
            raise FileAccessError(f"Failed to read file: {e}") from e

        # Start watching for changes
        event_handler = _FileTailHandler(
            self.file_path, self._on_file_modified, self._on_file_deleted
        )
        self._observer = WatchdogObserver()
        self._observer.schedule(
            event_handler, str(self.file_path.parent), recursive=False
        )
        self._observer.start()

        # Open file for tailing
        try:
            self._file_handle = open(
                self.file_path, "r", encoding="utf-8", errors="replace"
            )
            self._file_handle.seek(0, 2)  # Seek to end
        except Exception as e:
            raise FileAccessError(f"Failed to open file for tailing: {e}") from e

        # Capture initial file state for change detection
        self._last_file_state = FileState.from_path(self.file_path)
        if self._last_file_state:
            logger.debug(
                f"Captured file state: mtime={self._last_file_state.mtime}, "
                f"size={self._last_file_state.size}, inode={self._last_file_state.inode}"
            )

    def _validate_file_state(self) -> None:
        """Validate file state and handle changes not caught by watchdog.

        This method provides a fallback mechanism for detecting file changes
        that watchdog may miss (especially on Windows). It checks:
        - File deletion (file no longer exists)
        - File replacement (inode changed - file was moved/deleted and recreated)
        - File truncation (size decreased)
        - File modification (mtime changed but no watchdog event received)
        """
        if not self._file_handle:
            return

        current_state = FileState.from_path(self.file_path)

        # File was deleted
        if current_state is None:
            logger.info(f"File state validation: file deleted - {self.file_path}")
            self._on_file_deleted()
            return

        # No previous state to compare (shouldn't happen, but handle gracefully)
        if self._last_file_state is None:
            self._last_file_state = current_state
            return

        # Check for file replacement (inode changed)
        if current_state.inode != self._last_file_state.inode:
            logger.info(
                f"File state validation: inode changed - {self.file_path} "
                f"(old={self._last_file_state.inode}, new={current_state.inode})"
            )
            self._reload_file("File replaced")
            return

        # Check for truncation (size decreased)
        if current_state.size < self._last_file_state.size:
            logger.info(
                f"File state validation: truncation detected - {self.file_path} "
                f"(old_size={self._last_file_state.size}, new_size={current_state.size})"
            )
            self._handle_truncation()
            self._last_file_state = current_state
            return

        # Check for modification (mtime changed and we might have missed content)
        if current_state.mtime > self._last_file_state.mtime:
            # File was modified - read any new content
            if current_state.size > self._last_file_state.size:
                logger.debug(
                    f"File state validation: new content detected - {self.file_path}"
                )
                self._on_file_modified()
            self._last_file_state = current_state

    def _handle_truncation(self) -> None:
        """Handle file truncation by resetting to beginning."""
        if not self._file_handle:
            return

        self._log_manager.publish_stream_interrupted(
            self._path_key, "File truncated/rotated"
        )
        self._file_handle.seek(0)
        self._log_manager.publish_stream_resumed(self._path_key)

        # Emit visual separator for file reload
        separator = "\n============= File Reloaded =============\n"
        self._log_manager.publish_content(self._path_key, separator)
        if not self._paused:
            self.new_lines.emit(separator)

        # Read content from beginning
        try:
            content = self._file_handle.read()
            if content:
                self._log_manager.publish_content(self._path_key, content)
                if not self._paused:
                    self.new_lines.emit(content)
                else:
                    self._buffer.append(content)
        except Exception as e:
            logger.error(f"Error reading after truncation: {e}")

    def _reload_file(self, reason: str) -> None:
        """Reload the file from scratch (for replacement scenarios).

        Args:
            reason: Reason for reloading (for logging/events)
        """
        logger.info(f"Reloading file: {self.file_path} - {reason}")

        # Publish interruption
        self._log_manager.publish_stream_interrupted(self._path_key, reason)

        # Close current handle
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception as e:
                logger.debug(f"Error closing file handle during reload: {e}")
            self._file_handle = None

        # Clear the log display for fresh content
        self._log_manager.clear_buffer(self._path_key)

        # Re-read the file from beginning
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                if self._tail_only:
                    lines = f.readlines()
                    if len(lines) > self._tail_lines:
                        lines = lines[-self._tail_lines :]
                    content = "".join(lines)
                else:
                    content = f.read()

                if content:
                    self._log_manager.publish_content(self._path_key, content)
                    if not self._paused:
                        self.new_lines.emit(content)
                    else:
                        self._buffer.append(content)
        except Exception as e:
            logger.error(f"Error reading file during reload: {e}")
            self.error_occurred.emit(f"Error reloading file: {e}")
            return

        # Reopen for tailing
        try:
            self._file_handle = open(
                self.file_path, "r", encoding="utf-8", errors="replace"
            )
            self._file_handle.seek(0, 2)  # Seek to end
        except Exception as e:
            logger.error(f"Error reopening file for tailing: {e}")
            self.error_occurred.emit(f"Error reopening file: {e}")
            return

        # Emit visual separator for file reload
        separator = "\n============= File Reloaded =============\n"
        self._log_manager.publish_content(self._path_key, separator)
        if not self._paused:
            self.new_lines.emit(separator)

        # Update file state
        self._last_file_state = FileState.from_path(self.file_path)
        self._log_manager.publish_stream_resumed(self._path_key)

    def _on_file_modified(self) -> None:
        """Callback when file is modified."""
        if not self._file_handle or not self._running:
            return

        try:
            # Check for file truncation (log rotation)
            current_pos = self._file_handle.tell()
            try:
                file_size = self.file_path.stat().st_size
                if file_size < current_pos:
                    # File was truncated - reset to beginning
                    logger.info(
                        f"File truncated detected: {self.file_path} "
                        f"(pos={current_pos}, size={file_size})"
                    )
                    self._log_manager.publish_stream_interrupted(
                        self._path_key, "File truncated/rotated"
                    )
                    self._file_handle.seek(0)
                    self._log_manager.publish_stream_resumed(self._path_key)
            except (FileNotFoundError, PermissionError, OSError) as e:
                logger.warning(f"Cannot stat file during modification check: {e}")

            lines = self._file_handle.readlines()
            if lines:
                content = "".join(lines)
                self._log_manager.publish_content(self._path_key, content)

                if self._paused:
                    self._buffer.extend(lines)
                else:
                    self.new_lines.emit(content)
        except Exception as e:
            self.error_occurred.emit(f"Error reading file: {e}")

    def _on_file_deleted(self) -> None:
        """Callback when file is deleted/moved (State 3)."""
        self._log_manager.publish_file_deleted(self._path_key)
        self._log_manager.publish_stream_interrupted(self._path_key, "File deleted")
        self.file_deleted.emit()
        self._last_file_state = None  # Reset file state
        self._cleanup()
        # Return to state 1
        if self._running:
            self._watch_for_creation()

    def _cleanup(self) -> None:
        """Clean up resources."""
        logger.debug(f"Cleanup called for: {self.file_path}")

        if self._file_handle:
            try:
                logger.debug("Closing file handle")
                self._file_handle.close()
            except Exception as e:
                logger.error(f"Error closing file handle: {e}")
            self._file_handle = None

        if self._observer:
            try:
                logger.debug(f"Observer exists, is_alive: {self._observer.is_alive()}")
                if self._observer.is_alive():
                    logger.debug("Stopping observer")
                    self._observer.stop()
                    logger.debug("Joining observer")
                    self._observer.join(timeout=1.0)
                    logger.debug("Observer stopped and joined")
            except Exception as e:
                logger.error(f"Error stopping observer: {e}", exc_info=True)
            self._observer = None


class _FileCreationHandler(FileSystemEventHandler):
    """Handler for watching file creation events."""

    def __init__(self, target_path: Path, callback: Callable[[], None]) -> None:
        """Initialize the handler.

        Args:
            target_path: Path to watch for
            callback: Function to call when file is created
        """
        super().__init__()
        self.target_path = target_path
        self.callback = callback

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        src_path = (
            event.src_path if isinstance(event.src_path, str) else str(event.src_path)
        )
        if not event.is_directory and Path(src_path) == self.target_path:
            self.callback()


class _FileTailHandler(FileSystemEventHandler):
    """Handler for watching file modification and deletion events."""

    def __init__(
        self,
        target_path: Path,
        on_modified: Callable[[], None],
        on_deleted: Callable[[], None],
    ) -> None:
        """Initialize the handler.

        Args:
            target_path: Path to watch
            on_modified: Callback for modification events
            on_deleted: Callback for deletion events
        """
        super().__init__()
        self.target_path = target_path
        self.on_modified_callback = on_modified
        self.on_deleted_callback = on_deleted

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        src_path = (
            event.src_path if isinstance(event.src_path, str) else str(event.src_path)
        )
        if not event.is_directory and Path(src_path) == self.target_path:
            self.on_modified_callback()

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion events."""
        src_path = (
            event.src_path if isinstance(event.src_path, str) else str(event.src_path)
        )
        if not event.is_directory and Path(src_path) == self.target_path:
            self.on_deleted_callback()

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move events (treat as deletion)."""
        src_path = (
            event.src_path if isinstance(event.src_path, str) else str(event.src_path)
        )
        if not event.is_directory and Path(src_path) == self.target_path:
            self.on_deleted_callback()
