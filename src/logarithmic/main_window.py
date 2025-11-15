"""Main Control Window - manages log tracking and viewer windows."""

import logging
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtGui import QDragEnterEvent
from PySide6.QtGui import QDropEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QFrame
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QInputDialog
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QListWidget
from PySide6.QtWidgets import QListWidgetItem
from PySide6.QtWidgets import QMainWindow
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QRadioButton
from PySide6.QtWidgets import QSpinBox
from PySide6.QtWidgets import QTabWidget
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from logarithmic.exceptions import FileAccessError
from logarithmic.exceptions import InvalidPathError
from logarithmic.file_watcher import FileWatcherThread
from logarithmic.fonts import get_font_manager
from logarithmic.k8s_selector_dialog import K8sSelectorDialog
from logarithmic.log_group_window import LogGroupWindow
from logarithmic.log_manager import LogManager
from logarithmic.log_viewer_window import LogViewerWindow
from logarithmic.mcp_bridge import McpBridge
from logarithmic.mcp_server import LogarithmicMcpServer
from logarithmic.providers import FileProvider
from logarithmic.providers import LogProvider
from logarithmic.providers import ProviderConfig
from logarithmic.providers import ProviderMode
from logarithmic.providers import ProviderRegistry
from logarithmic.providers import ProviderType
from logarithmic.settings import Settings
from logarithmic.shutdown_dialog import ShutdownDialog
from logarithmic.wildcard_watcher import WildcardFileWatcher

logger = logging.getLogger(__name__)


class TrackingModeDialog(QDialog):
    """Dialog to select tracking mode for a log file or folder."""

    def __init__(self, path: str, is_folder: bool = False, parent=None):
        """Initialize the dialog.

        Args:
            path: Path to the log file or folder
            is_folder: True if path is a folder, False if it's a file
            parent: Parent widget
        """
        super().__init__(parent)
        self.path = path
        self.is_folder = is_folder
        self.tracking_mode = "wildcard" if is_folder else "dedicated"  # Default
        self.wildcard_pattern = ""

        # Type hints for optional radio buttons (None when is_folder=True)
        self.dedicated_radio: QRadioButton | None = None
        self.wildcard_radio: QRadioButton | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Select Tracking Mode")
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Path info
        path_obj = Path(self.path)
        if self.is_folder:
            item_label = QLabel(f"Folder: {path_obj.name}")
        else:
            item_label = QLabel(f"File: {path_obj.name}")
        item_label.setWordWrap(True)
        item_label.setToolTip(self.path)
        layout.addWidget(item_label)

        path_label = QLabel(f"Path: {self.path}")
        path_label.setWordWrap(True)
        path_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(path_label)

        layout.addSpacing(10)

        # Radio buttons - only show dedicated option for files
        if not self.is_folder:
            self.dedicated_radio = QRadioButton("Dedicated - Track this specific file")
            self.dedicated_radio.setChecked(True)
            self.dedicated_radio.toggled.connect(self._on_mode_changed)
            layout.addWidget(self.dedicated_radio)

            self.wildcard_radio = QRadioButton(
                "Wildcard - Track files matching a pattern in this folder"
            )
            self.wildcard_radio.toggled.connect(self._on_mode_changed)
            layout.addWidget(self.wildcard_radio)
        else:
            # For folders, only wildcard mode is available
            self.dedicated_radio = None
            self.wildcard_radio = None
            mode_label = QLabel("Track files matching a pattern in this folder:")
            mode_label.setFont(mode_label.font())
            layout.addWidget(mode_label)

        # Wildcard pattern input
        wildcard_layout = QHBoxLayout()
        if not self.is_folder:
            wildcard_layout.addSpacing(20)
        wildcard_label = QLabel("Pattern:")
        wildcard_layout.addWidget(wildcard_label)

        self.wildcard_input = QLineEdit()
        self.wildcard_input.setPlaceholderText("e.g., *.log or app-*.txt")
        self.wildcard_input.setEnabled(self.is_folder)  # Always enabled for folders
        wildcard_layout.addWidget(self.wildcard_input)
        layout.addLayout(wildcard_layout)

        # Help text
        if self.is_folder:
            help_text = QLabel(
                "Wildcard patterns use * for any characters (e.g., *.log, app-*.txt)\n"
                "All matching files in the selected folder will be tracked."
            )
        else:
            help_text = QLabel(
                "Wildcard patterns use * for any characters (e.g., Log-*.txt)"
            )
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
        if self.wildcard_radio and self.wildcard_radio.isChecked():
            self.wildcard_input.setEnabled(True)
            # Pre-fill with filename as template
            filename = Path(self.path).name
            # Replace date/time patterns with wildcards
            import re

            pattern = re.sub(r"\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}", "*", filename)
            pattern = re.sub(r"\d{8}-\d{6}", "*", pattern)
            pattern = re.sub(r"\d+", "*", pattern)
            self.wildcard_input.setText(pattern)
            self.wildcard_input.setFocus()
            self.wildcard_input.selectAll()
        else:
            self.wildcard_input.setEnabled(False)

    def _on_accept(self) -> None:
        """Handle OK button click."""
        # For folders or when wildcard mode is selected
        if self.is_folder or (self.wildcard_radio and self.wildcard_radio.isChecked()):
            pattern = self.wildcard_input.text().strip()
            if not pattern:
                QMessageBox.warning(
                    self, "Invalid Pattern", "Please enter a wildcard pattern."
                )
                return

            if "*" not in pattern and "?" not in pattern:
                QMessageBox.warning(
                    self,
                    "Invalid Pattern",
                    "Wildcard pattern must contain * or ? characters.",
                )
                return

            self.tracking_mode = "wildcard"
            # Build full pattern with directory
            if self.is_folder:
                folder_dir = Path(self.path)
            else:
                folder_dir = Path(self.path).parent
            self.wildcard_pattern = str(folder_dir / pattern)
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

        # Provider registry
        self._provider_registry = ProviderRegistry.get_instance()

        # Track active watchers/providers and viewer windows
        self._watchers: dict[
            str, FileWatcherThread | WildcardFileWatcher
        ] = {}  # Legacy watchers (for backward compat)
        self._providers: dict[str, LogProvider] = {}  # New provider-based system
        self._viewer_windows: dict[str, LogViewerWindow] = {}
        self._group_windows: dict[str, LogGroupWindow] = {}  # group_name -> window
        self._log_groups: dict[str, str] = {}  # path_key -> group_name
        self._available_groups: list[str] = []  # List of group names

        # Track provider configs for session persistence
        self._provider_configs: dict[str, ProviderConfig] = {}  # path_key -> config

        # Track which windows should auto-open after content loads
        self._pending_window_opens: set[str] = set()

        # Settings manager
        self._settings = Settings()

        # MCP Server components
        self._mcp_bridge: McpBridge | None = None
        self._mcp_server: LogarithmicMcpServer | None = None

        # Store references to UI elements for dynamic font sizing
        self._ui_elements: list[QWidget] = []

        # Track main window position changes
        self._last_main_position: tuple[int, int, int, int] | None = None

        # Connect to log manager signals for auto-opening windows
        self._log_manager.log_content_available.connect(
            self._on_content_available_for_auto_open
        )

        self._setup_ui()
        self._restore_session()
        self._initialize_mcp_server()
        self._restore_main_window_position()
        self._load_font_sizes()

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

        # Provider type selector
        self.provider_combo = QComboBox()
        self.provider_combo.setFont(self._fonts.get_ui_font(10))
        self.provider_combo.setMinimumWidth(120)
        self.provider_combo.setToolTip("Select log source type")
        self._populate_provider_combo()
        self.provider_combo.currentIndexChanged.connect(self._on_provider_type_changed)
        control_layout.addWidget(self.provider_combo)
        self._ui_elements.append(self.provider_combo)

        # Browse buttons for file/folder selection (Apple sandboxing compliant)
        self.browse_file_button = QPushButton("📄 Browse File")
        self.browse_file_button.setFont(self._fonts.get_ui_font(10))
        self.browse_file_button.setToolTip("Select a log file to track")
        self.browse_file_button.clicked.connect(self._on_browse_file)
        control_layout.addWidget(self.browse_file_button)
        self._ui_elements.append(self.browse_file_button)

        self.browse_folder_button = QPushButton("📁 Browse Folder")
        self.browse_folder_button.setFont(self._fonts.get_ui_font(10))
        self.browse_folder_button.setToolTip(
            "Select a folder to track files with wildcard pattern"
        )
        self.browse_folder_button.clicked.connect(self._on_browse_folder)
        control_layout.addWidget(self.browse_folder_button)
        self._ui_elements.append(self.browse_folder_button)

        # Kubernetes button (shown when K8s provider is selected)
        self.k8s_button = QPushButton("☸️ Select Pod/App")
        self.k8s_button.setFont(self._fonts.get_ui_font(10))
        self.k8s_button.setToolTip("Select Kubernetes pod or app to track")
        self.k8s_button.clicked.connect(self._on_kubernetes_button)
        control_layout.addWidget(self.k8s_button)
        self._ui_elements.append(self.k8s_button)
        self.k8s_button.setVisible(False)  # Hidden by default

        layout.addWidget(control_frame)

        # Session management section
        session_frame = QFrame()
        session_frame.setFrameShape(QFrame.Shape.StyledPanel)
        session_layout = QHBoxLayout(session_frame)

        self.session_label = QLabel("Session:")
        self.session_label.setFont(self._fonts.get_ui_font(10, bold=True))
        session_layout.addWidget(self.session_label)
        self._ui_elements.append(self.session_label)

        self.session_combo = QComboBox()
        self.session_combo.setFont(self._fonts.get_ui_font(10))
        self.session_combo.setMinimumWidth(150)
        self.session_combo.setEditable(True)  # Allow typing new session name
        self.session_combo.currentTextChanged.connect(self._on_session_changed)
        session_layout.addWidget(self.session_combo)
        self._ui_elements.append(self.session_combo)

        self.save_session_button = QPushButton("Save")
        self.save_session_button.setFont(self._fonts.get_ui_font(9, bold=True))
        self.save_session_button.setToolTip(
            "Save current session (or enter new name to create)"
        )
        self.save_session_button.clicked.connect(self._on_save_session)
        session_layout.addWidget(self.save_session_button)
        self._ui_elements.append(self.save_session_button)

        self.duplicate_session_button = QPushButton("Duplicate")
        self.duplicate_session_button.setFont(self._fonts.get_ui_font(9))
        self.duplicate_session_button.setToolTip(
            "Duplicate current session with a new name"
        )
        self.duplicate_session_button.clicked.connect(self._on_duplicate_session)
        session_layout.addWidget(self.duplicate_session_button)
        self._ui_elements.append(self.duplicate_session_button)

        self.delete_session_button = QPushButton("Delete")
        self.delete_session_button.setFont(self._fonts.get_ui_font(9))
        self.delete_session_button.clicked.connect(self._on_delete_session)
        session_layout.addWidget(self.delete_session_button)
        self._ui_elements.append(self.delete_session_button)

        self.new_session_button = QPushButton("New Session")
        self.new_session_button.setFont(self._fonts.get_ui_font(9))
        self.new_session_button.setToolTip("Clear all logs and start fresh")
        self.new_session_button.clicked.connect(self._on_reset_session)
        session_layout.addWidget(self.new_session_button)
        self._ui_elements.append(self.new_session_button)

        session_layout.addStretch()
        layout.addWidget(session_frame)

        # Populate session combo
        self._refresh_session_list()

        # Tabbed interface
        self.tabs = QTabWidget()
        self.tabs.setFont(self._fonts.get_ui_font(10))
        # Make tabs expand to fit content with larger fonts
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555555;
            }
            QTabBar::tab {
                padding: 0.5em 1em;
                min-width: 5em;
            }
        """)
        self._ui_elements.append(self.tabs)

        # === Logs Tab ===
        logs_tab = QWidget()
        logs_layout = QVBoxLayout(logs_tab)

        self.logs_label = QLabel("Tracked Logs:")
        self.logs_label.setFont(self._fonts.get_ui_font(11, bold=True))
        logs_layout.addWidget(self.logs_label)
        self._ui_elements.append(self.logs_label)

        self.log_list = QListWidget()
        self.log_list.itemDoubleClicked.connect(self._on_log_double_clicked)
        logs_layout.addWidget(self.log_list)

        self.tabs.addTab(logs_tab, "📄 Logs")

        # === Groups Tab ===
        groups_tab = QWidget()
        groups_layout = QVBoxLayout(groups_tab)

        groups_header_layout = QHBoxLayout()
        self.groups_label = QLabel("Log Groups:")
        self.groups_label.setFont(self._fonts.get_ui_font(11, bold=True))
        groups_header_layout.addWidget(self.groups_label)
        self._ui_elements.append(self.groups_label)

        self.add_group_button = QPushButton("+ Add Group")
        self.add_group_button.setFont(self._fonts.get_ui_font(9))
        self.add_group_button.clicked.connect(self._on_add_group)
        groups_header_layout.addWidget(self.add_group_button)
        self._ui_elements.append(self.add_group_button)
        groups_header_layout.addStretch()

        groups_layout.addLayout(groups_header_layout)

        self.groups_list = QListWidget()
        self.groups_list.itemDoubleClicked.connect(self._on_group_double_clicked)
        groups_layout.addWidget(self.groups_list)

        self.tabs.addTab(groups_tab, "📁 Groups")

        # === Settings Tab ===
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)

        # Font Sizes section
        font_sizes_frame = QFrame()
        font_sizes_frame.setFrameShape(QFrame.Shape.StyledPanel)
        font_sizes_layout = QVBoxLayout(font_sizes_frame)

        self.font_sizes_title = QLabel("Font Sizes")
        self.font_sizes_title.setFont(self._fonts.get_ui_font(12, bold=True))
        font_sizes_layout.addWidget(self.font_sizes_title)
        self._ui_elements.append(self.font_sizes_title)

        # Log content font size
        log_font_layout = QHBoxLayout()
        self.log_font_label = QLabel("Log Content:")
        self.log_font_label.setFont(self._fonts.get_ui_font(10))
        log_font_layout.addWidget(self.log_font_label)
        log_font_layout.addStretch()
        self._ui_elements.append(self.log_font_label)

        # Current size display
        self.log_font_size_value = QLabel("13 pt")
        self.log_font_size_value.setFont(self._fonts.get_ui_font(10, bold=True))
        self.log_font_size_value.setStyleSheet(
            "padding: 0.3em 0.5em; background-color: #2b2b2b; border-radius: 0.2em;"
        )
        log_font_layout.addWidget(self.log_font_size_value)
        self._ui_elements.append(self.log_font_size_value)

        # Down button
        self.log_font_size_down = QPushButton("▼")
        self.log_font_size_down.setFont(self._fonts.get_ui_font(10))
        self.log_font_size_down.setFixedWidth(40)
        self.log_font_size_down.clicked.connect(lambda: self._change_log_font_size(-1))
        log_font_layout.addWidget(self.log_font_size_down)
        self._ui_elements.append(self.log_font_size_down)

        # Up button
        self.log_font_size_up = QPushButton("▲")
        self.log_font_size_up.setFont(self._fonts.get_ui_font(10))
        self.log_font_size_up.setFixedWidth(40)
        self.log_font_size_up.clicked.connect(lambda: self._change_log_font_size(1))
        log_font_layout.addWidget(self.log_font_size_up)
        self._ui_elements.append(self.log_font_size_up)

        self._log_font_size = 13  # Track current size

        font_sizes_layout.addLayout(log_font_layout)

        # UI font size
        ui_font_layout = QHBoxLayout()
        self.ui_font_label = QLabel("UI Elements:")
        self.ui_font_label.setFont(self._fonts.get_ui_font(10))
        ui_font_layout.addWidget(self.ui_font_label)
        ui_font_layout.addStretch()
        self._ui_elements.append(self.ui_font_label)

        # Current size display
        self.ui_font_size_value = QLabel("13 pt")
        self.ui_font_size_value.setFont(self._fonts.get_ui_font(10, bold=True))
        self.ui_font_size_value.setStyleSheet(
            "padding: 0.3em 0.5em; background-color: #2b2b2b; border-radius: 0.2em;"
        )
        ui_font_layout.addWidget(self.ui_font_size_value)
        self._ui_elements.append(self.ui_font_size_value)

        # Down button
        self.ui_font_size_down = QPushButton("▼")
        self.ui_font_size_down.setFont(self._fonts.get_ui_font(10))
        self.ui_font_size_down.setFixedWidth(40)
        self.ui_font_size_down.clicked.connect(lambda: self._change_ui_font_size(-1))
        ui_font_layout.addWidget(self.ui_font_size_down)
        self._ui_elements.append(self.ui_font_size_down)

        # Up button
        self.ui_font_size_up = QPushButton("▲")
        self.ui_font_size_up.setFont(self._fonts.get_ui_font(10))
        self.ui_font_size_up.setFixedWidth(40)
        self.ui_font_size_up.clicked.connect(lambda: self._change_ui_font_size(1))
        ui_font_layout.addWidget(self.ui_font_size_up)
        self._ui_elements.append(self.ui_font_size_up)

        self._ui_font_size = 13  # Track current size

        font_sizes_layout.addLayout(ui_font_layout)

        # Status bar font size
        status_font_layout = QHBoxLayout()
        self.status_font_label = QLabel("Status Bar:")
        self.status_font_label.setFont(self._fonts.get_ui_font(10))
        status_font_layout.addWidget(self.status_font_label)
        status_font_layout.addStretch()
        self._ui_elements.append(self.status_font_label)

        # Current size display
        self.status_font_size_value = QLabel("13 pt")
        self.status_font_size_value.setFont(self._fonts.get_ui_font(10, bold=True))
        self.status_font_size_value.setStyleSheet(
            "padding: 0.3em 0.5em; background-color: #2b2b2b; border-radius: 0.2em;"
        )
        status_font_layout.addWidget(self.status_font_size_value)
        self._ui_elements.append(self.status_font_size_value)

        # Down button
        self.status_font_size_down = QPushButton("▼")
        self.status_font_size_down.setFont(self._fonts.get_ui_font(10))
        self.status_font_size_down.setFixedWidth(40)
        self.status_font_size_down.clicked.connect(
            lambda: self._change_status_font_size(-1)
        )
        status_font_layout.addWidget(self.status_font_size_down)
        self._ui_elements.append(self.status_font_size_down)

        # Up button
        self.status_font_size_up = QPushButton("▲")
        self.status_font_size_up.setFont(self._fonts.get_ui_font(10))
        self.status_font_size_up.setFixedWidth(40)
        self.status_font_size_up.clicked.connect(
            lambda: self._change_status_font_size(1)
        )
        status_font_layout.addWidget(self.status_font_size_up)
        self._ui_elements.append(self.status_font_size_up)

        self._status_font_size = 13  # Track current size

        font_sizes_layout.addLayout(status_font_layout)

        settings_layout.addWidget(font_sizes_frame)

        # Window Management section
        window_mgmt_frame = QFrame()
        window_mgmt_frame.setFrameShape(QFrame.Shape.StyledPanel)
        window_mgmt_layout = QVBoxLayout(window_mgmt_frame)

        self.window_mgmt_title = QLabel("Window Management")
        self.window_mgmt_title.setFont(self._fonts.get_ui_font(12, bold=True))
        window_mgmt_layout.addWidget(self.window_mgmt_title)
        self._ui_elements.append(self.window_mgmt_title)

        # Reset Windows button with description
        reset_windows_desc = QLabel("Reset all window positions to default locations")
        reset_windows_desc.setFont(self._fonts.get_ui_font(9))
        reset_windows_desc.setStyleSheet("color: gray;")
        window_mgmt_layout.addWidget(reset_windows_desc)
        self._ui_elements.append(reset_windows_desc)

        self.reset_windows_button = QPushButton("Reset Window Positions")
        self.reset_windows_button.setFont(self._fonts.get_ui_font(10))
        self.reset_windows_button.clicked.connect(self._on_reset_windows)
        window_mgmt_layout.addWidget(self.reset_windows_button)
        self._ui_elements.append(self.reset_windows_button)

        window_mgmt_layout.addSpacing(10)

        # Set Sizes button with description
        set_sizes_desc = QLabel(
            "Resize all open log viewer windows to the default size"
        )
        set_sizes_desc.setFont(self._fonts.get_ui_font(9))
        set_sizes_desc.setStyleSheet("color: gray;")
        window_mgmt_layout.addWidget(set_sizes_desc)
        self._ui_elements.append(set_sizes_desc)

        self.set_all_sizes_button = QPushButton("Apply Default Size to All Windows")
        self.set_all_sizes_button.setFont(self._fonts.get_ui_font(10))
        self.set_all_sizes_button.clicked.connect(self._on_set_all_window_sizes)
        window_mgmt_layout.addWidget(self.set_all_sizes_button)
        self._ui_elements.append(self.set_all_sizes_button)

        settings_layout.addWidget(window_mgmt_frame)

        # MCP Server section
        mcp_frame = QFrame()
        mcp_frame.setFrameShape(QFrame.Shape.StyledPanel)
        mcp_layout = QVBoxLayout(mcp_frame)

        self.mcp_title = QLabel("MCP Server")
        self.mcp_title.setFont(self._fonts.get_ui_font(12, bold=True))
        mcp_layout.addWidget(self.mcp_title)
        self._ui_elements.append(self.mcp_title)

        mcp_desc = QLabel(
            "Enable Model Context Protocol server to expose logs to AI agents"
        )
        mcp_desc.setFont(self._fonts.get_ui_font(9))
        mcp_desc.setStyleSheet("color: gray;")
        mcp_layout.addWidget(mcp_desc)
        self._ui_elements.append(mcp_desc)

        # Enable MCP checkbox
        self.mcp_enabled_checkbox = QCheckBox("Enable MCP Server")
        self.mcp_enabled_checkbox.setFont(self._fonts.get_ui_font(10))
        mcp_settings = self._settings.get_mcp_server_settings()
        self.mcp_enabled_checkbox.setChecked(mcp_settings.get("enabled", False))
        self.mcp_enabled_checkbox.stateChanged.connect(self._on_mcp_enabled_changed)
        mcp_layout.addWidget(self.mcp_enabled_checkbox)
        self._ui_elements.append(self.mcp_enabled_checkbox)

        # Binding address
        binding_layout = QHBoxLayout()
        self.mcp_binding_label = QLabel("Binding Address:")
        self.mcp_binding_label.setFont(self._fonts.get_ui_font(10))
        binding_layout.addWidget(self.mcp_binding_label)
        self._ui_elements.append(self.mcp_binding_label)

        self.mcp_binding_input = QLineEdit()
        self.mcp_binding_input.setFont(self._fonts.get_ui_font(10))
        self.mcp_binding_input.setText(mcp_settings.get("binding_address", "127.0.0.1"))
        self.mcp_binding_input.setPlaceholderText("127.0.0.1")
        self.mcp_binding_input.textChanged.connect(self._on_mcp_binding_changed)
        binding_layout.addWidget(self.mcp_binding_input)
        self._ui_elements.append(self.mcp_binding_input)

        mcp_layout.addLayout(binding_layout)

        # Port
        port_layout = QHBoxLayout()
        self.mcp_port_label = QLabel("Port:")
        self.mcp_port_label.setFont(self._fonts.get_ui_font(10))
        port_layout.addWidget(self.mcp_port_label)
        self._ui_elements.append(self.mcp_port_label)

        self.mcp_port_spin = QSpinBox()
        self.mcp_port_spin.setFont(self._fonts.get_ui_font(10))
        self.mcp_port_spin.setRange(1024, 65535)
        self.mcp_port_spin.setValue(mcp_settings.get("port", 3000))
        self.mcp_port_spin.valueChanged.connect(self._on_mcp_port_changed)
        port_layout.addWidget(self.mcp_port_spin)
        self._ui_elements.append(self.mcp_port_spin)

        port_layout.addStretch()
        mcp_layout.addLayout(port_layout)

        # Restart note
        restart_note = QLabel(
            "Note: Changes require application restart to take effect"
        )
        restart_note.setFont(self._fonts.get_ui_font(8))
        restart_note.setStyleSheet("color: orange; font-style: italic;")
        mcp_layout.addWidget(restart_note)
        self._ui_elements.append(restart_note)

        settings_layout.addWidget(mcp_frame)
        settings_layout.addStretch()

        self.tabs.addTab(settings_tab, "⚙️ Settings")

        layout.addWidget(self.tabs)

        # Set initial button visibility based on default provider type
        self._on_provider_type_changed(self.provider_combo.currentIndex())

    def _populate_provider_combo(self) -> None:
        """Populate the provider type combo box."""
        available_providers = self._provider_registry.get_available_providers()

        for provider_info in available_providers:
            icon = provider_info.get("icon", "📄")
            display_name = provider_info.get("display_name", "Unknown")
            provider_type = provider_info.get("type", "")

            # Add item with icon and name, store type as user data
            self.provider_combo.addItem(f"{icon} {display_name}", provider_type)

        # Default to File provider
        for i in range(self.provider_combo.count()):
            if self.provider_combo.itemData(i) == ProviderType.FILE.value:
                self.provider_combo.setCurrentIndex(i)
                break

    def _on_provider_type_changed(self, index: int) -> None:
        """Handle provider type selection change.

        Args:
            index: Selected index
        """
        provider_type = self.provider_combo.currentData()

        if provider_type == ProviderType.FILE:
            # Show browse buttons for file provider
            self.browse_file_button.setVisible(True)
            self.browse_folder_button.setVisible(True)
            self.k8s_button.setVisible(False)
        elif provider_type == ProviderType.KUBERNETES:
            # Show K8s button, hide file browse buttons
            self.browse_file_button.setVisible(False)
            self.browse_folder_button.setVisible(False)
            self.k8s_button.setVisible(True)
        else:
            # Hide all buttons for other providers
            self.browse_file_button.setVisible(False)
            self.browse_folder_button.setVisible(False)
            self.k8s_button.setVisible(False)

    def _on_browse_file(self) -> None:
        """Handle browse file button click."""
        logger.info("Browse file button clicked")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Log File",
            "",
            "All Files (*);;Log Files (*.log);;Text Files (*.txt)",
        )

        logger.info(f"Selected file: {file_path}")
        if file_path:
            # Show tracking mode dialog
            dialog = TrackingModeDialog(file_path, is_folder=False, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._add_log_from_dialog(dialog)

    def _on_browse_folder(self) -> None:
        """Handle browse folder button click."""
        logger.info("Browse folder button clicked")
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Folder to Track", "", QFileDialog.Option.ShowDirsOnly
        )

        logger.info(f"Selected folder: {folder_path}")
        if folder_path:
            # Show tracking mode dialog for folder (wildcard only)
            dialog = TrackingModeDialog(folder_path, is_folder=True, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._add_log_from_dialog(dialog)

    def _on_kubernetes_button(self) -> None:
        """Handle Kubernetes button click."""
        logger.info("Kubernetes button clicked")
        try:
            self._add_kubernetes_log("")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Adding Kubernetes Log",
                f"Failed to add Kubernetes log:\n{e}",
            )
            logger.error(f"Failed to add K8s log: {e}", exc_info=True)

    def _add_log_to_list(self, path_key: str, is_wildcard: bool = False) -> None:
        """Add a log file to the list with custom widget.

        Args:
            path_key: Full path or pattern
            is_wildcard: Whether this is a wildcard pattern
        """
        # Get current UI font size from settings
        font_sizes = self._settings.get_font_sizes()
        ui_size = font_sizes.get("ui_elements", 10)

        # Create list item
        item = QListWidgetItem(self.log_list)

        # Create custom widget for the item
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)

        # Determine provider type and icon
        provider_icon = "📄"  # Default to file
        if path_key.startswith("k8s://"):
            provider_icon = "☸️"
        elif path_key.startswith("kafka://"):
            provider_icon = "📨"
        elif path_key.startswith("pubsub://"):
            provider_icon = "☁️"

        # Display name with provider icon
        if path_key.startswith("k8s://"):
            # For K8s, show namespace/pod or namespace/app=label
            display_name = path_key.replace("k8s://", "")
        else:
            # For files, show just filename
            display_name = Path(path_key).name

        # Add wildcard indicator if applicable
        if is_wildcard:
            display_name = f"{provider_icon} 🔍 {display_name}"
        else:
            display_name = f"{provider_icon} {display_name}"

        name_label = QLabel(display_name)
        name_label.setFont(self._fonts.get_ui_font(ui_size))
        name_label.setToolTip(path_key)  # Show full path on hover
        layout.addWidget(name_label)

        # Group selector
        group_combo = QComboBox()
        group_combo.setFont(self._fonts.get_ui_font(ui_size))
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
        add_to_group_btn.setFont(self._fonts.get_ui_font(ui_size))
        add_to_group_btn.setToolTip("Add to selected group")
        add_to_group_btn.setMaximumWidth(30)
        add_to_group_btn.clicked.connect(
            lambda: self._on_assign_to_group(path_key, group_combo.currentText())
        )
        layout.addWidget(add_to_group_btn)

        layout.addStretch()

        # Refresh button
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFont(self._fonts.get_ui_font(ui_size))
        refresh_btn.setToolTip("Refresh log (clear and restart)")
        refresh_btn.setMaximumWidth(30)
        refresh_btn.clicked.connect(lambda: self._on_refresh_log(path_key))
        layout.addWidget(refresh_btn)

        # Unregister/Close button
        close_btn = QPushButton("✖")
        close_btn.setFont(self._fonts.get_ui_font(ui_size))
        close_btn.setToolTip("Unregister and close log")
        close_btn.setMaximumWidth(30)
        close_btn.clicked.connect(lambda: self._on_unregister_log(path_key))
        layout.addWidget(close_btn)

        # Set the custom widget
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.ItemDataRole.UserRole, path_key)  # Store full path in item data
        self.log_list.addItem(item)
        self.log_list.setItemWidget(item, widget)

    def _add_kubernetes_log(self, input_str: str) -> None:
        """Add a Kubernetes pod log source.

        Args:
            input_str: Input string (ignored, dialog is used instead)
        """
        # Show K8s selector dialog with settings for kubeconfig persistence
        dialog = K8sSelectorDialog(self, settings=self._settings)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        namespace, tracking_mode, identifier, container, app_label = (
            dialog.get_selection()
        )

        if not identifier:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select a pod or app label to track.",
            )
            return

        # Create path key based on tracking mode
        if tracking_mode == "pod":
            # Single pod mode
            if container:
                path_key = f"k8s://{namespace}/{identifier}/{container}"
            else:
                path_key = f"k8s://{namespace}/{identifier}"
            is_wildcard = False
        else:
            # App/deployment mode (wildcard)
            path_key = f"k8s://{namespace}/app={identifier}"
            is_wildcard = True

        # Check if already tracking
        if path_key in self._providers or path_key in self._watchers:
            QMessageBox.warning(
                self,
                "Already Tracking",
                f"Already tracking: {path_key}",
            )
            return

        try:
            # Import K8s provider
            from logarithmic.providers.kubernetes_provider import KubernetesProvider

            # Create provider config
            # App mode always uses TAIL_ONLY, pod mode can use FULL_LOG
            mode = (
                ProviderMode.TAIL_ONLY
                if tracking_mode == "app"
                else ProviderMode.TAIL_ONLY
            )

            config = KubernetesProvider.create_config(
                namespace=namespace,
                pod_name=identifier if tracking_mode == "pod" else f"app={app_label}",
                container=container,
                is_deployment=(tracking_mode == "app"),
                mode=mode,
                kubeconfig_path=dialog.kubeconfig_path,  # Pass user-selected kubeconfig
            )

            # Add to list
            self._add_log_to_list(path_key, is_wildcard=is_wildcard)

            # Register with log manager
            self._log_manager.register_log(path_key)

            # Subscribe MCP bridge if enabled
            if self._mcp_bridge:
                self._mcp_bridge.subscribe_to_log(path_key)

            # Create and start provider
            provider = self._provider_registry.create_provider(
                config, self._log_manager, path_key
            )
            provider.error_occurred.connect(
                lambda err: self._on_watcher_error(path_key, err)
            )
            provider.start()

            self._providers[path_key] = provider
            self._provider_configs[path_key] = config

            # Save to settings
            self._settings.add_tracked_log(path_key)

            # Save provider config (including kubeconfig path) for session restore
            if dialog.kubeconfig_path:
                self._settings.set_provider_config(
                    path_key, {"kubeconfig_path": dialog.kubeconfig_path}
                )

            mode_desc = "app label" if tracking_mode == "app" else "pod"
            logger.info(f"Added K8s {mode_desc} log: {path_key}")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Adding K8s Log",
                f"Failed to add Kubernetes log:\n{e}",
            )
            logger.error(f"Failed to add K8s log: {e}", exc_info=True)

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

        # Restart the provider or watcher
        if path_key in self._providers:
            # New provider-based system
            provider = self._providers[path_key]
            provider.stop()

            # Recreate provider from config
            config = self._provider_configs.get(path_key)
            if config:
                new_provider = self._provider_registry.create_provider(
                    config, self._log_manager, path_key
                )
                new_provider.error_occurred.connect(
                    lambda err: self._on_watcher_error(path_key, err)
                )
                new_provider.start()
                self._providers[path_key] = new_provider
        elif path_key in self._watchers:
            # Legacy watcher system
            watcher = self._watchers[path_key]
            watcher.stop()
            watcher.wait()  # Wait for thread to finish

            # Start new watcher
            is_wildcard = "*" in path_key or "?" in path_key
            if is_wildcard:
                self._start_wildcard_watcher(path_key, path_key)
            else:
                self._start_watcher(path_key, Path(path_key))

        logger.info(f"Refreshed log: {path_key}")

    def _on_add_group(self) -> None:
        """Handle adding a new group."""
        group_name, ok = QInputDialog.getText(
            self, "Add Group", "Enter group name:", QLineEdit.EchoMode.Normal
        )

        if not ok or not group_name.strip():
            return

        group_name = group_name.strip()

        if group_name in self._available_groups:
            QMessageBox.warning(
                self, "Duplicate Group", f"Group '{group_name}' already exists."
            )
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
        # Get current UI font size from settings
        font_sizes = self._settings.get_font_sizes()
        ui_size = font_sizes.get("ui_elements", 10)

        item = QListWidgetItem(self.groups_list)

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)

        name_label = QLabel(f"📁 {group_name}")
        name_label.setFont(self._fonts.get_ui_font(ui_size, bold=True))
        layout.addWidget(name_label)

        layout.addStretch()

        # Show/Hide button
        show_btn = QPushButton("Show")
        show_btn.setFont(self._fonts.get_ui_font(ui_size))
        show_btn.setMaximumWidth(50)
        show_btn.clicked.connect(lambda: self._on_show_group(group_name))
        layout.addWidget(show_btn)

        # Remove button
        remove_btn = QPushButton("✖")
        remove_btn.setFont(self._fonts.get_ui_font(ui_size))
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
        assigned_logs = [
            path for path, group in self._log_groups.items() if group == group_name
        ]

        if assigned_logs:
            reply = QMessageBox.question(
                self,
                "Remove Group",
                f"Group '{group_name}' has {len(assigned_logs)} log(s) assigned.\n"
                f"Remove group and unassign all logs?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
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
        theme_colors = self._settings.get_theme_colors()
        group_window = LogGroupWindow(group_name, theme_colors=theme_colors)
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
            lambda: list(self._viewer_windows.values())
            + [gw for gw in self._group_windows.values() if gw != group_window]
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

        # Apply font sizes
        font_sizes = self._settings.get_font_sizes()
        group_window.set_log_font_size(font_sizes.get("log_content", 9))
        group_window.set_ui_font_size(font_sizes.get("ui_elements", 10))
        group_window.set_status_font_size(font_sizes.get("status_bar", 9))

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
            is_wildcard = "*" in path_key or "?" in path_key
            self._add_log_to_list(path_key, is_wildcard)

    def _refresh_all_group_items(self) -> None:
        """Refresh all group list items to update fonts."""
        # Store current items
        items_data = []
        for i in range(self.groups_list.count()):
            item = self.groups_list.item(i)
            group_name = item.data(Qt.ItemDataRole.UserRole)
            items_data.append(group_name)

        # Clear and recreate
        self.groups_list.clear()
        for group_name in items_data:
            self._add_group_to_list(group_name)

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

        # Stop provider or watcher
        if path_key in self._providers:
            provider = self._providers[path_key]
            provider.stop()
            del self._providers[path_key]
            if path_key in self._provider_configs:
                del self._provider_configs[path_key]
        elif path_key in self._watchers:
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

        # Unsubscribe from MCP bridge if enabled
        if self._mcp_bridge:
            self._mcp_bridge.unsubscribe_from_log(path_key)

        # Remove from settings
        self._settings.remove_tracked_log(path_key)
        self._settings.remove_provider_config(path_key)  # Clean up provider config

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
            logger.info(
                f"Log {path_key} is in group {group_name}, showing group window instead"
            )
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
        theme_colors = self._settings.get_theme_colors()
        viewer = LogViewerWindow(path_key, theme_colors=theme_colors)
        viewer.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        viewer.destroyed.connect(lambda: self._on_viewer_window_closed(path_key))

        # Connect provider/watcher pause/resume to content controller pause callback
        if path_key in self._providers:
            provider = self._providers[path_key]
            viewer.set_pause_callback(
                lambda paused: provider.pause() if paused else provider.resume()
            )
        elif path_key in self._watchers:
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

        # Apply font sizes
        font_sizes = self._settings.get_font_sizes()
        viewer.set_log_font_size(font_sizes.get("log_content", 9))
        viewer.set_ui_font_size(font_sizes.get("ui_elements", 10))
        viewer.set_status_font_size(font_sizes.get("status_bar", 9))

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

    def _on_window_position_changed(
        self, path_key: str, x: int, y: int, width: int, height: int
    ) -> None:
        """Handle window position/size change.

        Args:
            path_key: Path key identifying the log file
            x: X position
            y: Y position
            width: Window width
            height: Window height
        """
        self._settings.set_window_position(path_key, x, y, width, height)
        logger.debug(
            f"Updated window position for {path_key}: ({x}, {y}) {width}x{height}"
        )

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
        watcher.error_occurred.connect(
            lambda err: self._on_watcher_error(path_key, err)
        )
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
        watcher.file_switched.connect(
            lambda old, new: self._on_file_switched(path_key, old, new)
        )
        watcher.error_occurred.connect(
            lambda err: self._on_watcher_error(path_key, err)
        )
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

    def _restore_kubernetes_log(self, path_key: str) -> None:
        """Restore a Kubernetes log from session.

        Args:
            path_key: K8s path key (e.g., "k8s://namespace/pod" or "k8s://namespace/app=label")
        """
        try:
            from logarithmic.providers.kubernetes_provider import KubernetesProvider

            # Parse the path key
            # Format: k8s://namespace/pod-name or k8s://namespace/pod-name/container
            # or k8s://namespace/app=label
            parts = path_key.replace("k8s://", "").split("/")

            if len(parts) < 2:
                logger.warning(f"Invalid K8s path key: {path_key}")
                return

            namespace = parts[0]
            pod_or_label = parts[1]
            container = parts[2] if len(parts) > 2 else None

            # Determine if it's an app label (wildcard) or single pod
            is_deployment = pod_or_label.startswith("app=")
            is_wildcard = is_deployment

            # Get saved provider config (e.g., kubeconfig path)
            saved_config = self._settings.get_provider_config(path_key)
            kubeconfig_path = (
                saved_config.get("kubeconfig_path") if saved_config else None
            )

            # Create provider config
            config = KubernetesProvider.create_config(
                namespace=namespace,
                pod_name=pod_or_label,
                container=container,
                is_deployment=is_deployment,
                mode=ProviderMode.TAIL_ONLY,
                kubeconfig_path=kubeconfig_path,  # Restore saved kubeconfig path
            )

            # Add to list
            self._add_log_to_list(path_key, is_wildcard=is_wildcard)

            # Register with log manager
            self._log_manager.register_log(path_key)

            # Create and start provider
            provider = self._provider_registry.create_provider(
                config, self._log_manager, path_key
            )
            provider.error_occurred.connect(
                lambda err: self._on_watcher_error(path_key, err)
            )
            provider.start()

            self._providers[path_key] = provider
            self._provider_configs[path_key] = config

            mode_desc = "app label" if is_deployment else "pod"
            logger.info(f"Restored K8s {mode_desc} log: {path_key}")

        except Exception as e:
            logger.error(f"Failed to restore K8s log {path_key}: {e}", exc_info=True)

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
                # Detect provider type from path_key
                if path_str.startswith("k8s://"):
                    # Restore Kubernetes log
                    self._restore_kubernetes_log(path_str)
                    continue
                elif path_str.startswith("kafka://"):
                    logger.warning(
                        f"Kafka provider not yet implemented, skipping: {path_str}"
                    )
                    continue
                elif path_str.startswith("pubsub://"):
                    logger.warning(
                        f"PubSub provider not yet implemented, skipping: {path_str}"
                    )
                    continue

                # Check if it's a wildcard pattern (for files)
                is_wildcard = "*" in path_str or "?" in path_str

                if is_wildcard:
                    # Restore wildcard pattern using provider
                    pattern_path = Path(path_str)
                    if not pattern_path.parent.exists():
                        logger.warning(
                            f"Skipping pattern (parent dir missing): {path_str}"
                        )
                        continue

                    # Add to list with wildcard indicator
                    self._add_log_to_list(path_str, is_wildcard=True)

                    # Register with log manager
                    self._log_manager.register_log(path_str)

                    # Create and start provider
                    config = FileProvider.create_config(path_str, is_wildcard=True)
                    provider = self._provider_registry.create_provider(
                        config, self._log_manager, path_str
                    )
                    provider.error_occurred.connect(
                        lambda err, pk=path_str: self._on_watcher_error(pk, err)
                    )
                    provider.start()

                    self._providers[path_str] = provider
                    self._provider_configs[path_str] = config
                    logger.info(f"Restored wildcard pattern via provider: {path_str}")

                else:
                    # Restore regular file using provider
                    file_path = Path(path_str)

                    # Check parent directory exists
                    if not file_path.parent.exists():
                        logger.warning(f"Skipping log (parent dir missing): {path_str}")
                        continue

                    # Add to list
                    self._add_log_to_list(path_str, is_wildcard=False)

                    # Register with log manager
                    self._log_manager.register_log(path_str)

                    # Create and start provider
                    config = FileProvider.create_config(path_str, is_wildcard=False)
                    provider = self._provider_registry.create_provider(
                        config, self._log_manager, path_str
                    )
                    provider.error_occurred.connect(
                        lambda err, pk=path_str: self._on_watcher_error(pk, err)
                    )
                    provider.start()

                    self._providers[path_str] = provider
                    self._provider_configs[path_str] = config
                    logger.info(f"Restored file log via provider: {path_str}")

            except Exception as e:
                logger.error(f"Failed to restore log {path_str}: {e}")

        # Mark ALL tracked logs for auto-opening once content is available
        # This ensures windows open automatically when the app starts
        logger.info(f"Marking {len(tracked_logs)} windows for auto-open")

        for path_str in tracked_logs:
            self._pending_window_opens.add(path_str)
            logger.info(f"Will auto-open window for: {path_str}")

    def _initialize_mcp_server(self) -> None:
        """Initialize and start MCP server if enabled in settings."""
        mcp_settings = self._settings.get_mcp_server_settings()

        if not mcp_settings.get("enabled", False):
            logger.info("MCP server is disabled in settings")
            return

        try:
            # Create MCP bridge
            self._mcp_bridge = McpBridge(self._log_manager, self._settings)

            # Subscribe to all tracked logs
            self._mcp_bridge.subscribe_to_all_tracked_logs()

            # Create and start MCP server
            binding_address = mcp_settings.get("binding_address", "127.0.0.1")
            port = mcp_settings.get("port", 3000)

            self._mcp_server = LogarithmicMcpServer(
                self._mcp_bridge, host=binding_address, port=port
            )

            self._mcp_server.start()
            logger.info(f"MCP server started on {binding_address}:{port}")

        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "MCP Server Error",
                f"Failed to start MCP server: {e}\n\nThe application will continue without MCP support.",
            )

    def _on_reset_session(self) -> None:
        """Handle new session button click - clears everything and starts fresh."""
        reply = QMessageBox.question(
            self,
            "New Session",
            "Clear all logs and start a fresh session?\nCurrent session will be saved.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        logger.info("Creating new session")

        # Unsubscribe all viewers from log manager BEFORE closing
        for path_key, viewer in list(self._viewer_windows.items()):
            self._log_manager.unsubscribe(path_key, viewer)

        # Unsubscribe all group windows from log manager
        for group_name, group_window in list(self._group_windows.items()):
            for path_key in list(self._log_groups.keys()):
                if self._log_groups.get(path_key) == group_name:
                    self._log_manager.unsubscribe(path_key, group_window)

        # Stop all providers and watchers
        for provider in self._providers.values():
            provider.stop()
        for watcher in self._watchers.values():
            watcher.stop()

        # Close all viewer windows
        for viewer in list(self._viewer_windows.values()):
            viewer.close()

        # Close all group windows
        for group_window in list(self._group_windows.values()):
            group_window.close()

        # Unregister all logs from log manager
        for path_key in list(self._providers.keys()):
            self._log_manager.unregister_log(path_key)
        for path_key in list(self._watchers.keys()):
            self._log_manager.unregister_log(path_key)

        # Clear data structures
        self._providers.clear()
        self._provider_configs.clear()
        self._watchers.clear()
        self._viewer_windows.clear()
        self._group_windows.clear()
        self._log_groups.clear()
        self._available_groups.clear()
        self.log_list.clear()
        self.groups_list.clear()

        # Clear settings
        self._settings.clear_tracked_logs()

        # Clear session combo box (set to empty for new unnamed session)
        self.session_combo.blockSignals(True)
        self.session_combo.setCurrentText("")
        self.session_combo.blockSignals(False)

        logger.info("New session created")

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
        all_windows = list(self._viewer_windows.values()) + list(
            self._group_windows.values()
        )
        for i, window in enumerate(all_windows):
            window.move(offset_x + (i * 30), offset_y + (i * 30))
            window.resize(800, 600)

    def _move_all_windows_to_cursor(self) -> None:
        """Move all windows (main, viewers, groups) to the mouse cursor location.

        This is useful when monitor configuration changes (e.g., undocking a laptop)
        and windows become inaccessible on disconnected monitors.
        """
        # Get cursor position
        cursor_pos = QCursor.pos()
        cursor_x = cursor_pos.x()
        cursor_y = cursor_pos.y()

        logger.info(f"Moving all windows to cursor position: ({cursor_x}, {cursor_y})")

        # Move main window to cursor
        self.move(cursor_x, cursor_y)
        logger.info("Moved main window to cursor position")

        # Offset for stacking windows
        offset = 30
        window_count = 1

        # Move all viewer windows
        for path_key, viewer in self._viewer_windows.items():
            new_x = cursor_x + (offset * window_count)
            new_y = cursor_y + (offset * window_count)
            viewer.move(new_x, new_y)
            logger.info(f"Moved viewer window '{path_key}' to ({new_x}, {new_y})")
            window_count += 1

        # Move all group windows
        for group_name, group_window in self._group_windows.items():
            new_x = cursor_x + (offset * window_count)
            new_y = cursor_y + (offset * window_count)
            group_window.move(new_x, new_y)
            logger.info(f"Moved group window '{group_name}' to ({new_x}, {new_y})")
            window_count += 1

        total_windows = window_count
        logger.info(f"Moved {total_windows} window(s) to cursor location")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events.

        Args:
            event: Key press event
        """
        # F3 - Move all windows to cursor position
        if event.key() == Qt.Key.Key_F3:
            self._move_all_windows_to_cursor()
            event.accept()
        else:
            super().keyPressEvent(event)

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
        """Handle drop event - supports both files and folders.

        Args:
            event: Drop event
        """
        urls = event.mimeData().urls()
        if not urls:
            return

        for url in urls:
            path_str = url.toLocalFile()
            if not path_str:
                continue

            path_obj = Path(path_str)

            # Support both files and folders
            if path_obj.is_file():
                # Show tracking mode dialog for file
                dialog = TrackingModeDialog(path_str, is_folder=False, parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self._add_log_from_dialog(dialog)
            elif path_obj.is_dir():
                # Show tracking mode dialog for folder (wildcard only)
                dialog = TrackingModeDialog(path_str, is_folder=True, parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    self._add_log_from_dialog(dialog)
            else:
                QMessageBox.warning(
                    self,
                    "Invalid Drop",
                    f"Path does not exist or is not accessible:\n{path_str}",
                )

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
                if path_key in self._providers or path_key in self._watchers:
                    QMessageBox.information(
                        self,
                        "Already Tracking",
                        f"Already tracking pattern: {path_key}",
                    )
                    return

                # Validate parent directory exists
                pattern_path = Path(path_key)
                if not pattern_path.parent.exists():
                    raise InvalidPathError(
                        f"Parent directory does not exist: {pattern_path.parent}"
                    )

                # Create provider config
                config = FileProvider.create_config(path_key, is_wildcard=True)

                # Add to list
                self._add_log_to_list(path_key, is_wildcard=True)

                # Register with log manager
                self._log_manager.register_log(path_key)

                # Create and start provider
                provider = self._provider_registry.create_provider(
                    config, self._log_manager, path_key
                )
                provider.error_occurred.connect(
                    lambda err: self._on_watcher_error(path_key, err)
                )
                provider.start()

                self._providers[path_key] = provider
                self._provider_configs[path_key] = config

                # Save to settings
                self._settings.add_tracked_log(path_key)
                logger.info(
                    f"Added wildcard pattern via drag-drop (provider): {path_key}"
                )

            else:  # dedicated
                path_key = dialog.path
                file_path = Path(path_key)

                # Check if already tracking
                if path_key in self._providers or path_key in self._watchers:
                    QMessageBox.information(
                        self,
                        "Already Tracking",
                        f"Already tracking: {file_path.name}",
                    )
                    return

                # Validate path
                if not file_path.parent.exists():
                    raise InvalidPathError(
                        f"Parent directory does not exist: {file_path.parent}"
                    )

                # Check read permissions (if file exists)
                if file_path.exists() and not os.access(file_path, os.R_OK):
                    raise FileAccessError(f"Cannot read file: {file_path}")

                # Create provider config
                config = FileProvider.create_config(path_key, is_wildcard=False)

                # Add to list
                self._add_log_to_list(path_key, is_wildcard=False)

                # Register with log manager
                self._log_manager.register_log(path_key)

                # Create and start provider
                provider = self._provider_registry.create_provider(
                    config, self._log_manager, path_key
                )
                provider.error_occurred.connect(
                    lambda err: self._on_watcher_error(path_key, err)
                )
                provider.start()

                self._providers[path_key] = provider
                self._provider_configs[path_key] = config

                # Save to settings
                self._settings.add_tracked_log(path_key)
                logger.info(f"Added log via drag-drop (provider): {path_key}")

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

    def moveEvent(self, event) -> None:
        """Handle main window move event."""
        super().moveEvent(event)
        self._save_main_window_position()

    def resizeEvent(self, event) -> None:
        """Handle main window resize event."""
        super().resizeEvent(event)
        self._save_main_window_position()

    def _save_main_window_position(self) -> None:
        """Save main window position if changed."""
        pos = self.pos()
        size = self.size()
        current = (pos.x(), pos.y(), size.width(), size.height())

        if self._last_main_position is None:
            self._settings.set_main_window_position(*current)
            self._last_main_position = current
        else:
            old_x, old_y, old_w, old_h = self._last_main_position
            if (
                abs(current[0] - old_x) > 5
                or abs(current[1] - old_y) > 5
                or current[2] != old_w
                or current[3] != old_h
            ):
                self._settings.set_main_window_position(*current)
                self._last_main_position = current

    def _restore_main_window_position(self) -> None:
        """Restore main window position from settings."""
        pos = self._settings.get_main_window_position()
        if pos:
            self.move(pos["x"], pos["y"])
            self.resize(pos["width"], pos["height"])
            logger.info(
                f"Restored main window position: ({pos['x']}, {pos['y']}) {pos['width']}x{pos['height']}"
            )

    def closeEvent(self, event) -> None:
        """Handle window close event.

        Args:
            event: Close event
        """
        logger.info("Main window closing, stopping all providers and watchers...")

        # Create and show shutdown dialog
        shutdown_dialog = ShutdownDialog(self)
        shutdown_dialog.show()

        # Process events to ensure dialog is visible
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()

        # Stop MCP server
        if self._mcp_server and self._mcp_server.is_running():
            logger.info("Stopping MCP server...")
            shutdown_dialog.update_status("Stopping MCP server...")
            QApplication.processEvents()
            self._mcp_server.stop()

        # Stop all providers
        shutdown_dialog.update_status("Shutting down log providers...")
        QApplication.processEvents()
        for path_key, provider in self._providers.items():
            logger.debug(f"Stopping provider for: {path_key}")
            provider.stop()

        # Stop all watchers
        shutdown_dialog.update_status("Shutting down log watchers...")
        QApplication.processEvents()
        for path_key, watcher in self._watchers.items():
            logger.debug(f"Stopping watcher for: {path_key}")
            watcher.stop()

        # Wait for all provider threads to finish (with timeout)
        total_providers = len(self._providers)
        for idx, (path_key, provider) in enumerate(self._providers.items(), 1):
            # Check if provider has a thread to wait for
            if hasattr(provider, "wait"):
                shutdown_dialog.update_status(
                    f"Waiting for providers to finish ({idx}/{total_providers})..."
                )
                QApplication.processEvents()
                logger.debug(f"Waiting for provider thread to finish: {path_key}")
                # K8s threads may be blocked in socket reads, give them more time
                timeout = 5000 if path_key.startswith("k8s://") else 3000
                if not provider.wait(timeout):
                    logger.warning(
                        f"Provider thread did not finish in time: {path_key} "
                        "(this is normal for K8s streams blocked in socket reads)"
                    )
                else:
                    logger.debug(f"Provider thread finished: {path_key}")

        # Wait for all watcher threads to finish (with timeout)
        total_watchers = len(self._watchers)
        for idx, (path_key, watcher) in enumerate(self._watchers.items(), 1):
            shutdown_dialog.update_status(
                f"Waiting for watchers to finish ({idx}/{total_watchers})..."
            )
            QApplication.processEvents()
            logger.debug(f"Waiting for watcher thread to finish: {path_key}")
            if not watcher.wait(2000):  # Wait up to 2 seconds
                logger.warning(f"Watcher thread did not finish in time: {path_key}")
            else:
                logger.debug(f"Watcher thread finished: {path_key}")

        # Close all viewer windows
        shutdown_dialog.update_status("Closing viewer windows...")
        QApplication.processEvents()
        for viewer in list(self._viewer_windows.values()):
            viewer.close()

        # Close all group windows
        shutdown_dialog.update_status("Closing group windows...")
        QApplication.processEvents()
        for group_window in list(self._group_windows.values()):
            group_window.close()

        # Close shutdown dialog
        shutdown_dialog.close()

        logger.info("Main window cleanup complete")
        event.accept()

    # Session Management

    def _refresh_session_list(self) -> None:
        """Refresh the session combo box."""
        self.session_combo.blockSignals(True)  # Prevent triggering change event
        self.session_combo.clear()

        sessions = self._settings.get_available_sessions()
        self.session_combo.addItems(sessions)

        # Set current session
        current = self._settings.get_current_session()
        index = self.session_combo.findText(current)
        if index >= 0:
            self.session_combo.setCurrentIndex(index)

        self.session_combo.blockSignals(False)

    def _on_session_changed(self, session_name: str) -> None:
        """Handle session selection change.

        Args:
            session_name: Name of the selected session
        """
        if not session_name or session_name == self._settings.get_current_session():
            return

        # Confirm switch
        reply = QMessageBox.question(
            self,
            "Switch Session",
            f"Switch to session '{session_name}'?\nCurrent session will be saved and all windows will be closed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._switch_to_session(session_name)
        else:
            # Revert combo box
            self._refresh_session_list()

    def _switch_to_session(self, session_name: str) -> None:
        """Switch to a different session.

        Args:
            session_name: Name of the session to switch to
        """
        logger.info(f"Switching to session: {session_name}")

        # Unsubscribe all viewers from log manager BEFORE closing
        for path_key, viewer in list(self._viewer_windows.items()):
            self._log_manager.unsubscribe(path_key, viewer)

        # Unsubscribe all group windows from log manager
        for group_name, group_window in list(self._group_windows.items()):
            for path_key in list(self._log_groups.keys()):
                if self._log_groups.get(path_key) == group_name:
                    self._log_manager.unsubscribe(path_key, group_window)

        # Stop all watchers
        for watcher in list(self._watchers.values()):
            watcher.stop()

        # Close all windows
        for viewer in list(self._viewer_windows.values()):
            viewer.close()
        for group_window in list(self._group_windows.values()):
            group_window.close()

        # Clear data structures
        self._watchers.clear()
        self._viewer_windows.clear()
        self._group_windows.clear()
        self._log_groups.clear()
        self._available_groups.clear()
        self.log_list.clear()
        self.groups_list.clear()

        # Switch session in settings
        self._settings.switch_session(session_name)

        # Restore new session
        self._restore_session()

        logger.info(f"Switched to session: {session_name}")

    def _on_save_session(self) -> None:
        """Handle Save button click - saves current session."""
        session_name = self.session_combo.currentText().strip()

        if not session_name:
            # Empty name - ask for new session name
            session_name, ok = QInputDialog.getText(
                self,
                "Save New Session",
                "Enter session name:",
                QLineEdit.EchoMode.Normal,
            )

            if not ok or not session_name.strip():
                return

            session_name = session_name.strip()

        # Check if we're creating a new session or saving existing
        existing_sessions = self._settings.get_available_sessions()
        current_session = self._settings.get_current_session()

        if session_name != current_session and session_name in existing_sessions:
            # Trying to save with a different existing session name
            reply = QMessageBox.question(
                self,
                "Overwrite Session",
                f"Session '{session_name}' already exists.\nOverwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Save the session
        if session_name == current_session:
            # Just save current session
            self._settings._save()
            logger.info(f"Saved session: {session_name}")
        else:
            # Save as new session and switch to it
            self._settings.save_session_as(session_name)
            self._settings.switch_session(session_name)
            logger.info(f"Saved and switched to session: {session_name}")

        self._refresh_session_list()
        QMessageBox.information(
            self, "Session Saved", f"Session '{session_name}' saved"
        )

    def _on_duplicate_session(self) -> None:
        """Handle Duplicate button click - duplicates current session with new name."""
        current_session = self._settings.get_current_session()

        session_name, ok = QInputDialog.getText(
            self,
            "Duplicate Session",
            f"Enter name for duplicate of '{current_session}':",
            QLineEdit.EchoMode.Normal,
            f"{current_session}-copy",
        )

        if not ok or not session_name.strip():
            return

        session_name = session_name.strip()

        # Check if session exists
        if session_name in self._settings.get_available_sessions():
            reply = QMessageBox.question(
                self,
                "Overwrite Session",
                f"Session '{session_name}' already exists.\nOverwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._settings.save_session_as(session_name)
        self._refresh_session_list()
        QMessageBox.information(
            self, "Session Duplicated", f"Session duplicated as '{session_name}'"
        )
        logger.info(f"Duplicated session as: {session_name}")

    def _on_delete_session(self) -> None:
        """Handle Delete Session button click."""
        current_session = self.session_combo.currentText()

        if current_session == self._settings.get_current_session():
            QMessageBox.warning(
                self,
                "Cannot Delete",
                "Cannot delete the current session.\nSwitch to another session first.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Delete Session",
            f"Delete session '{current_session}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self._settings.delete_session(current_session):
                self._refresh_session_list()
                QMessageBox.information(
                    self, "Session Deleted", f"Session '{current_session}' deleted"
                )
                logger.info(f"Deleted session: {current_session}")
            else:
                QMessageBox.warning(
                    self,
                    "Delete Failed",
                    f"Could not delete session '{current_session}'",
                )

    # Font Size Management

    def _load_font_sizes(self) -> None:
        """Load font sizes from settings and apply to UI."""
        font_sizes = self._settings.get_font_sizes()

        # Update tracked sizes and labels
        self._log_font_size = font_sizes.get("log_content", 13)
        self._ui_font_size = font_sizes.get("ui_elements", 13)
        self._status_font_size = font_sizes.get("status_bar", 13)

        self.log_font_size_value.setText(f"{self._log_font_size} pt")
        self.ui_font_size_value.setText(f"{self._ui_font_size} pt")
        self.status_font_size_value.setText(f"{self._status_font_size} pt")

        logger.info(f"Loaded font sizes: {font_sizes}")

        # Actually apply the font sizes to UI elements
        self._apply_font_sizes(font_sizes)

    def _apply_font_sizes(self, font_sizes: dict) -> None:
        """Apply font sizes to all UI elements.

        Args:
            font_sizes: Dictionary with log_content, ui_elements, and status_bar sizes
        """
        log_size = font_sizes.get("log_content", 13)
        ui_size = font_sizes.get("ui_elements", 13)

        # Apply UI element fonts
        for element in self._ui_elements:
            element.setFont(self._fonts.get_ui_font(ui_size))

        # Apply to log viewers
        for viewer in self._viewer_windows.values():
            viewer.set_log_font_size(log_size)

        # Apply to group windows
        for group_window in self._group_windows.values():
            group_window.set_log_font_size(log_size)

        # Refresh list items to update their fonts
        self._refresh_all_log_items()
        self._refresh_all_group_items()

    def _change_log_font_size(self, delta: int) -> None:
        """Change log content font size by delta.

        Args:
            delta: Amount to change (+1 or -1)
        """
        new_size = max(6, min(24, self._log_font_size + delta))
        if new_size == self._log_font_size:
            return

        self._log_font_size = new_size
        self.log_font_size_value.setText(f"{new_size} pt")
        self._settings.set_font_size("log_content", new_size)
        logger.info(f"Log content font size changed to {new_size}")

        # Update all open log viewer windows
        for viewer in self._viewer_windows.values():
            viewer.set_log_font_size(new_size)

        # Update all group windows
        for group_window in self._group_windows.values():
            group_window.set_log_font_size(new_size)

    def _change_ui_font_size(self, delta: int) -> None:
        """Change UI elements font size by delta.

        Args:
            delta: Amount to change (+1 or -1)
        """
        new_size = max(6, min(24, self._ui_font_size + delta))
        if new_size == self._ui_font_size:
            return

        self._ui_font_size = new_size
        self.ui_font_size_value.setText(f"{new_size} pt")
        self._settings.set_font_size("ui_elements", new_size)
        logger.info(f"UI elements font size changed to {new_size}")

        # Update all UI elements
        for element in self._ui_elements:
            element.setFont(self._fonts.get_ui_font(new_size))

        # Update tab widgets
        self.tabs.setFont(self._fonts.get_ui_font(new_size))

        # Update log list items
        self._refresh_all_log_items()

        # Update group list items
        self._refresh_all_group_items()

    def _change_status_font_size(self, delta: int) -> None:
        """Change status bar font size by delta.

        Args:
            delta: Amount to change (+1 or -1)
        """
        new_size = max(6, min(24, self._status_font_size + delta))
        if new_size == self._status_font_size:
            return

        self._status_font_size = new_size
        self.status_font_size_value.setText(f"{new_size} pt")
        self._settings.set_font_size("status_bar", new_size)
        logger.info(f"Status bar font size changed to {new_size}")

    def _on_status_font_size_changed(self, size: int) -> None:
        """Handle status bar font size change."""
        self._settings.set_font_size("status_bar", size)
        logger.info(f"Status bar font size changed to {size}")

        # Update all open log viewer windows
        for viewer in self._viewer_windows.values():
            viewer.set_status_font_size(size)

        # Update all group windows
        for group_window in self._group_windows.values():
            group_window.set_status_font_size(size)

    # MCP Server Settings Handlers

    def _on_mcp_enabled_changed(self, state: int) -> None:
        """Handle MCP server enabled checkbox change.

        Args:
            state: Checkbox state (Qt.CheckState)
        """
        enabled = state == Qt.CheckState.Checked.value
        self._settings.set_mcp_server_enabled(enabled)
        logger.info(f"MCP server enabled changed to {enabled}")

        if enabled:
            # Start the MCP server
            self._start_mcp_server()
        else:
            # Stop the MCP server
            self._stop_mcp_server()

    def _on_mcp_binding_changed(self, text: str) -> None:
        """Handle MCP server binding address change.

        Args:
            text: New binding address
        """
        if text.strip():
            self._settings.set_mcp_server_binding_address(text.strip())
            logger.info(f"MCP server binding address changed to {text.strip()}")

    def _on_mcp_port_changed(self, port: int) -> None:
        """Handle MCP server port change.

        Args:
            port: New port number
        """
        self._settings.set_mcp_server_port(port)
        logger.info(f"MCP server port changed to {port}")

    def _start_mcp_server(self) -> None:
        """Start the MCP server."""
        if self._mcp_server and self._mcp_server.is_running():
            logger.info("MCP server is already running")
            return

        try:
            # Create MCP bridge if not exists
            if not self._mcp_bridge:
                self._mcp_bridge = McpBridge(self._log_manager, self._settings)
                # Subscribe to all tracked logs
                self._mcp_bridge.subscribe_to_all_tracked_logs()

            # Get settings
            mcp_settings = self._settings.get_mcp_server_settings()
            binding_address = mcp_settings.get("binding_address", "127.0.0.1")
            port = mcp_settings.get("port", 3000)

            # Create and start MCP server
            self._mcp_server = LogarithmicMcpServer(
                self._mcp_bridge, host=binding_address, port=port
            )
            self._mcp_server.start()

            logger.info(f"MCP server started on {binding_address}:{port}")
            QMessageBox.information(
                self,
                "MCP Server Started",
                f"MCP server is now running on {binding_address}:{port}\n\n"
                f"You can connect AI agents to this endpoint.",
            )

        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "MCP Server Error",
                f"Failed to start MCP server: {e}\n\nCheck the logs for more details.",
            )
            # Uncheck the checkbox since server failed to start
            self.mcp_enabled_checkbox.setChecked(False)

    def _stop_mcp_server(self) -> None:
        """Stop the MCP server."""
        if not self._mcp_server or not self._mcp_server.is_running():
            logger.info("MCP server is not running")
            return

        try:
            self._mcp_server.stop()
            logger.info("MCP server stopped")
            QMessageBox.information(
                self,
                "MCP Server Stopped",
                "MCP server has been stopped.",
            )
        except Exception as e:
            logger.error(f"Failed to stop MCP server: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "MCP Server Error",
                f"Failed to stop MCP server: {e}",
            )
