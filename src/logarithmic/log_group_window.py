"""Log Group Window - displays multiple log files in tabs or combined view."""

import logging
import time
from pathlib import Path
from typing import Callable

from PySide6.QtGui import QCloseEvent
from PySide6.QtGui import QMoveEvent
from PySide6.QtGui import QResizeEvent
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QTabWidget
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from logarithmic.content_controller import ContentController
from logarithmic.fonts import get_font_manager

logger = logging.getLogger(__name__)


class LogGroupWindow(QWidget):
    """A window that displays multiple log files in tabs or combined mode.

    Modes:
    - Tabbed: Each log file in its own tab
    - Combined: All logs merged into one view with prefixes
    """

    def __init__(
        self,
        group_name: str,
        theme_colors: dict | None = None,
        parent: QWidget | None = None,
        initial_mode: str = "combined",
    ) -> None:
        """Initialize the log group window.

        Args:
            group_name: Name of the log group
            theme_colors: Theme color settings
            parent: Parent widget
            initial_mode: Initial display mode ("tabbed" or "combined")
        """
        super().__init__(parent)
        self.group_name = group_name
        self._fonts = get_font_manager()
        self._theme_colors = theme_colors or {}
        self._position_changed_callback: Callable[[int, int, int, int], None] | None = (
            None
        )
        self._last_saved_position: tuple[int, int, int, int] | None = None
        self._set_default_size_callback: Callable[[int, int], None] | None = None
        self._get_other_windows_callback: Callable[[], list] | None = None
        self._snap_threshold = 20
        self._mode_changed_callback: Callable[[str], None] | None = None

        # Mode: "tabbed" or "combined" - store initial mode to apply after setup
        self._initial_mode = initial_mode
        self._mode = "tabbed"  # Start in tabbed, switch after logs added

        # Track log files in this group
        self._log_paths: list[str] = []

        # Tab widgets for tabbed mode (path -> dict with 'controller')
        self._tab_widgets: dict[str, dict] = {}

        # Combined mode controller
        self._combined_controller: ContentController | None = None
        self._combined_line_count: int = 0  # Separate line count for combined view only

        # Line counts per log (for tabbed mode)
        self._line_counts: dict[str, int] = {}

        # Buffer content for each log (preserved across mode switches)
        self._log_buffers: dict[str, str] = {}

        # Debouncing for combined clear to prevent spam
        self._last_combined_clear_time: float = 0
        self._last_mode_switch_time: float = 0
        self._initialized = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self.setWindowTitle(f"Log Group: {self.group_name}")
        self.resize(1000, 800)

        # Main layout
        layout = QVBoxLayout(self)

        # Top: Controls
        controls_layout = QHBoxLayout()

        # Mode toggle button
        self.mode_button = QPushButton("Switch to Combined Mode")
        self.mode_button.setFont(self._fonts.get_ui_font(10, bold=True))
        self.mode_button.clicked.connect(self._on_mode_toggle)
        controls_layout.addWidget(self.mode_button)

        # Set Default Size button
        set_size_button = QPushButton("Set Default Size")
        set_size_button.setFont(self._fonts.get_ui_font(10))
        set_size_button.setToolTip(
            "Set the current window size as the default for all new log windows"
        )
        set_size_button.clicked.connect(self._on_set_default_size_clicked)
        controls_layout.addWidget(set_size_button)

        controls_layout.addStretch()

        # Status label
        self.status_label = QLabel()
        self.status_label.setFont(self._fonts.get_ui_font(10))
        controls_layout.addWidget(self.status_label)

        layout.addLayout(controls_layout)

        # Center: Tab widget (for tabbed mode) or plain text (for combined mode)
        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(self._fonts.get_ui_font(10))
        # Make tabs expand to fit content with larger fonts
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555555;
            }
            QTabBar::tab {
                padding: 0.5em 1em;
                min-width: 5em;
            }
        """)
        layout.addWidget(self.tab_widget)

        self._update_status()

    def add_log(self, path: str) -> None:
        """Add a log file to this group.

        Args:
            path: Log file path
        """
        if path in self._log_paths:
            logger.warning(f"Log {path} already in group {self.group_name}")
            return

        self._log_paths.append(path)
        self._line_counts[path] = 0

        if self._mode == "tabbed":
            self._add_tab(path)

        self._update_status()
        logger.info(f"Added {path} to group {self.group_name}")

    def remove_log(self, path: str) -> None:
        """Remove a log file from this group.

        Args:
            path: Log file path
        """
        if path not in self._log_paths:
            return

        self._log_paths.remove(path)

        if path in self._line_counts:
            del self._line_counts[path]

        if self._mode == "tabbed" and path in self._tab_widgets:
            # Find and remove tab
            for i in range(self.tab_widget.count()):
                if self.tab_widget.tabText(i) == Path(path).name:
                    self.tab_widget.removeTab(i)
                    break
            del self._tab_widgets[path]

        self._update_status()
        logger.info(f"Removed {path} from group {self.group_name}")

    def _add_tab(self, path: str) -> None:
        """Add a new tab for a log file.

        Args:
            path: Log file path
        """
        # Create content controller
        filename = Path(path).name
        controller = ContentController(
            self._fonts,
            filename,
            show_filename_in_status=True,
            theme_colors=self._theme_colors,
        )

        # Create the widget
        widget = controller.create_widget()

        # Add tab
        self.tab_widget.addTab(widget, filename)

        # Store controller
        self._tab_widgets[path] = {"controller": controller}

        # Restore buffered content if exists
        if path in self._log_buffers:
            controller.set_text(self._log_buffers[path])
            self._line_counts[path] = self._log_buffers[path].count("\n")
        else:
            self._line_counts[path] = 0

        logger.info(f"Added tab for {path}")

    def _on_mode_toggle(self) -> None:
        """Toggle between tabbed and combined mode."""
        if self._mode == "tabbed":
            self._switch_to_combined()
        else:
            self._switch_to_tabbed()

        # Notify callback of mode change
        if self._mode_changed_callback:
            self._mode_changed_callback(self._mode)

    def set_mode_changed_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for when mode changes.

        Args:
            callback: Function that takes the new mode string
        """
        self._mode_changed_callback = callback

    def initialize_mode(self) -> None:
        """Initialize to the requested mode after logs are added.

        Call this after all logs have been added to the group.
        """
        if self._initialized:
            return

        self._initialized = True
        if self._initial_mode == "combined" and self._mode != "combined":
            self._switch_to_combined()
            logger.info(f"Initialized group {self.group_name} in combined mode")

    def _switch_to_combined(self) -> None:
        """Switch to combined mode."""
        # Debounce: ignore if called within 0.5 seconds of last switch
        current_time = time.time()
        if current_time - self._last_mode_switch_time < 0.5:
            logger.debug(
                f"Ignoring duplicate mode switch for group {self.group_name} "
                f"(debounced within 0.5 seconds)"
            )
            return

        self._last_mode_switch_time = current_time

        self._mode = "combined"
        self.mode_button.setText("Switch to Tabbed Mode")

        # Reset combined view line count (fresh start)
        self._combined_line_count = 0

        # Save current tab content to buffers
        for path, widgets in self._tab_widgets.items():
            controller = widgets["controller"]
            self._log_buffers[path] = controller.get_text()

        # Clear tabs
        self.tab_widget.clear()
        self._tab_widgets.clear()

        # Create content controller for combined view with prefix_lines enabled
        self._combined_controller = ContentController(
            self._fonts,
            "Combined View",
            show_filename_in_status=False,
            theme_colors=self._theme_colors,
            prefix_lines=True,  # Enable line prefixing for combined mode
        )

        # Create the widget
        widget = self._combined_controller.create_widget()

        # Override the clear button behavior to show warning message
        if self._combined_controller._clear_btn:
            # Disconnect default clear behavior
            self._combined_controller._clear_btn.clicked.disconnect()
            # Connect to our custom clear handler
            self._combined_controller._clear_btn.clicked.connect(
                self._on_combined_clear
            )

        # Start with empty combined view - warning will be shown only when user clears
        logger.debug(f"Initializing empty combined view for group {self.group_name}")
        self._combined_controller.set_text("")

        # Add tab
        self.tab_widget.addTab(widget, "Combined View")

        logger.info(f"Switched group {self.group_name} to combined mode")
        self._update_status()

    def _switch_to_tabbed(self) -> None:
        """Switch to tabbed mode."""
        self._mode = "tabbed"
        self.mode_button.setText("Switch to Combined Mode")

        # Clear combined view
        self.tab_widget.clear()
        self._combined_controller = None

        # Recreate tabs (will restore buffered content)
        for path in self._log_paths:
            self._add_tab(path)

        logger.info(f"Switched group {self.group_name} to tabbed mode")
        self._update_status()

    def on_log_content(self, path: str, content: str) -> None:
        """Called when new log content is available.

        Args:
            path: Log file path
            content: New content to append
        """
        if path not in self._log_paths:
            return

        self._line_counts[path] += content.count("\n")

        # Always buffer content
        if path not in self._log_buffers:
            self._log_buffers[path] = ""
        self._log_buffers[path] += content

        if self._mode == "tabbed":
            # Append to specific tab using controller
            if path in self._tab_widgets:
                controller = self._tab_widgets[path]["controller"]
                if not controller.is_paused():
                    controller.append_text(content)
        else:
            # Append to combined view with source prefix
            if self._combined_controller:
                if not self._combined_controller.is_paused():
                    filename = Path(path).name
                    # Update combined view line count
                    self._combined_line_count += content.count("\n")
                    logger.debug(
                        f"Appending {len(content)} chars to combined view from {filename}"
                    )
                    # ContentController will handle prefixing with source
                    self._combined_controller.append_text(content, source=filename)

        self._update_status()

    def on_log_cleared(self, path: str) -> None:
        """Called when log buffer is cleared.

        Args:
            path: Log file path
        """
        if path not in self._log_paths:
            return

        self._line_counts[path] = 0

        # Clear the buffer for this path
        if path in self._log_buffers:
            self._log_buffers[path] = ""

        if self._mode == "tabbed" and path in self._tab_widgets:
            # Clear the controller's display, not the dict itself!
            controller = self._tab_widgets[path].get("controller")
            if controller:
                controller.clear()

        self._update_status()

    def on_stream_interrupted(self, path: str, reason: str) -> None:
        """Called when the log stream is interrupted.

        Args:
            path: Log file path
            reason: Reason for interruption
        """
        if path not in self._log_paths:
            return

        separator = f"\n{'═' * 70}\n║  Stream Interrupted: {reason}\n{'═' * 70}\n"
        self.on_log_content(path, separator)

    def on_stream_resumed(self, path: str) -> None:
        """Called when the log stream resumes.

        Args:
            path: Log file path
        """
        if path not in self._log_paths:
            return

        separator = f"\n{'═' * 70}\n║  Stream Resumed\n{'═' * 70}\n\n"
        self.on_log_content(path, separator)

    def _update_status(self) -> None:
        """Update the status label."""
        total_lines = sum(self._line_counts.values())
        mode_str = "Combined" if self._mode == "combined" else "Tabbed"
        self.status_label.setText(
            f"{len(self._log_paths)} logs | {total_lines:,} total lines | {mode_str} mode"
        )

    def _update_tab_status(self, path: str) -> None:
        """Update status bar for a specific tab.

        Args:
            path: Log file path
        """
        if path not in self._tab_widgets:
            return

        tab_data = self._tab_widgets[path]
        status_bar = tab_data["status_bar"]

        line_count = self._line_counts.get(path, 0)
        mode = "🔴 LIVE" if tab_data["is_live"] else "⏸ SCROLL"
        pause_status = " [PAUSED]" if tab_data["is_paused"] else ""

        filename = Path(path).name
        status_text = (
            f"📄 {filename}  |  📊 {line_count:,} lines  |  {mode}{pause_status}"
        )
        status_bar.setText(status_text)

    def _on_tab_scroll_changed(self, path: str) -> None:
        """Handle scroll change in a tab.

        Args:
            path: Log file path
        """
        if path not in self._tab_widgets:
            return

        tab_data = self._tab_widgets[path]
        text_edit = tab_data["text_edit"]
        scrollbar = text_edit.verticalScrollBar()

        # Check if scrolled away from bottom
        is_at_bottom = scrollbar.value() >= scrollbar.maximum() - 10

        if not is_at_bottom and tab_data["is_live"]:
            # User scrolled up, exit live mode
            tab_data["is_live"] = False
            tab_data["go_live_btn"].show()
            self._update_tab_status(path)

    def _on_tab_go_live(self, path: str) -> None:
        """Handle Go Live button click for a tab.

        Args:
            path: Log file path
        """
        if path not in self._tab_widgets:
            return

        tab_data = self._tab_widgets[path]
        tab_data["is_live"] = True
        tab_data["go_live_btn"].hide()

        # Scroll to bottom
        tab_data["text_edit"].moveCursor(QTextCursor.MoveOperation.End)

        self._update_tab_status(path)

    def _on_tab_pause(self, path: str, checked: bool) -> None:
        """Handle Pause button toggle for a tab.

        Args:
            path: Log file path
            checked: Whether pause is enabled
        """
        if path not in self._tab_widgets:
            return

        tab_data = self._tab_widgets[path]
        tab_data["is_paused"] = checked
        self._update_tab_status(path)

    def _on_tab_clear(self, path: str) -> None:
        """Handle Clear button click for a tab.

        Args:
            path: Log file path
        """
        if path not in self._tab_widgets:
            return

        tab_data = self._tab_widgets[path]
        tab_data["text_edit"].clear()
        self._line_counts[path] = 0
        self._log_buffers[path] = ""
        self._update_tab_status(path)

    def _on_combined_clear(self) -> None:
        """Handle Clear button click in combined mode.

        This only clears the visible combined view, not the underlying log buffers.
        Tabbed mode content is preserved.
        """
        if not self._combined_controller:
            return

        # Debounce: ignore if called within 1 second of last clear
        current_time = time.time()
        if current_time - self._last_combined_clear_time < 1.0:
            logger.debug(
                f"Ignoring duplicate combined clear for group {self.group_name} "
                f"(debounced within 1 second)"
            )
            return

        self._last_combined_clear_time = current_time
        logger.info(f"Clearing combined view for group {self.group_name}")

        # Use controller's clear method
        warning = (
            "═" * 80 + "\n"
            "║  COMBINED MODE - History Cleared\n"
            "║  Only new log entries will be displayed here.\n"
            "║  Switch back to Tabbed Mode to see full history.\n"
            "═" * 80 + "\n\n"
        )
        self._combined_controller.set_text(warning)

        # Reset ONLY the combined view line count (not the individual log line counts)
        self._combined_line_count = 0

        logger.info("Combined view cleared successfully")

    def _on_set_default_size_clicked(self) -> None:
        """Handle Set Default Size button click."""
        width = self.width()
        height = self.height()

        if self._set_default_size_callback:
            self._set_default_size_callback(width, height)
            logger.info(f"Set default size to {width}x{height}")

    def set_default_size_callback(self, callback: Callable[[int, int], None]) -> None:
        """Set callback for when user sets default size.

        Args:
            callback: Function to call with (width, height)
        """
        self._set_default_size_callback = callback

    def set_other_windows_callback(self, callback: Callable[[], list]) -> None:
        """Set callback to get list of other windows for snapping.

        Args:
            callback: Function that returns list of other window instances
        """
        self._get_other_windows_callback = callback

    def set_position_changed_callback(
        self, callback: Callable[[int, int, int, int], None]
    ) -> None:
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
            other_windows: List of other window instances

        Returns:
            Tuple of (x, y) if should snap, None otherwise
        """
        my_rect = self.geometry()
        my_frame = self.frameGeometry()
        my_x = my_rect.x()
        my_y = my_rect.y()
        my_width = my_rect.width()
        my_height = my_rect.height()

        title_bar_height = my_frame.height() - my_rect.height()
        threshold = self._snap_threshold

        for other in other_windows:
            other_rect = other.geometry()
            other_x = other_rect.x()
            other_y = other_rect.y()
            other_width = other_rect.width()
            other_height = other_rect.height()

            # Check for snap to right edge
            if abs((other_x + other_width) - my_x) < threshold:
                if not (my_y + my_height < other_y or my_y > other_y + other_height):
                    return (other_x + other_width, other_y)

            # Check for snap to left edge
            if abs(other_x - (my_x + my_width)) < threshold:
                if not (my_y + my_height < other_y or my_y > other_y + other_height):
                    return (other_x - my_width, other_y)

            # Check for snap to bottom edge
            if abs((other_y + other_height) - my_y) < threshold:
                if not (my_x + my_width < other_x or my_x > other_x + other_width):
                    return (other_x, other_y + other_height)

            # Check for snap to top edge (account for title bar)
            if abs(other_y - (my_y + my_height)) < threshold:
                if not (my_x + my_width < other_x or my_x > other_x + other_width):
                    return (other_x, other_y - my_height - title_bar_height)

        return None

    def _save_position_if_changed(self) -> None:
        """Save position only if it has changed significantly."""
        if self._position_changed_callback:
            pos = self.pos()
            size = self.size()
            current = (pos.x(), pos.y(), size.width(), size.height())

            if self._last_saved_position is None:
                self._position_changed_callback(*current)
                self._last_saved_position = current
            else:
                old_x, old_y, old_w, old_h = self._last_saved_position
                if (
                    abs(current[0] - old_x) > 5
                    or abs(current[1] - old_y) > 5
                    or current[2] != old_w
                    or current[3] != old_h
                ):
                    self._position_changed_callback(*current)
                    self._last_saved_position = current

    def set_log_font_size(self, size: int) -> None:
        """Set log content font size for all tabs.

        Args:
            size: Font size in points
        """
        # Update tabbed mode controllers
        for widgets in self._tab_widgets.values():
            controller = widgets["controller"]
            controller.set_log_font_size(size)

        # Update combined mode controller
        if self._combined_controller:
            self._combined_controller.set_log_font_size(size)

    def set_ui_font_size(self, size: int) -> None:
        """Set UI elements font size for all tabs.

        Args:
            size: Font size in points
        """
        # Update tabbed mode controllers
        for widgets in self._tab_widgets.values():
            controller = widgets["controller"]
            controller.set_ui_font_size(size)

        # Update combined mode controller
        if self._combined_controller:
            self._combined_controller.set_ui_font_size(size)

    def set_status_font_size(self, size: int) -> None:
        """Set status bar font size for all tabs.

        Args:
            size: Font size in points
        """
        # Update tabbed mode controllers
        for widgets in self._tab_widgets.values():
            controller = widgets["controller"]
            controller.set_status_font_size(size)

        # Update combined mode controller
        if self._combined_controller:
            self._combined_controller.set_status_font_size(size)

    def update_theme(self, theme_colors: dict) -> None:
        """Update theme colors for all controllers.

        Args:
            theme_colors: New theme color dictionary
        """
        self._theme_colors = theme_colors

        # Update tabbed mode controllers
        for widgets in self._tab_widgets.values():
            controller = widgets["controller"]
            controller.update_theme(theme_colors)

        # Update combined mode controller
        if self._combined_controller:
            self._combined_controller.update_theme(theme_colors)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close event.

        Args:
            event: Close event
        """
        # ContentController handles cleanup automatically
        event.accept()
