"""Main Control Window - manages log tracking and viewer windows."""

import logging
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QButtonGroup
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QInputDialog
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtWidgets import QFrame
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QListWidget
from PySide6.QtWidgets import QListWidgetItem
from PySide6.QtWidgets import QMainWindow
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QRadioButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from logarithmic.exceptions import FileAccessError
from logarithmic.exceptions import InvalidPathError
from logarithmic.file_watcher import FileWatcherThread
from logarithmic.fonts import get_font_manager
from logarithmic.log_group_window import LogGroupWindow
from logarithmic.log_manager import LogManager
from logarithmic.log_viewer_window import LogViewerWindow
from logarithmic.settings import Settings
from logarithmic.wildcard_watcher import WildcardFileWatcher

logger = logging.getLogger(__name__)


class TrackingModeDialog(QDialog):
    """Dialog to select tracking mode for a log file."""
    
    def __init__(self, file_path: str, parent=None):
        """Initialize the dialog.
        
        Args:
            file_path: Path to the log file
            parent: Parent widget
        """
        super().__init__(parent)
        self.file_path = file_path
        self.tracking_mode = "dedicated"  # Default
        self.wildcard_pattern = ""
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Select Tracking Mode")
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # File info
        file_label = QLabel(f"File: {Path(self.file_path).name}")
        file_label.setWordWrap(True)
        file_label.setToolTip(self.file_path)
        layout.addWidget(file_label)
        
        path_label = QLabel(f"Path: {self.file_path}")
        path_label.setWordWrap(True)
        path_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(path_label)
        
        layout.addSpacing(10)
        
        # Radio buttons
        self.dedicated_radio = QRadioButton("Dedicated - Track this specific file")
        self.dedicated_radio.setChecked(True)
        self.dedicated_radio.toggled.connect(self._on_mode_changed)
        layout.addWidget(self.dedicated_radio)
        
        self.wildcard_radio = QRadioButton("Wildcard - Track files matching a pattern")
        self.wildcard_radio.toggled.connect(self._on_mode_changed)
        layout.addWidget(self.wildcard_radio)
        
        # Wildcard pattern input
        wildcard_layout = QHBoxLayout()
        wildcard_layout.addSpacing(20)
        wildcard_label = QLabel("Pattern:")
        wildcard_layout.addWidget(wildcard_label)
        
        self.wildcard_input = QLineEdit()
        self.wildcard_input.setPlaceholderText("e.g., Cook-*.txt")
        self.wildcard_input.setEnabled(False)
        wildcard_layout.addWidget(self.wildcard_input)
        layout.addLayout(wildcard_layout)
        
        # Help text
        help_text = QLabel("Wildcard patterns use * for any characters (e.g., Log-*.txt)")
        help_text.setStyleSheet("color: gray; font-size: 9pt; font-style: italic;")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        
        layout.addSpacing(10)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _on_mode_changed(self) -> None:
        """Handle tracking mode change."""
        if self.wildcard_radio.isChecked():
            self.wildcard_input.setEnabled(True)
            # Pre-fill with filename as template
            filename = Path(self.file_path).name
            # Replace date/time patterns with wildcards
            import re
            pattern = re.sub(r'\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}', '*', filename)
            pattern = re.sub(r'\d{8}-\d{6}', '*', pattern)
            pattern = re.sub(r'\d+', '*', pattern)
            self.wildcard_input.setText(pattern)
            self.wildcard_input.setFocus()
            self.wildcard_input.selectAll()
        else:
            self.wildcard_input.setEnabled(False)
    
    def _on_accept(self) -> None:
        """Handle OK button click."""
        if self.wildcard_radio.isChecked():
            pattern = self.wildcard_input.text().strip()
            if not pattern:
                QMessageBox.warning(
                    self,
                    "Invalid Pattern",
                    "Please enter a wildcard pattern."
                )
                return
            
            if '*' not in pattern and '?' not in pattern:
                QMessageBox.warning(
                    self,
                    "Invalid Pattern",
                    "Wildcard pattern must contain * or ? characters."
                )
                return
            
            self.tracking_mode = "wildcard"
            # Build full pattern with directory
            parent_dir = Path(self.file_path).parent
            self.wildcard_pattern = str(parent_dir / pattern)
        else:
            self.tracking_mode = "dedicated"
        
        self.accept()


class MainWindow(QMainWindow):
    """Main control window for the Logarithmic application.
    
    This window provides controls for adding log files, managing the session,
    and opening log viewer windows.
    """

    def __init__(self) -> None:
        """Initialize the main window."""
        super().__init__()
        
        # Load custom fonts
        self._fonts = get_font_manager()
        
        # Central log manager
        self._log_manager = LogManager()
        
        # Track active watchers and viewer windows
        self._watchers: dict[str, FileWatcherThread] = {}
        self._viewer_windows: dict[str, LogViewerWindow] = {}
        self._group_windows: dict[str, LogGroupWindow] = {}  # group_name -> window
        self._log_groups: dict[str, str] = {}  # path_key -> group_name
        self._available_groups: list[str] = []  # List of group names
        
        # Track which windows should auto-open after content loads
        self._pending_window_opens: set[str] = set()
        
        # Settings manager
        self._settings = Settings()
        
        # Connect to log manager signals for auto-opening windows
        self._log_manager.log_content_available.connect(self._on_content_available_for_auto_open)
        
        self._setup_ui()
        self._restore_session()
        
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self.setWindowTitle("Logarithmic - Log Tracker")
        self.resize(600, 400)
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        
        # Set window title font
        self.setFont(self._fonts.get_ui_font(10))
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        control_frame = QFrame()
        control_frame.setFrameShape(QFrame.Shape.StyledPanel)
        control_layout = QHBoxLayout(control_frame)
        
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Enter log file path or wildcard pattern (e.g., C:/logs/*.txt)")
        self.path_input.setFont(self._fonts.get_ui_font(10))
        control_layout.addWidget(self.path_input)
        
        add_button = QPushButton("Add Log")
        add_button.setFont(self._fonts.get_ui_font(10, bold=True))
        add_button.clicked.connect(self._on_add_log)
        control_layout.addWidget(add_button)
        
        reset_session_button = QPushButton("Reset Session")
        reset_session_button.setFont(self._fonts.get_ui_font(10))
        reset_session_button.clicked.connect(self._on_reset_session)
        control_layout.addWidget(reset_session_button)
        
        reset_windows_button = QPushButton("Reset Windows")
        reset_windows_button.setFont(self._fonts.get_ui_font(10))
        reset_windows_button.clicked.connect(self._on_reset_windows)
        control_layout.addWidget(reset_windows_button)
        
        set_all_sizes_button = QPushButton("Set All Window Sizes")
        set_all_sizes_button.setFont(self._fonts.get_ui_font(10))
        set_all_sizes_button.setToolTip("Resize all log viewer windows to the default size")
        set_all_sizes_button.clicked.connect(self._on_set_all_window_sizes)
        control_layout.addWidget(set_all_sizes_button)
        
        layout.addWidget(control_frame)
        
        # Groups section
        groups_frame = QFrame()
        groups_frame.setFrameShape(QFrame.Shape.StyledPanel)
        groups_layout = QVBoxLayout(groups_frame)
        
        groups_header_layout = QHBoxLayout()
        groups_label = QLabel("Log Groups:")
        groups_label.setFont(self._fonts.get_ui_font(11, bold=True))
        groups_header_layout.addWidget(groups_label)
        
        add_group_button = QPushButton("+ Add Group")
        add_group_button.setFont(self._fonts.get_ui_font(9))
        add_group_button.clicked.connect(self._on_add_group)
        groups_header_layout.addWidget(add_group_button)
        groups_header_layout.addStretch()
        
        groups_layout.addLayout(groups_header_layout)
        
        self.groups_list = QListWidget()
        self.groups_list.setMaximumHeight(100)
        self.groups_list.itemDoubleClicked.connect(self._on_group_double_clicked)
        groups_layout.addWidget(self.groups_list)
        
        layout.addWidget(groups_frame)
        
        # Tracked Logs section
        logs_label = QLabel("Tracked Logs:")
        logs_label.setFont(self._fonts.get_ui_font(11, bold=True))
        layout.addWidget(logs_label)
        
        # Log list with custom item widgets
        self.log_list = QListWidget()
        self.log_list.itemDoubleClicked.connect(self._on_log_double_clicked)
        layout.addWidget(self.log_list)
        
    def _add_log_to_list(self, path_key: str, is_wildcard: bool = False) -> None:
        """Add a log file to the list with custom widget.
        
        Args:
            path_key: Full path or pattern
            is_wildcard: Whether this is a wildcard pattern
        """
        # Create list item
        item = QListWidgetItem(self.log_list)
        
        # Create custom widget for the item
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)
        
        # Display name (just filename)
        if is_wildcard:
            display_name = f"🔍 {Path(path_key).name}"
        else:
            display_name = Path(path_key).name
        
        name_label = QLabel(display_name)
        name_label.setFont(self._fonts.get_ui_font(10))
        name_label.setToolTip(path_key)  # Show full path on hover
        layout.addWidget(name_label)
        
        # Group selector
        group_combo = QComboBox()
        group_combo.setFont(self._fonts.get_ui_font(9))
        group_combo.setMaximumWidth(120)
        group_combo.addItem("(no group)")
        for group_name in self._available_groups:
            group_combo.addItem(group_name)
        
        # Set current group if assigned
        current_group = self._log_groups.get(path_key)
        if current_group:
            index = group_combo.findText(current_group)
            if index >= 0:
                group_combo.setCurrentIndex(index)
        
        layout.addWidget(group_combo)
        
        # Add to group button
        add_to_group_btn = QPushButton("→")
        add_to_group_btn.setFont(self._fonts.get_ui_font(9))
        add_to_group_btn.setToolTip("Add to selected group")
        add_to_group_btn.setMaximumWidth(30)
        add_to_group_btn.clicked.connect(lambda: self._on_assign_to_group(path_key, group_combo.currentText()))
        layout.addWidget(add_to_group_btn)
        
        layout.addStretch()
        
        # Refresh button
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFont(self._fonts.get_ui_font(9))
        refresh_btn.setToolTip("Refresh log (clear and restart)")
        refresh_btn.setMaximumWidth(30)
        refresh_btn.clicked.connect(lambda: self._on_refresh_log(path_key))
        layout.addWidget(refresh_btn)
        
        # Unregister/Close button
        close_btn = QPushButton("✖")
        close_btn.setFont(self._fonts.get_ui_font(9))
        close_btn.setToolTip("Unregister and close log")
        close_btn.setMaximumWidth(30)
        close_btn.clicked.connect(lambda: self._on_unregister_log(path_key))
        layout.addWidget(close_btn)
        
        # Set the custom widget
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.ItemDataRole.UserRole, path_key)  # Store full path in item data
        self.log_list.addItem(item)
        self.log_list.setItemWidget(item, widget)
    
    def _on_add_log(self) -> None:
        """Handle add log button click."""
        path_str = self.path_input.text().strip()
        if not path_str:
            return
        
        try:
            # Check if pattern contains wildcards
            is_wildcard = '*' in path_str or '?' in path_str
            
            if is_wildcard:
                # Use pattern as-is for wildcard watching
                path_key = path_str
                
                # Check if already tracking
                if path_key in self._watchers:
                    QMessageBox.warning(
                        self,
                        "Already Tracking",
                        f"Already tracking pattern: {path_key}",
                    )
                    return
                
                # Validate parent directory exists
                pattern_path = Path(path_str)
                if not pattern_path.parent.exists():
                    raise InvalidPathError(f"Parent directory does not exist: {pattern_path.parent}")
                
                # Add to list with wildcard indicator
                self._add_log_to_list(path_key, is_wildcard=True)
                
                # Register with log manager
                self._log_manager.register_log(path_key)
                
                # Start wildcard watcher
                self._start_wildcard_watcher(path_key, path_str)
                
                # Save to settings
                self._settings.add_tracked_log(path_key)
                logger.info(f"Added wildcard pattern to session: {path_key}")
                
            else:
                # Regular file watching
                file_path = Path(path_str)
                path_key = str(file_path)
                
                # Check if already tracking
                if path_key in self._watchers:
                    QMessageBox.warning(
                        self,
                        "Already Tracking",
                        f"Already tracking: {path_key}",
                    )
                    return
                
                # Validate path
                if not file_path.parent.exists():
                    raise InvalidPathError(f"Parent directory does not exist: {file_path.parent}")
                    
                # Check read permissions (if file exists)
                if file_path.exists() and not os.access(file_path, os.R_OK):
                    raise FileAccessError(f"Cannot read file: {file_path}")
                    
                # Add to list
                self._add_log_to_list(path_key, is_wildcard=False)
                
                # Register with log manager
                self._log_manager.register_log(path_key)
                
                # Start watcher thread
                self._start_watcher(path_key, file_path)
                
                # Save to settings
                self._settings.add_tracked_log(path_key)
                logger.info(f"Added log to session: {path_key}")
            
            # Clear input
            self.path_input.clear()
            
        except (InvalidPathError, FileAccessError) as e:
            QMessageBox.critical(
                self,
                "Error Adding Log",
                str(e),
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Unexpected Error",
                f"Failed to add log file:\n{e}",
            )
            
    def _on_refresh_log(self, path_key: str) -> None:
        """Refresh a log file (clear and restart).
        
        Args:
            path_key: Path key identifying the log file
        """
        logger.info(f"Refreshing log: {path_key}")
        
        # Clear the buffer
        self._log_manager.clear_buffer(path_key)
        
        # Close viewer window if open
        if path_key in self._viewer_windows:
            viewer = self._viewer_windows[path_key]
            viewer.close()
        
        # Restart the watcher
        if path_key in self._watchers:
            watcher = self._watchers[path_key]
            watcher.stop()
            watcher.wait()  # Wait for thread to finish
            
            # Start new watcher
            is_wildcard = '*' in path_key or '?' in path_key
            if is_wildcard:
                self._start_wildcard_watcher(path_key, path_key)
            else:
                self._start_watcher(path_key, Path(path_key))
        
        logger.info(f"Refreshed log: {path_key}")
    
    def _on_add_group(self) -> None:
        """Handle adding a new group."""
        group_name, ok = QInputDialog.getText(
            self,
            "Add Group",
            "Enter group name:",
            QLineEdit.EchoMode.Normal
        )
        
        if not ok or not group_name.strip():
            return
        
        group_name = group_name.strip()
        
        if group_name in self._available_groups:
            QMessageBox.warning(self, "Duplicate Group", f"Group '{group_name}' already exists.")
            return
        
        self._available_groups.append(group_name)
        self._add_group_to_list(group_name)
        self._refresh_all_log_items()
        self._save_groups()
        logger.info(f"Added group: {group_name}")
    
    def _add_group_to_list(self, group_name: str) -> None:
        """Add a group to the groups list.
        
        Args:
            group_name: Name of the group
        """
        item = QListWidgetItem(self.groups_list)
        
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)
        
        name_label = QLabel(f"📁 {group_name}")
        name_label.setFont(self._fonts.get_ui_font(10, bold=True))
        layout.addWidget(name_label)
        
        layout.addStretch()
        
        # Show/Hide button
        show_btn = QPushButton("Show")
        show_btn.setFont(self._fonts.get_ui_font(9))
        show_btn.setMaximumWidth(50)
        show_btn.clicked.connect(lambda: self._on_show_group(group_name))
        layout.addWidget(show_btn)
        
        # Remove button
        remove_btn = QPushButton("✖")
        remove_btn.setFont(self._fonts.get_ui_font(9))
        remove_btn.setToolTip("Remove group")
        remove_btn.setMaximumWidth(30)
        remove_btn.clicked.connect(lambda: self._on_remove_group(group_name))
        layout.addWidget(remove_btn)
        
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.ItemDataRole.UserRole, group_name)
        self.groups_list.addItem(item)
        self.groups_list.setItemWidget(item, widget)
    
    def _on_remove_group(self, group_name: str) -> None:
        """Handle removing a group.
        
        Args:
            group_name: Name of the group to remove
        """
        # Check if any logs are assigned to this group
        assigned_logs = [path for path, group in self._log_groups.items() if group == group_name]
        
        if assigned_logs:
            reply = QMessageBox.question(
                self,
                "Remove Group",
                f"Group '{group_name}' has {len(assigned_logs)} log(s) assigned.\n"
                f"Remove group and unassign all logs?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # Unassign all logs
            for path in assigned_logs:
                self._unassign_from_group(path)
        
        # Close group window if open
        if group_name in self._group_windows:
            self._group_windows[group_name].close()
            del self._group_windows[group_name]
        
        # Remove from available groups
        self._available_groups.remove(group_name)
        
        # Remove from list
        for i in range(self.groups_list.count()):
            item = self.groups_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == group_name:
                self.groups_list.takeItem(i)
                break
        
        self._refresh_all_log_items()
        self._save_groups()
        logger.info(f"Removed group: {group_name}")
    
    def _on_show_group(self, group_name: str) -> None:
        """Show or create a group window.
        
        Args:
            group_name: Name of the group
        """
        if group_name in self._group_windows:
            # Window exists, show and raise it
            window = self._group_windows[group_name]
            window.show()
            window.raise_()
            window.activateWindow()
        else:
            # Create new group window
            self._create_group_window(group_name)
    
    def _on_group_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on a group.
        
        Args:
            item: List item that was double-clicked
        """
        group_name = item.data(Qt.ItemDataRole.UserRole)
        self._on_show_group(group_name)
    
    def _on_log_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on log item to open viewer window or show group.
        
        Args:
            item: List item that was double-clicked
        """
        path_key = item.data(Qt.ItemDataRole.UserRole)
        
        # Check if log is in a group
        if path_key in self._log_groups:
            group_name = self._log_groups[path_key]
            # Show/flash the group window
            self._on_show_group(group_name)
            logger.info(f"Showing group window for grouped log: {path_key}")
        else:
            # Open individual viewer
            self._open_log_viewer(path_key)
    
    def _create_group_window(self, group_name: str) -> None:
        """Create a group window.
        
        Args:
            group_name: Name of the group
        """
        group_window = LogGroupWindow(group_name)
        group_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        group_window.destroyed.connect(lambda: self._on_group_window_closed(group_name))
        
        # Set callbacks
        group_window.set_position_changed_callback(
            lambda x, y, w, h: self._on_window_position_changed(group_name, x, y, w, h)
        )
        group_window.set_default_size_callback(
            lambda w, h: self._settings.set_default_window_size(w, h)
        )
        group_window.set_other_windows_callback(
            lambda: list(self._viewer_windows.values()) + [gw for gw in self._group_windows.values() if gw != group_window]
        )
        
        # Restore position if saved
        pos = self._settings.get_window_position(group_name)
        if pos:
            group_window.move(pos["x"], pos["y"])
            group_window.resize(pos["width"], pos["height"])
            logger.info(f"Restored group window position for: {group_name}")
        else:
            # Apply default size
            default_width, default_height = self._settings.get_default_window_size()
            group_window.resize(default_width, default_height)
        
        # Add all logs assigned to this group
        for path, group in self._log_groups.items():
            if group == group_name:
                group_window.add_log(path)
                self._log_manager.subscribe(path, group_window)
        
        self._group_windows[group_name] = group_window
        group_window.show()
        logger.info(f"Created group window: {group_name}")
    
    def _refresh_all_log_items(self) -> None:
        """Refresh all log list items to update group dropdowns."""
        # Store current items
        items_data = []
        for i in range(self.log_list.count()):
            item = self.log_list.item(i)
            path_key = item.data(Qt.ItemDataRole.UserRole)
            items_data.append(path_key)
        
        # Clear and recreate
        self.log_list.clear()
        for path_key in items_data:
            is_wildcard = '*' in path_key or '?' in path_key
            self._add_log_to_list(path_key, is_wildcard)
    
    def _on_assign_to_group(self, path_key: str, group_selection: str) -> None:
        """Handle assigning a log to a group.
        
        Args:
            path_key: Path key identifying the log file
            group_selection: Selected group from combo box
        """
        if group_selection == "(no group)":
            # Unassign from group
            self._unassign_from_group(path_key)
        else:
            # Assign to group
            self._assign_to_group(path_key, group_selection)
    
    def _assign_to_group(self, path_key: str, group_name: str) -> None:
        """Assign a log to a group.
        
        Args:
            path_key: Path key identifying the log file
            group_name: Group name
        """
        old_group = self._log_groups.get(path_key)
        
        if old_group == group_name:
            return
        
        logger.info(f"Assigning {path_key} to group: {group_name}")
        
        # Remove from old group
        if old_group:
            self._unassign_from_group(path_key)
        
        # Close individual viewer window if open
        if path_key in self._viewer_windows:
            self._viewer_windows[path_key].close()
            del self._viewer_windows[path_key]
        
        # Update assignment
        self._log_groups[path_key] = group_name
        
        # Add to group window if it exists
        if group_name in self._group_windows:
            self._group_windows[group_name].add_log(path_key)
            self._log_manager.subscribe(path_key, self._group_windows[group_name])
        
        self._save_groups()
    
    def _unassign_from_group(self, path_key: str) -> None:
        """Unassign a log from its group.
        
        Args:
            path_key: Path key identifying the log file
        """
        if path_key not in self._log_groups:
            return
        
        group_name = self._log_groups[path_key]
        logger.info(f"Unassigning {path_key} from group: {group_name}")
        
        # Remove from group window
        if group_name in self._group_windows:
            self._group_windows[group_name].remove_log(path_key)
            self._log_manager.unsubscribe(path_key, self._group_windows[group_name])
        
        # Remove assignment
        del self._log_groups[path_key]
        self._save_groups()
    
    def _on_viewer_window_closed(self, path_key: str) -> None:
        """Handle viewer window being closed.
        
        Args:
            path_key: Path key identifying the log file
        """
        if path_key in self._viewer_windows:
            # Unsubscribe from log manager
            viewer = self._viewer_windows[path_key]
            self._log_manager.unsubscribe(path_key, viewer)
            del self._viewer_windows[path_key]
            logger.info(f"Viewer window closed and unsubscribed: {path_key}")
            self._save_open_windows()
    
    def _on_group_window_closed(self, group_name: str) -> None:
        """Handle group window being closed.
        
        Args:
            group_name: Name of the group that was closed
        """
        if group_name in self._group_windows:
            del self._group_windows[group_name]
            logger.info(f"Group window closed: {group_name}")
    
    def _on_unregister_log(self, path_key: str) -> None:
        """Unregister and close a log file.
        
        Args:
            path_key: Path key identifying the log file
        """
        logger.info(f"Unregistering log: {path_key}")
        
        # Stop watcher
        if path_key in self._watchers:
            watcher = self._watchers[path_key]
            watcher.stop()
            watcher.wait()
            del self._watchers[path_key]
        
        # Close viewer window
        if path_key in self._viewer_windows:
            viewer = self._viewer_windows[path_key]
            viewer.close()
            # Window will be removed from dict by the destroyed signal
        
        # Unregister from log manager
        self._log_manager.unregister_log(path_key)
        
        # Remove from settings
        self._settings.remove_tracked_log(path_key)
        
        # Remove from list
        for i in range(self.log_list.count()):
            item = self.log_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == path_key:
                self.log_list.takeItem(i)
                break
        
        logger.info(f"Unregistered log: {path_key}")
    
    def _open_log_viewer(self, path_key: str, restore_position: bool = False) -> None:
        """Open a log viewer window for the given path.
        
        Args:
            path_key: Path key identifying the log file
            restore_position: Whether to restore saved window position
        """
        # Check if log is in a group - if so, show group window instead
        if path_key in self._log_groups:
            group_name = self._log_groups[path_key]
            logger.info(f"Log {path_key} is in group {group_name}, showing group window instead")
            self._on_show_group(group_name)
            return
        
        logger.info(f"Opening log viewer for: {path_key}")
        
        # Check if window already exists
        if path_key in self._viewer_windows:
            window = self._viewer_windows[path_key]
            window.raise_()
            window.activateWindow()
            # Flash the window to get user's attention
            window.flash_window()
            logger.info(f"Flashed existing window for: {path_key}")
            return
            
        # Create new viewer window
        viewer = LogViewerWindow(path_key)
        viewer.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        viewer.destroyed.connect(lambda: self._on_viewer_window_closed(path_key))
        
        # Connect watcher pause/resume to content controller pause callback
        if path_key in self._watchers:
            watcher = self._watchers[path_key]
            viewer.set_pause_callback(
                lambda paused: watcher.pause() if paused else watcher.resume()
            )
        
        # Restore position if requested
        if restore_position:
            pos = self._settings.get_window_position(path_key)
            if pos:
                viewer.move(pos["x"], pos["y"])
                viewer.resize(pos["width"], pos["height"])
                logger.info(f"Restored window position for: {path_key}")
            
        # Set callbacks
        viewer.set_position_changed_callback(
            lambda x, y, w, h: self._on_window_position_changed(path_key, x, y, w, h)
        )
        viewer.set_default_size_callback(
            lambda w, h: self._settings.set_default_window_size(w, h)
        )
        viewer.set_other_windows_callback(
            lambda: [v for v in self._viewer_windows.values() if v != viewer]
        )
        
        # Apply default size if not restoring position
        if not restore_position:
            default_width, default_height = self._settings.get_default_window_size()
            viewer.resize(default_width, default_height)
        
        # Subscribe to log manager
        logger.info(f"Subscribing viewer to log manager for: {path_key}")
        self._log_manager.subscribe(path_key, viewer)
        logger.info(f"Subscription complete for: {path_key}")
            
        viewer.show()
        self._viewer_windows[path_key] = viewer
        
        # Update open windows list
        self._save_open_windows()
        
    def _on_content_available_for_auto_open(self, path_key: str, content: str) -> None:
        """Handle content available signal for auto-opening windows.
        
        Args:
            path_key: Path key identifying the log file
            content: Content (not used, just need to know content exists)
        """
        if path_key in self._pending_window_opens:
            # Check if buffer has content
            buffer_content = self._log_manager.get_buffer_content(path_key)
            if buffer_content:
                logger.info(f"Auto-opening window for {path_key} (buffer has content)")
                self._pending_window_opens.remove(path_key)
                self._open_log_viewer(path_key, restore_position=True)
    
    def _on_new_lines(self, path_key: str, text: str) -> None:
        """Handle new lines from a watcher thread (for UI feedback).
        
        Note: Content is now published via LogManager to subscribers.
        This handler is kept for potential UI status updates.
        
        Args:
            path_key: Path key identifying the log file
            text: New text content
        """
        # Content is handled by LogManager -> subscribers
        pass
            
    def _on_file_created(self, path_key: str) -> None:
        """Handle file creation event.
        
        Args:
            path_key: Path key identifying the log file
        """
        viewer = self._viewer_windows.get(path_key)
        if viewer:
            viewer.set_status_message("File created, starting tail...")
            
    def _on_file_deleted(self, path_key: str) -> None:
        """Handle file deletion event.
        
        Args:
            path_key: Path key identifying the log file
        """
        viewer = self._viewer_windows.get(path_key)
        if viewer:
            viewer.set_status_message("File deleted, watching for recreation...")
    
    def _on_file_switched(self, path_key: str, old_path: str, new_path: str) -> None:
        """Handle wildcard watcher switching to a new file.
        
        Args:
            path_key: Path key identifying the pattern
            old_path: Previous file path
            new_path: New file path
        """
        logger.info(f"File switched for {path_key}: {old_path} -> {new_path}")
        # Stream lifecycle events are handled by WildcardFileWatcher
    
    def _on_watcher_error(self, path_key: str, error: str) -> None:
        """Handle watcher thread error.
        
        Args:
            path_key: Path key identifying the log file
            error: Error message
        """
        QMessageBox.critical(
            self,
            "Watcher Error",
            f"Error watching {path_key}:\n{error}",
        )
        
    def _on_window_position_changed(self, path_key: str, x: int, y: int, width: int, height: int) -> None:
        """Handle window position/size change.
        
        Args:
            path_key: Path key identifying the log file
            x: X position
            y: Y position
            width: Window width
            height: Window height
        """
        self._settings.set_window_position(path_key, x, y, width, height)
        logger.debug(f"Updated window position for {path_key}: ({x}, {y}) {width}x{height}")
    
    def _on_viewer_closed(self, path_key: str) -> None:
        """Handle viewer window being closed.
        
        Args:
            path_key: Path key identifying the log file
        """
        if path_key in self._viewer_windows:
            viewer = self._viewer_windows[path_key]
            # Unsubscribe from log manager
            self._log_manager.unsubscribe(path_key, viewer)
            logger.info(f"Unsubscribed viewer from log manager: {path_key}")
            del self._viewer_windows[path_key]
            
        # Update open windows list
        self._save_open_windows()
            
    def _start_watcher(self, path_key: str, file_path: Path) -> None:
        """Start a watcher thread for a log file.
        
        Args:
            path_key: Path key identifying the log file
            file_path: Path object for the log file
        """
        watcher = FileWatcherThread(file_path, self._log_manager, path_key)
        watcher.new_lines.connect(lambda text: self._on_new_lines(path_key, text))
        watcher.file_created.connect(lambda: self._on_file_created(path_key))
        watcher.file_deleted.connect(lambda: self._on_file_deleted(path_key))
        watcher.error_occurred.connect(lambda err: self._on_watcher_error(path_key, err))
        watcher.start()
        
        self._watchers[path_key] = watcher
    
    def _start_wildcard_watcher(self, path_key: str, pattern: str) -> None:
        """Start a wildcard watcher thread for a glob pattern.
        
        Args:
            path_key: Path key identifying the pattern
            pattern: Glob pattern (e.g., "C:/logs/Cook-*.txt")
        """
        watcher = WildcardFileWatcher(pattern, self._log_manager, path_key)
        watcher.new_lines.connect(lambda text: self._on_new_lines(path_key, text))
        watcher.file_switched.connect(lambda old, new: self._on_file_switched(path_key, old, new))
        watcher.error_occurred.connect(lambda err: self._on_watcher_error(path_key, err))
        watcher.start()
        
        self._watchers[path_key] = watcher
        logger.info(f"Started wildcard watcher for pattern: {pattern}")
        
    def _save_open_windows(self) -> None:
        """Save list of currently open viewer windows."""
        open_paths = list(self._viewer_windows.keys())
        self._settings.set_open_windows(open_paths)
    
    def _save_groups(self) -> None:
        """Save groups and log-to-group assignments."""
        self._settings.set_groups(self._available_groups)
        self._settings.set_log_groups(self._log_groups)
        
    def _restore_session(self) -> None:
        """Restore tracked logs and groups from previous session."""
        # Restore groups first
        saved_groups = self._settings.get_groups()
        self._available_groups = saved_groups.copy()
        for group_name in saved_groups:
            self._add_group_to_list(group_name)
        logger.info(f"Restored {len(saved_groups)} groups")
        
        # Restore log-to-group assignments
        self._log_groups = self._settings.get_log_groups().copy()
        
        tracked_logs = self._settings.get_tracked_logs()
        logger.info(f"Restoring {len(tracked_logs)} logs from previous session")
        
        for path_str in tracked_logs:
            try:
                # Check if it's a wildcard pattern
                is_wildcard = '*' in path_str or '?' in path_str
                
                if is_wildcard:
                    # Restore wildcard pattern
                    pattern_path = Path(path_str)
                    if not pattern_path.parent.exists():
                        logger.warning(f"Skipping pattern (parent dir missing): {path_str}")
                        continue
                    
                    # Add to list with wildcard indicator
                    self._add_log_to_list(path_str, is_wildcard=True)
                    
                    # Register with log manager
                    self._log_manager.register_log(path_str)
                    
                    # Start wildcard watcher
                    self._start_wildcard_watcher(path_str, path_str)
                    logger.info(f"Restored wildcard pattern: {path_str}")
                    
                else:
                    # Restore regular file
                    file_path = Path(path_str)
                    
                    # Check parent directory exists
                    if not file_path.parent.exists():
                        logger.warning(f"Skipping log (parent dir missing): {path_str}")
                        continue
                    
                    # Add to list
                    self._add_log_to_list(path_str, is_wildcard=False)
                    
                    # Register with log manager
                    self._log_manager.register_log(path_str)
                    
                    # Start watcher
                    self._start_watcher(path_str, file_path)
                    logger.info(f"Restored log: {path_str}")
                
            except Exception as e:
                logger.error(f"Failed to restore log {path_str}: {e}")
                
        # Mark ALL tracked logs for auto-opening once content is available
        # This ensures windows open automatically when the app starts
        logger.info(f"Marking {len(tracked_logs)} windows for auto-open")
        
        for path_str in tracked_logs:
            self._pending_window_opens.add(path_str)
            logger.info(f"Will auto-open window for: {path_str}")
    
    def _on_reset_session(self) -> None:
        """Handle reset session button click."""
        # Stop all watchers
        for watcher in self._watchers.values():
            watcher.stop()
            watcher.wait()
            
        # Close all viewer windows
        for viewer in list(self._viewer_windows.values()):
            viewer.close()
            
        # Unregister all logs from log manager
        for path_key in list(self._watchers.keys()):
            self._log_manager.unregister_log(path_key)
            
        # Clear data structures
        self._watchers.clear()
        self._viewer_windows.clear()
        self.log_list.clear()
        
        # Clear settings
        self._settings.clear_tracked_logs()
        logger.info("Session reset")
        
    def _on_set_all_window_sizes(self) -> None:
        """Set all log viewer and group windows to the default size."""
        default_width, default_height = self._settings.get_default_window_size()
        
        count = 0
        for viewer in self._viewer_windows.values():
            viewer.resize(default_width, default_height)
            count += 1
        
        for group_window in self._group_windows.values():
            group_window.resize(default_width, default_height)
            count += 1
        
        logger.info(f"Resized {count} windows to {default_width}x{default_height}")
    
    def _on_reset_windows(self) -> None:
        """Handle reset windows button click - cascade all viewer and group windows."""
        if not self._viewer_windows and not self._group_windows:
            return
            
        # Get main window position
        main_pos = self.pos()
        offset_x = main_pos.x() + 50
        offset_y = main_pos.y() + 50
        
        # Cascade all windows (viewers + groups)
        all_windows = list(self._viewer_windows.values()) + list(self._group_windows.values())
        for i, window in enumerate(all_windows):
            window.move(offset_x + (i * 30), offset_y + (i * 30))
            window.resize(800, 600)
            
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter event.
        
        Args:
            event: Drag enter event
        """
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop event.
        
        Args:
            event: Drop event
        """
        urls = event.mimeData().urls()
        if not urls:
            return
        
        for url in urls:
            file_path = url.toLocalFile()
            if not file_path:
                continue
            
            # Check if it's a file (not directory)
            path_obj = Path(file_path)
            if not path_obj.is_file():
                QMessageBox.warning(
                    self,
                    "Invalid Drop",
                    f"Only files can be tracked, not directories:\n{file_path}"
                )
                continue
            
            # Show tracking mode dialog
            dialog = TrackingModeDialog(file_path, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._add_log_from_dialog(dialog)
        
        event.acceptProposedAction()
    
    def _add_log_from_dialog(self, dialog: TrackingModeDialog) -> None:
        """Add a log file based on dialog selection.
        
        Args:
            dialog: Tracking mode dialog with user selections
        """
        try:
            if dialog.tracking_mode == "wildcard":
                path_key = dialog.wildcard_pattern
                
                # Check if already tracking
                if path_key in self._watchers:
                    QMessageBox.information(
                        self,
                        "Already Tracking",
                        f"Already tracking pattern: {path_key}",
                    )
                    return
                
                # Validate parent directory exists
                pattern_path = Path(path_key)
                if not pattern_path.parent.exists():
                    raise InvalidPathError(f"Parent directory does not exist: {pattern_path.parent}")
                
                # Add to list
                self._add_log_to_list(path_key, is_wildcard=True)
                
                # Register with log manager
                self._log_manager.register_log(path_key)
                
                # Start wildcard watcher
                self._start_wildcard_watcher(path_key, path_key)
                
                # Save to settings
                self._settings.add_tracked_log(path_key)
                logger.info(f"Added wildcard pattern via drag-drop: {path_key}")
                
            else:  # dedicated
                path_key = dialog.file_path
                file_path = Path(path_key)
                
                # Check if already tracking
                if path_key in self._watchers:
                    QMessageBox.information(
                        self,
                        "Already Tracking",
                        f"Already tracking: {file_path.name}",
                    )
                    return
                
                # Validate path
                if not file_path.parent.exists():
                    raise InvalidPathError(f"Parent directory does not exist: {file_path.parent}")
                
                # Check read permissions (if file exists)
                if file_path.exists() and not os.access(file_path, os.R_OK):
                    raise FileAccessError(f"Cannot read file: {file_path}")
                
                # Add to list
                self._add_log_to_list(path_key, is_wildcard=False)
                
                # Register with log manager
                self._log_manager.register_log(path_key)
                
                # Start watcher thread
                self._start_watcher(path_key, file_path)
                
                # Save to settings
                self._settings.add_tracked_log(path_key)
                logger.info(f"Added log via drag-drop: {path_key}")
                
        except (InvalidPathError, FileAccessError) as e:
            QMessageBox.warning(
                self,
                "Error Adding Log",
                str(e),
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Unexpected Error",
                f"Failed to add log file:\n{e}",
            )
    
    def closeEvent(self, event) -> None:
        """Handle window close event.
        
        Args:
            event: Close event
        """
        # Stop all watchers
        for watcher in self._watchers.values():
            watcher.stop()
            
        # Close all viewer windows
        for viewer in list(self._viewer_windows.values()):
            viewer.close()
        
        # Close all group windows
        for group_window in list(self._group_windows.values()):
            group_window.close()
            
        event.accept()
