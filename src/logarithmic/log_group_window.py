"""Log Group Window - displays multiple log files in tabs or combined view."""

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QMoveEvent
from PySide6.QtGui import QResizeEvent
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QButtonGroup
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QMainWindow
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QRadioButton
from PySide6.QtWidgets import QTabWidget
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from logarithmic.fonts import get_font_manager

logger = logging.getLogger(__name__)


class LogGroupWindow(QWidget):
    """A window that displays multiple log files in tabs or combined mode.
    
    Modes:
    - Tabbed: Each log file in its own tab
    - Combined: All logs merged into one view with prefixes
    """

    def __init__(self, group_name: str, parent: QWidget | None = None) -> None:
        """Initialize the log group window.
        
        Args:
            group_name: Name of the log group
            parent: Parent widget
        """
        super().__init__(parent)
        self.group_name = group_name
        self._fonts = get_font_manager()
        self._position_changed_callback: Callable[[int, int, int, int], None] | None = None
        self._last_saved_position: tuple[int, int, int, int] | None = None
        self._set_default_size_callback: Callable[[int, int], None] | None = None
        self._get_other_windows_callback: Callable[[], list] | None = None
        self._snap_threshold = 20
        
        # Mode: "tabbed" or "combined"
        self._mode = "tabbed"
        
        # Track log files in this group
        self._log_paths: list[str] = []
        
        # Tab widgets for tabbed mode (path -> dict with 'text_edit', 'status_bar', 'pause_btn', 'go_live_btn', 'is_live', 'is_paused')
        self._tab_widgets: dict[str, dict] = {}
        
        # Combined mode widget and controls
        self._combined_widget: QPlainTextEdit | None = None
        self._combined_controls: dict = {}  # Store combined mode controls
        self._combined_line_count: int = 0  # Separate line count for combined view only
        
        # Line counts per log (for tabbed mode)
        self._line_counts: dict[str, int] = {}
        
        # Buffer content for each log (preserved across mode switches)
        self._log_buffers: dict[str, str] = {}
        
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
        set_size_button.setToolTip("Set the current window size as the default for all new log windows")
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
        # Create tab container
        tab_container = QWidget()
        tab_layout = QVBoxLayout(tab_container)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        # Go Live button (hidden by default)
        go_live_btn = QPushButton("Go Live")
        go_live_btn.setFont(self._fonts.get_ui_font(10, bold=True))
        go_live_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        go_live_btn.hide()
        controls_layout.addWidget(go_live_btn)
        
        # Pause button
        pause_btn = QPushButton("Pause")
        pause_btn.setFont(self._fonts.get_ui_font(10))
        pause_btn.setCheckable(True)
        controls_layout.addWidget(pause_btn)
        
        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setFont(self._fonts.get_ui_font(10))
        clear_btn.clicked.connect(lambda: self._on_tab_clear(path))
        controls_layout.addWidget(clear_btn)
        
        controls_layout.addStretch()
        tab_layout.addLayout(controls_layout)
        
        # Text edit
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        text_edit.setFont(self._fonts.get_mono_font(9))
        
        # Connect scroll detection
        scrollbar = text_edit.verticalScrollBar()
        scrollbar.valueChanged.connect(lambda: self._on_tab_scroll_changed(path))
        
        tab_layout.addWidget(text_edit)
        
        # Status bar
        status_bar = QLabel()
        status_bar.setFont(self._fonts.get_ui_font(10))
        status_bar.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                color: #cccccc;
                padding: 5px;
                border-top: 1px solid #555555;
            }
        """)
        tab_layout.addWidget(status_bar)
        
        # Add tab
        filename = Path(path).name
        self.tab_widget.addTab(tab_container, filename)
        
        # Store widgets
        self._tab_widgets[path] = {
            'text_edit': text_edit,
            'status_bar': status_bar,
            'pause_btn': pause_btn,
            'go_live_btn': go_live_btn,
            'is_live': True,
            'is_paused': False
        }
        
        # Connect button handlers
        go_live_btn.clicked.connect(lambda: self._on_tab_go_live(path))
        pause_btn.toggled.connect(lambda checked: self._on_tab_pause(path, checked))
        
        # Restore buffered content if exists
        if path in self._log_buffers:
            text_edit.setPlainText(self._log_buffers[path])
            text_edit.moveCursor(QTextCursor.MoveOperation.End)
        
        self._update_tab_status(path)
    
    def _on_mode_toggle(self) -> None:
        """Toggle between tabbed and combined mode."""
        if self._mode == "tabbed":
            self._switch_to_combined()
        else:
            self._switch_to_tabbed()
    
    def _switch_to_combined(self) -> None:
        """Switch to combined mode."""
        self._mode = "combined"
        self.mode_button.setText("Switch to Tabbed Mode")
        
        # Reset combined view line count (fresh start)
        self._combined_line_count = 0
        
        # Save current tab content to buffers
        for path, widgets in self._tab_widgets.items():
            self._log_buffers[path] = widgets['text_edit'].toPlainText()
        
        # Clear tabs
        self.tab_widget.clear()
        self._tab_widgets.clear()
        
        # Create combined view container
        combined_container = QWidget()
        combined_layout = QVBoxLayout(combined_container)
        combined_layout.setContentsMargins(0, 0, 0, 0)
        
        # Controls for combined mode
        controls_layout = QHBoxLayout()
        
        # Go Live button (hidden by default)
        go_live_btn = QPushButton("Go Live")
        go_live_btn.setFont(self._fonts.get_ui_font(10, bold=True))
        go_live_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        go_live_btn.hide()
        go_live_btn.clicked.connect(self._on_combined_go_live)
        controls_layout.addWidget(go_live_btn)
        
        # Pause button
        pause_btn = QPushButton("Pause")
        pause_btn.setFont(self._fonts.get_ui_font(10))
        pause_btn.setCheckable(True)
        pause_btn.toggled.connect(self._on_combined_pause)
        controls_layout.addWidget(pause_btn)
        
        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setFont(self._fonts.get_ui_font(10))
        clear_btn.clicked.connect(self._on_combined_clear)
        controls_layout.addWidget(clear_btn)
        
        controls_layout.addStretch()
        combined_layout.addLayout(controls_layout)
        
        # Create combined text view
        self._combined_widget = QPlainTextEdit()
        self._combined_widget.setReadOnly(True)
        self._combined_widget.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._combined_widget.setFont(self._fonts.get_mono_font(9))
        
        # Connect scroll detection
        scrollbar = self._combined_widget.verticalScrollBar()
        scrollbar.valueChanged.connect(self._on_combined_scroll_changed)
        
        # Add warning message
        warning = (
            "═" * 80 + "\n"
            "║  COMBINED MODE - History Cleared\n"
            "║  Only new log entries will be displayed here.\n"
            "║  Switch back to Tabbed Mode to see full history.\n"
            "═" * 80 + "\n\n"
        )
        self._combined_widget.setPlainText(warning)
        
        combined_layout.addWidget(self._combined_widget)
        
        # Status bar
        status_bar = QLabel()
        status_bar.setFont(self._fonts.get_ui_font(10))
        status_bar.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                color: #cccccc;
                padding: 5px;
                border-top: 1px solid #555555;
            }
        """)
        combined_layout.addWidget(status_bar)
        
        # Store controls
        self._combined_controls = {
            'go_live_btn': go_live_btn,
            'pause_btn': pause_btn,
            'status_bar': status_bar,
            'is_live': True,
            'is_paused': False
        }
        
        self.tab_widget.addTab(combined_container, "Combined View")
        
        self._update_combined_status()
        logger.info(f"Switched group {self.group_name} to combined mode")
        self._update_status()
    
    def _switch_to_tabbed(self) -> None:
        """Switch to tabbed mode."""
        self._mode = "tabbed"
        self.mode_button.setText("Switch to Combined Mode")
        
        # Clear combined view
        self.tab_widget.clear()
        self._combined_widget = None
        self._combined_controls.clear()
        
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
        
        self._line_counts[path] += content.count('\n')
        
        # Always buffer content
        if path not in self._log_buffers:
            self._log_buffers[path] = ""
        self._log_buffers[path] += content
        
        if self._mode == "tabbed":
            # Append to specific tab
            if path in self._tab_widgets:
                tab_data = self._tab_widgets[path]
                if not tab_data['is_paused']:
                    text_edit = tab_data['text_edit']
                    cursor = text_edit.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.End)
                    cursor.insertText(content)
                    text_edit.setTextCursor(cursor)
                    
                    if tab_data['is_live']:
                        text_edit.moveCursor(QTextCursor.MoveOperation.End)
                
                self._update_tab_status(path)
        else:
            # Append to combined view with live/pause mode support
            if self._combined_widget and self._combined_controls:
                if not self._combined_controls['is_paused']:
                    filename = Path(path).name
                    # Prefix each line with the log filename
                    lines = content.split('\n')
                    prefixed_lines = [f"[{filename}] {line}" if line else "" for line in lines]
                    prefixed_content = '\n'.join(prefixed_lines)
                    
                    # Update combined view line count
                    self._combined_line_count += content.count('\n')
                    
                    cursor = self._combined_widget.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.End)
                    cursor.insertText(prefixed_content)
                    self._combined_widget.setTextCursor(cursor)
                    
                    if self._combined_controls['is_live']:
                        self._combined_widget.moveCursor(QTextCursor.MoveOperation.End)
                
                self._update_combined_status()
        
        self._update_status()
    
    def on_log_cleared(self, path: str) -> None:
        """Called when log buffer is cleared.
        
        Args:
            path: Log file path
        """
        if path not in self._log_paths:
            return
        
        self._line_counts[path] = 0
        
        if self._mode == "tabbed" and path in self._tab_widgets:
            self._tab_widgets[path].clear()
        
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
        self.status_label.setText(f"{len(self._log_paths)} logs | {total_lines:,} total lines | {mode_str} mode")
    
    def _update_tab_status(self, path: str) -> None:
        """Update status bar for a specific tab.
        
        Args:
            path: Log file path
        """
        if path not in self._tab_widgets:
            return
        
        tab_data = self._tab_widgets[path]
        status_bar = tab_data['status_bar']
        
        line_count = self._line_counts.get(path, 0)
        mode = "🔴 LIVE" if tab_data['is_live'] else "⏸ SCROLL"
        pause_status = " [PAUSED]" if tab_data['is_paused'] else ""
        
        filename = Path(path).name
        status_text = f"📄 {filename}  |  📊 {line_count:,} lines  |  {mode}{pause_status}"
        status_bar.setText(status_text)
    
    def _on_tab_scroll_changed(self, path: str) -> None:
        """Handle scroll change in a tab.
        
        Args:
            path: Log file path
        """
        if path not in self._tab_widgets:
            return
        
        tab_data = self._tab_widgets[path]
        text_edit = tab_data['text_edit']
        scrollbar = text_edit.verticalScrollBar()
        
        # Check if scrolled away from bottom
        is_at_bottom = scrollbar.value() >= scrollbar.maximum() - 10
        
        if not is_at_bottom and tab_data['is_live']:
            # User scrolled up, exit live mode
            tab_data['is_live'] = False
            tab_data['go_live_btn'].show()
            self._update_tab_status(path)
    
    def _on_tab_go_live(self, path: str) -> None:
        """Handle Go Live button click for a tab.
        
        Args:
            path: Log file path
        """
        if path not in self._tab_widgets:
            return
        
        tab_data = self._tab_widgets[path]
        tab_data['is_live'] = True
        tab_data['go_live_btn'].hide()
        
        # Scroll to bottom
        tab_data['text_edit'].moveCursor(QTextCursor.MoveOperation.End)
        
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
        tab_data['is_paused'] = checked
        self._update_tab_status(path)
    
    def _on_tab_clear(self, path: str) -> None:
        """Handle Clear button click for a tab.
        
        Args:
            path: Log file path
        """
        if path not in self._tab_widgets:
            return
        
        tab_data = self._tab_widgets[path]
        tab_data['text_edit'].clear()
        self._line_counts[path] = 0
        self._log_buffers[path] = ""
        self._update_tab_status(path)
    
    def _on_combined_scroll_changed(self) -> None:
        """Handle scroll change in combined mode."""
        if not self._combined_widget or not self._combined_controls:
            return
        
        scrollbar = self._combined_widget.verticalScrollBar()
        is_at_bottom = scrollbar.value() >= scrollbar.maximum() - 10
        
        if not is_at_bottom and self._combined_controls['is_live']:
            # User scrolled up, exit live mode
            self._combined_controls['is_live'] = False
            self._combined_controls['go_live_btn'].show()
            self._update_combined_status()
    
    def _on_combined_go_live(self) -> None:
        """Handle Go Live button click in combined mode."""
        if not self._combined_controls:
            return
        
        self._combined_controls['is_live'] = True
        self._combined_controls['go_live_btn'].hide()
        
        # Scroll to bottom
        if self._combined_widget:
            self._combined_widget.moveCursor(QTextCursor.MoveOperation.End)
        
        self._update_combined_status()
    
    def _on_combined_pause(self, checked: bool) -> None:
        """Handle Pause button toggle in combined mode.
        
        Args:
            checked: Whether pause is enabled
        """
        if not self._combined_controls:
            return
        
        self._combined_controls['is_paused'] = checked
        self._update_combined_status()
    
    def _on_combined_clear(self) -> None:
        """Handle Clear button click in combined mode.
        
        This only clears the visible combined view, not the underlying log buffers.
        Tabbed mode content is preserved.
        """
        if not self._combined_widget or not self._combined_controls:
            return
        
        logger.info(f"Clearing combined view for group {self.group_name}")
        
        # Completely clear the widget first
        self._combined_widget.clear()
        
        # Then set the warning message
        warning = (
            "═" * 80 + "\n"
            "║  COMBINED MODE - History Cleared\n"
            "║  Only new log entries will be displayed here.\n"
            "║  Switch back to Tabbed Mode to see full history.\n"
            "═" * 80 + "\n\n"
        )
        self._combined_widget.setPlainText(warning)
        
        # Reset ONLY the combined view line count (not the individual log line counts)
        self._combined_line_count = 0
        
        # Ensure we're in live mode
        self._combined_controls['is_live'] = True
        self._combined_controls['go_live_btn'].hide()
        
        # Scroll to bottom (end of warning message)
        self._combined_widget.moveCursor(QTextCursor.MoveOperation.End)
        
        self._update_combined_status()
        logger.info(f"Combined view cleared successfully")
    
    def _update_combined_status(self) -> None:
        """Update status bar for combined mode."""
        if not self._combined_controls:
            return
        
        status_bar = self._combined_controls['status_bar']
        # Use combined view line count (not individual log counts)
        mode = "🔴 LIVE" if self._combined_controls['is_live'] else "⏸ SCROLL"
        pause_status = " [PAUSED]" if self._combined_controls['is_paused'] else ""
        
        status_text = f"📊 {self._combined_line_count:,} lines  |  {mode}{pause_status}"
        status_bar.setText(status_text)
    
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
                if (abs(current[0] - old_x) > 5 or abs(current[1] - old_y) > 5 or
                    current[2] != old_w or current[3] != old_h):
                    self._position_changed_callback(*current)
                    self._last_saved_position = current
