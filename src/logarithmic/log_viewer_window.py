"""Log Viewer Window - displays tailed log content."""

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtGui import QMoveEvent
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from logarithmic.content_controller import ContentController
from logarithmic.fonts import get_font_manager

logger = logging.getLogger(__name__)


class LogViewerWindow(QWidget):
    """A separate window that displays the content of a single log file.

    This window shows the tailed output of a log file with controls to
    pause/resume tailing and clear the display.

    Implements the LogSubscriber protocol to receive log events from LogManager.
    """

    def __init__(self, file_path: str, theme_colors: dict | None = None):
        """Initialize the log viewer window.

        Args:
            file_path: Path to the log file to display
            theme_colors: Theme color settings
        """
        super().__init__()

        self._path_str = file_path
        self._fonts = get_font_manager()
        self._theme_colors = theme_colors or {}

        # Callbacks
        self._set_default_size_callback: Callable[[int, int], None] | None = None
        self._get_other_windows_callback: Callable[[], list] | None = None

        # Track last saved position
        self._last_saved_position: tuple[int, int, int, int] | None = None

        # Snap threshold in pixels
        self._snap_threshold = 20

        # Create content controller
        filename = Path(file_path).name
        self._content_controller = ContentController(
            self._fonts,
            filename,
            show_filename_in_status=True,
            theme_colors=self._theme_colors
        )

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self.resize(800, 600)

        # Set window title
        filename = Path(self._path_str).name
        self.setWindowTitle(f"Log Viewer - {filename}")

        # Main layout
        layout = QVBoxLayout(self)

        # Window controls (above content)
        controls_layout = QHBoxLayout()

        # Set Default Size button
        set_size_button = QPushButton("Set Default Size")
        set_size_button.setFont(self._fonts.get_ui_font(10))
        set_size_button.setToolTip("Set the current window size as the default for all new log windows")
        set_size_button.clicked.connect(self._on_set_default_size_clicked)
        controls_layout.addWidget(set_size_button)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Content controller widget (includes controls, text edit, status bar)
        content_widget = self._content_controller.create_widget()
        layout.addWidget(content_widget)

    def append_text(self, text: str) -> None:
        """Append new text to the log view.

        Args:
            text: Text content to append
        """
        self._content_controller.append_text(text)

    def set_status_message(self, message: str) -> None:
        """Display a status message in the log view.

        Args:
            message: Status message to display
        """
        current_text = self._content_controller.get_text()
        self._content_controller.set_text(current_text + f"\n[{message}]\n")

    def is_paused(self) -> bool:
        """Check if the viewer is currently paused.

        Returns:
            True if paused, False otherwise
        """
        return self._content_controller.is_paused()

    def set_pause_callback(self, callback: Callable[[bool], None]) -> None:
        """Set callback for when pause state changes.

        Args:
            callback: Function to call with pause state (True=paused, False=resumed)
        """
        self._content_controller.set_pause_callback(callback)

    def set_default_size_callback(self, callback: Callable[[int, int], None]) -> None:
        """Set callback for when user sets default size.

        Args:
            callback: Function to call with (width, height)
        """
        self._set_default_size_callback = callback

    def set_other_windows_callback(self, callback: Callable[[], list]) -> None:
        """Set callback to get list of other windows for snapping.

        Args:
            callback: Function that returns list of other LogViewerWindow instances
        """
        self._get_other_windows_callback = callback

    def _on_set_default_size_clicked(self) -> None:
        """Handle Set Default Size button click."""
        width = self.width()
        height = self.height()

        if self._set_default_size_callback:
            self._set_default_size_callback(width, height)
            logger.info(f"Set default size to {width}x{height}")

    def set_position_changed_callback(self, callback: Callable[[int, int, int, int], None]) -> None:
        """Set callback for when window position/size changes.

        Args:
            callback: Function that takes (x, y, width, height)
        """
        self._position_changed_callback = callback

    def moveEvent(self, event: QMoveEvent) -> None:
        """Handle window move event with auto-snapping.

        Args:
            event: Move event
        """
        # Auto-snap to other windows if callback is set
        if self._get_other_windows_callback:
            other_windows = self._get_other_windows_callback()
            if other_windows:
                snapped_pos = self._calculate_snap_position(other_windows)
                if snapped_pos:
                    # Move to snapped position
                    super().moveEvent(event)
                    self.move(snapped_pos[0], snapped_pos[1])
                    self._save_position_if_changed()
                    return

        super().moveEvent(event)
        self._save_position_if_changed()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Handle window resize event.

        Args:
            event: Resize event
        """
        super().resizeEvent(event)
        self._save_position_if_changed()

    def _calculate_snap_position(self, other_windows: list) -> tuple[int, int] | None:
        """Calculate snapped position if close to another window.

        Args:
            other_windows: List of other LogViewerWindow instances

        Returns:
            Tuple of (x, y) if should snap, None otherwise
        """
        my_rect = self.geometry()
        my_frame = self.frameGeometry()  # Includes title bar
        my_x = my_rect.x()
        my_y = my_rect.y()
        my_width = my_rect.width()
        my_height = my_rect.height()

        # Calculate title bar height (frame height - content height)
        title_bar_height = my_frame.height() - my_rect.height()

        threshold = self._snap_threshold

        for other in other_windows:
            other_rect = other.geometry()
            other.frameGeometry()
            other_x = other_rect.x()
            other_y = other_rect.y()
            other_width = other_rect.width()
            other_height = other_rect.height()

            # Check for snap to right edge of other window
            if abs((other_x + other_width) - my_x) < threshold:
                # Check if vertically aligned enough
                if not (my_y + my_height < other_y or my_y > other_y + other_height):
                    return (other_x + other_width, other_y)

            # Check for snap to left edge of other window
            if abs(other_x - (my_x + my_width)) < threshold:
                # Check if vertically aligned enough
                if not (my_y + my_height < other_y or my_y > other_y + other_height):
                    return (other_x - my_width, other_y)

            # Check for snap to bottom edge of other window
            if abs((other_y + other_height) - my_y) < threshold:
                # Check if horizontally aligned enough
                if not (my_x + my_width < other_x or my_x > other_x + other_width):
                    return (other_x, other_y + other_height)

            # Check for snap to top edge of other window (account for title bar)
            if abs(other_y - (my_y + my_height)) < threshold:
                # Check if horizontally aligned enough
                if not (my_x + my_width < other_x or my_x > other_x + other_width):
                    # Snap above, but leave room for the title bar
                    return (other_x, other_y - my_height - title_bar_height)

        return None

    def _save_position_if_changed(self) -> None:
        """Save position only if it has changed significantly."""
        if self._position_changed_callback:
            pos = self.pos()
            size = self.size()
            current = (pos.x(), pos.y(), size.width(), size.height())

            # Only save if position changed by more than 5 pixels or size changed
            if self._last_saved_position is None:
                self._position_changed_callback(*current)
                self._last_saved_position = current
            else:
                dx = abs(current[0] - self._last_saved_position[0])
                dy = abs(current[1] - self._last_saved_position[1])
                dw = abs(current[2] - self._last_saved_position[2])
                dh = abs(current[3] - self._last_saved_position[3])

                if dx > 5 or dy > 5 or dw > 0 or dh > 0:
                    self._position_changed_callback(*current)
                    self._last_saved_position = current

    # LogSubscriber protocol methods

    def on_log_content(self, path: str, content: str) -> None:
        """Called when new log content is available.

        Args:
            path: Log file path
            content: New content to append
        """
        if path == self._path_str:
            if not self.is_paused():
                self.append_text(content)
                logger.debug(f"Appended {len(content)} chars to viewer for {path}")
            else:
                logger.debug(f"Content received but viewer is paused for {path}")

    def on_log_cleared(self, path: str) -> None:
        """Called when log buffer is cleared.

        Args:
            path: Log file path
        """
        if path == self._path_str:
            self._content_controller.clear()
            logger.info(f"Cleared viewer for {path}")

    def on_stream_interrupted(self, path: str, reason: str) -> None:
        """Called when the log stream is interrupted.

        Args:
            path: Log file path
            reason: Reason for interruption
        """
        if path == self._path_str:
            # Extract new filename from reason first
            if "Initial file:" in reason:
                # Initial file for wildcard - just set the name, don't show separator
                parts = reason.split("Initial file:")
                if len(parts) == 2:
                    new_filename = parts[1].strip()
                    if '\\' in new_filename or '/' in new_filename:
                        self._current_file_name = Path(new_filename).name
                    else:
                        self._current_file_name = new_filename
                    logger.info(f"Initial wildcard file: {self._current_file_name}")
                return  # Don't show separator for initial file

            # Show separator for actual interruptions
            separator = (
                "\n"
                "═" * 70 + "\n"
                f"║  STREAM INTERRUPTED: {reason}\n"
                f"║  Waiting for file to be recreated...\n"
                "═" * 70 + "\n"
            )
            current_text = self._content_controller.get_text()
            self._content_controller.set_text(current_text + separator)

            # Extract new filename from reason
            if "Switched to file:" in reason:
                # Extract filename from reason (format: "Switched to file: path/to/file.txt")
                try:
                    new_file = reason.split("Switched to file:")[1].strip()
                    self._current_file_name = new_file
                    self._restart_count += 1
                    logger.info(f"Updated current file to: {new_file}, restart count: {self._restart_count}")
                except Exception as e:
                    logger.error(f"Failed to extract filename from reason: {e}")

            logger.info(f"Displayed stream interruption for {path}: {reason}")

    def on_stream_resumed(self, path: str) -> None:
        """Called when the log stream resumes.

            path: Log file path
        """
        if path == self._path_str:
            separator = (
                "\n"
                "═" * 70 + "\n"
                "║  Stream Resumed - File Recreated\n"
                "═" * 70 + "\n"
                "\n"
            )
            current_text = self._content_controller.get_text()
            self._content_controller.set_text(current_text + separator)
            logger.info(f"Displayed stream resumption for {path}")


    def flash_window(self) -> None:
        """Flash the window to get user's attention."""
        # Save original window title
        original_title = self.windowTitle()

        # Flash by changing title briefly
        self.setWindowTitle(f"⚠️ {original_title} ⚠️")

        # Restore after 500ms
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, lambda: self.setWindowTitle(original_title))

        logger.info(f"Flashed window for {self._path_str}")

    def set_log_font_size(self, size: int) -> None:
        """Set log content font size.

        Args:
            size: Font size in points
        """
        self._content_controller.set_log_font_size(size)

    def set_ui_font_size(self, size: int) -> None:
        """Set UI elements font size.

        Args:
            size: Font size in points
        """
        self._content_controller.set_ui_font_size(size)

    def set_status_font_size(self, size: int) -> None:
        """Set status bar font size.

        Args:
            size: Font size in points
        """
        self._content_controller.set_status_font_size(size)

    def update_theme(self, theme_colors: dict) -> None:
        """Update theme colors.

        Args:
            theme_colors: New theme color dictionary
        """
        self._theme_colors = theme_colors
        self._content_controller.update_theme(theme_colors)
