"""Wildcard File Watcher - handles glob patterns and automatic file switching."""

import fnmatch
import glob
import logging
import os
import time
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

from logarithmic.exceptions import InvalidPathError

if TYPE_CHECKING:
    from logarithmic.log_manager import LogManager

logger = logging.getLogger(__name__)


# Global registry to share observers across multiple watchers for the same directory
_DIRECTORY_OBSERVERS: dict[str, tuple[WatchdogObserver, int]] = {}
_OBSERVER_LOCK = __import__("threading").Lock()


class _DirectoryWatchHandler(FileSystemEventHandler):
    """Handler for watching directory for new matching files."""

    def __init__(self, pattern: str, callback: Callable[[str], None]) -> None:
        """Initialize handler.

        Args:
            pattern: Glob pattern to match
            callback: Function to call when matching file is created
        """
        super().__init__()
        self._pattern = pattern
        self._callback = callback
        self._seen_files: set[str] = set()  # Track files we've already notified about
        self._last_event_time: dict[str, float] = {}  # Debounce duplicate events

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation event.

        Args:
            event: File system event
        """
        if not event.is_directory:
            # Check if new file matches pattern using fnmatch
            src_path = (
                event.src_path
                if isinstance(event.src_path, str)
                else str(event.src_path)
            )
            filename = Path(src_path).name
            pattern_name = Path(self._pattern).name

            if fnmatch.fnmatch(filename, pattern_name):
                # Debounce: ignore if we've seen this file very recently (within 1 second)
                current_time = time.time()
                last_time = self._last_event_time.get(src_path, 0)

                if current_time - last_time < 1.0:
                    logger.debug(f"Ignoring duplicate creation event for: {src_path}")
                    return

                self._last_event_time[src_path] = current_time

                # Only notify if this is truly a new file we haven't seen
                if src_path not in self._seen_files:
                    logger.info(f"New matching file detected: {src_path}")
                    self._seen_files.add(src_path)
                    self._callback(src_path)
                else:
                    logger.debug(f"File already tracked, ignoring: {src_path}")


class WildcardFileWatcher(QThread):
    """Watches for files matching a glob pattern and switches to latest.

    This watcher monitors a directory for files matching a wildcard pattern
    (e.g., "Cook-*.txt") and automatically switches to the newest matching file.
    When a new file appears, it triggers a stream interruption/resumption cycle.

    Signals:
        new_lines: Emitted when new lines are read from the current file
        file_switched: Emitted when switching to a new file (old_path, new_path)
        error_occurred: Emitted when an error occurs
    """

    new_lines = Signal(str)
    file_switched = Signal(str, str)  # old_path, new_path
    error_occurred = Signal(str)

    def __init__(
        self,
        pattern: str,
        log_manager: "LogManager",
        path_key: str,
        tail_only: bool = False,
        tail_lines: int = 200,
    ) -> None:
        """Initialize the wildcard watcher.

        Args:
            pattern: Glob pattern (e.g., "C:/logs/Cook-*.txt")
            log_manager: Central log manager for publishing events
            path_key: String key used to register this log with the manager
            tail_only: If True, only read last N lines instead of entire file
            tail_lines: Number of lines to read in tail-only mode
        """
        super().__init__()
        self._pattern = pattern
        self._path_key = path_key
        self._log_manager = log_manager
        self._running = False
        self._paused = False
        self._current_file: Path | None = None
        self._observer: BaseObserver | None = None
        self._file_handle: TextIO | None = None
        self._tail_only = tail_only
        self._tail_lines = tail_lines
        self._dir_handler: _DirectoryWatchHandler | None = (
            None  # Track handler for seen files
        )

        # Validate pattern
        pattern_path = Path(pattern)
        if not pattern_path.parent.exists():
            raise InvalidPathError(
                f"Parent directory does not exist: {pattern_path.parent}"
            )

        # Check if pattern contains wildcards
        if "*" not in pattern and "?" not in pattern:
            raise InvalidPathError(f"Pattern must contain wildcards: {pattern}")

    def run(self) -> None:
        """Main thread execution loop."""
        self._running = True
        logger.info(f"Starting wildcard watcher for pattern: {self._pattern}")

        try:
            # Find initial file
            latest_file = self._find_latest_matching_file()
            if latest_file:
                logger.info(f"Found initial file: {latest_file}")
                self._switch_to_file(latest_file, is_initial=True)
            else:
                logger.info(f"No matching files found for pattern: {self._pattern}")

            # Watch directory for new files
            self._watch_directory()

            # Keep thread alive
            while self._running:
                self.msleep(100)

                # Check if current file still exists
                if self._current_file and not self._current_file.exists():
                    logger.warning(f"Current file deleted: {self._current_file}")
                    self._log_manager.publish_stream_interrupted(
                        self._path_key, f"File deleted: {self._current_file.name}"
                    )
                    self._cleanup_current_file()

                    # Look for another matching file
                    latest_file = self._find_latest_matching_file()
                    if latest_file:
                        self._switch_to_file(latest_file, is_initial=False)

                # Read new content if file is open
                if self._file_handle and not self._paused:
                    self._read_new_content()

        except Exception as e:
            logger.error(f"Error in wildcard watcher: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
        finally:
            self._cleanup()

    def stop(self) -> None:
        """Stop the watcher thread."""
        self._running = False
        logger.info(f"Stopping wildcard watcher for: {self._pattern}")

    def pause(self) -> None:
        """Pause reading new content."""
        self._paused = True
        logger.info(f"Paused wildcard watcher for: {self._pattern}")

    def resume(self) -> None:
        """Resume reading new content."""
        self._paused = False
        logger.info(f"Resumed wildcard watcher for: {self._pattern}")

    def is_paused(self) -> bool:
        """Check if watcher is paused.

        Returns:
            True if paused
        """
        return self._paused

    def _find_latest_matching_file(self) -> Path | None:
        """Find the most recently modified file matching the pattern.

        Returns:
            Path to latest file, or None if no matches
        """
        matching_files = glob.glob(self._pattern)
        if not matching_files:
            return None

        # Sort by modification time, newest first
        matching_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        latest = Path(matching_files[0])
        logger.debug(
            f"Latest matching file: {latest} (from {len(matching_files)} matches)"
        )
        return latest

    def _switch_to_file(self, new_file: Path, is_initial: bool) -> None:
        """Switch to watching a new file.

        Args:
            new_file: Path to new file
            is_initial: True if this is the initial file (no interruption event)
        """
        old_file = self._current_file

        # Don't switch if it's the same file
        if old_file and old_file == new_file:
            logger.debug(f"Already watching {new_file}, skipping switch")
            return

        # Clean up old file
        if old_file and not is_initial:
            self._cleanup_current_file()
            self._log_manager.publish_stream_interrupted(
                self._path_key, f"Switching from {old_file.name} to {new_file.name}"
            )

        # Switch to new file
        self._current_file = new_file
        logger.info(f"Switching to file: {new_file}")

        try:
            mtime = new_file.stat().st_mtime
            logger.info(f"File details: name={new_file.name}, mtime={mtime}")
        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.warning(f"Cannot stat file {new_file}: {e}")

        # Read file content based on mode
        try:
            with open(new_file, "r", encoding="utf-8", errors="replace") as f:
                if self._tail_only:
                    # Tail-only mode: read last N lines
                    lines = f.readlines()
                    if len(lines) > self._tail_lines:
                        lines = lines[-self._tail_lines :]
                    content = "".join(lines)
                    logger.info(
                        f"Tail-only mode: read last {len(lines)} lines from {new_file}"
                    )
                else:
                    # Full log mode: read entire file
                    content = f.read()
                    logger.info(f"Full log mode: read entire file {new_file}")

                if content:
                    self._log_manager.publish_content(self._path_key, content)
                    if not self._paused:
                        self.new_lines.emit(content)
        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.error(f"Error reading file {new_file}: {e}")
            self.error_occurred.emit(f"Error reading file: {e}")
            return
        except Exception as e:
            logger.error(
                f"Unexpected error reading file {new_file}: {e}", exc_info=True
            )
            self.error_occurred.emit(f"Error reading file: {e}")
            return

        # Open for tailing
        try:
            self._file_handle = open(new_file, "r", encoding="utf-8", errors="replace")
            self._file_handle.seek(0, 2)  # Seek to end
            logger.info(f"Now tailing: {new_file}")
        except Exception as e:
            logger.error(f"Error opening file for tailing: {e}")
            self.error_occurred.emit(f"Error opening file: {e}")
            return

        # Publish events
        if is_initial:
            # For initial file, just log it - don't publish interruption/resumption events
            logger.info(f"Initial file loaded: {new_file.name}")
        else:
            # Only publish stream resumed for actual file switches
            self._log_manager.publish_stream_resumed(self._path_key)
            self.file_switched.emit(str(old_file) if old_file else "", str(new_file))

    def _watch_directory(self) -> None:
        """Watch directory for new matching files."""
        pattern_path = Path(self._pattern)
        directory = str(pattern_path.parent)

        self._dir_handler = _DirectoryWatchHandler(
            self._pattern, self._on_new_file_created
        )

        # Mark current file as already seen to prevent duplicate notifications
        if self._current_file:
            self._dir_handler._seen_files.add(str(self._current_file))
            logger.debug(f"Marked initial file as seen: {self._current_file}")

        # Use shared observer for this directory to avoid FSEvents conflicts
        with _OBSERVER_LOCK:
            if directory in _DIRECTORY_OBSERVERS:
                # Reuse existing observer
                self._observer, ref_count = _DIRECTORY_OBSERVERS[directory]
                _DIRECTORY_OBSERVERS[directory] = (self._observer, ref_count + 1)
                logger.debug(
                    f"Reusing observer for directory: {directory} (refs: {ref_count + 1})"
                )
            else:
                # Create new observer
                self._observer = WatchdogObserver()
                self._observer.start()
                _DIRECTORY_OBSERVERS[directory] = (self._observer, 1)
                logger.debug(f"Created new observer for directory: {directory}")

            # Schedule handler on the observer
            self._observer.schedule(self._dir_handler, directory, recursive=False)
            logger.info(f"Watching directory: {directory}")

    def _on_new_file_created(self, file_path: str) -> None:
        """Callback when a new matching file is created.

        Args:
            file_path: Path to new file
        """
        new_file = Path(file_path)

        # Wait a bit for file to be fully created and accessible
        time.sleep(0.1)

        # Verify file exists and is accessible
        if not new_file.exists():
            logger.warning(f"New file detected but doesn't exist yet: {new_file}")
            return

        try:
            new_mtime = new_file.stat().st_mtime
        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.warning(f"Cannot access new file {new_file}: {e}")
            return

        # Check if this file is newer than current
        if self._current_file:
            try:
                current_mtime = self._current_file.stat().st_mtime
                if new_mtime > current_mtime:
                    logger.info(
                        f"Newer file detected: {new_file} (mtime: {new_mtime} > {current_mtime})"
                    )
                    self._switch_to_file(new_file, is_initial=False)
                else:
                    logger.debug(
                        f"Ignoring older file: {new_file} (mtime: {new_mtime} <= {current_mtime})"
                    )
            except (FileNotFoundError, PermissionError, OSError) as e:
                logger.warning(f"Cannot access current file {self._current_file}: {e}")
                # Current file is gone, switch to new one
                logger.info(
                    f"Switching to new file since current is inaccessible: {new_file}"
                )
                self._switch_to_file(new_file, is_initial=False)
        else:
            # No current file, switch to this one
            logger.info(f"No current file, switching to: {new_file}")
            self._switch_to_file(new_file, is_initial=False)

    def _read_new_content(self) -> None:
        """Read new content from current file."""
        if not self._file_handle:
            return

        try:
            lines = self._file_handle.readlines()
            if lines:
                content = "".join(lines)
                self._log_manager.publish_content(self._path_key, content)
                if not self._paused:
                    self.new_lines.emit(content)
        except Exception as e:
            logger.error(f"Error reading content: {e}")
            self.error_occurred.emit(f"Error reading file: {e}")

    def _cleanup_current_file(self) -> None:
        """Clean up current file handle."""
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception as e:
                logger.error(f"Error closing file: {e}")
            self._file_handle = None

    def _cleanup(self) -> None:
        """Clean up all resources."""
        logger.debug(f"Cleanup called for pattern: {self._pattern}")

        self._cleanup_current_file()

        if self._observer:
            try:
                # Unregister handler from shared observer
                pattern_path = Path(self._pattern)
                directory = str(pattern_path.parent)

                if self._dir_handler:
                    self._observer.unschedule(self._dir_handler)
                    logger.debug(f"Unscheduled handler for directory: {directory}")

                # Decrement reference count and stop observer if no more references
                with _OBSERVER_LOCK:
                    if directory in _DIRECTORY_OBSERVERS:
                        observer, ref_count = _DIRECTORY_OBSERVERS[directory]
                        if ref_count <= 1:
                            # Last reference, stop and remove observer
                            if observer.is_alive():
                                observer.stop()
                                observer.join(timeout=1.0)
                            del _DIRECTORY_OBSERVERS[directory]
                            logger.debug(
                                f"Stopped and removed observer for directory: {directory}"
                            )
                        else:
                            # Decrement reference count
                            _DIRECTORY_OBSERVERS[directory] = (observer, ref_count - 1)
                            logger.debug(
                                f"Decremented observer ref count for directory: {directory} (refs: {ref_count - 1})"
                            )
            except Exception as e:
                logger.error(f"Error cleaning up observer: {e}")
            self._observer = None
