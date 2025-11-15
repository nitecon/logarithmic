"""Kubernetes pod selector dialog."""

import logging
from typing import Optional

from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QFormLayout
from PySide6.QtWidgets import QGroupBox
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QListWidget
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QRadioButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

# Check if kubernetes library is available
try:
    from kubernetes import client
    from kubernetes import config
    from kubernetes.client.rest import ApiException

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False


class K8sSelectorDialog(QDialog):
    """Dialog for selecting Kubernetes pods to track."""

    def __init__(self, parent: Optional[QWidget] = None, settings=None) -> None:
        """Initialize the K8s selector dialog.

        Args:
            parent: Parent widget
            settings: Settings instance to load/save kubeconfig path
        """
        super().__init__(parent)
        self.setWindowTitle("Select Kubernetes Pod")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self.selected_namespace: str = "default"
        self.selected_pod: Optional[str] = None
        self.selected_container: Optional[str] = None
        self.tracking_mode: str = "pod"  # "pod" or "app"
        self.app_label: Optional[str] = None
        self.kubeconfig_path: Optional[str] = None  # User-selected kubeconfig
        self._settings = settings  # Store settings reference

        self._setup_ui()

        if not KUBERNETES_AVAILABLE:
            self._show_error(
                "Kubernetes library not installed. Install with: pip install kubernetes"
            )
        else:
            # Try to load saved kubeconfig path
            if self._settings:
                saved_path = self._settings.get_kubeconfig_path()
                if saved_path:
                    self.kubeconfig_path = saved_path
                    import os

                    self.kubeconfig_label.setText(f"✅ {os.path.basename(saved_path)}")
                    self.kubeconfig_label.setStyleSheet(
                        "color: green; font-weight: bold;"
                    )
                    self._set_controls_enabled(True)
                    self._show_info("Loading namespaces...")
                    self._load_namespaces()
                    return

            # No saved kubeconfig - require selection
            self._show_info(
                "Please select your kubeconfig file to connect to Kubernetes"
            )

    def _setup_ui(self) -> None:
        """Setup the UI."""
        layout = QVBoxLayout(self)

        # Kubeconfig file selection (for sandboxing compliance)
        kubeconfig_group = QGroupBox("⚠️ Kubeconfig File (Required)")
        kubeconfig_layout = QVBoxLayout(kubeconfig_group)

        kubeconfig_desc = QLabel(
            "Due to app sandboxing, you must explicitly select your kubeconfig file.\n"
            "This is typically located at ~/.kube/config"
        )
        kubeconfig_desc.setWordWrap(True)
        kubeconfig_desc.setStyleSheet("color: #666; margin-bottom: 10px;")
        kubeconfig_layout.addWidget(kubeconfig_desc)

        button_layout = QHBoxLayout()
        self.kubeconfig_label = QLabel("(not selected)")
        self.kubeconfig_label.setStyleSheet("color: red; font-weight: bold;")
        button_layout.addWidget(self.kubeconfig_label)
        button_layout.addStretch()

        self.browse_kubeconfig_btn = QPushButton("📄 Select Kubeconfig File")
        self.browse_kubeconfig_btn.setToolTip(
            "Select your kubeconfig file to connect to Kubernetes"
        )
        self.browse_kubeconfig_btn.setStyleSheet("font-weight: bold; padding: 0.6em;")
        self.browse_kubeconfig_btn.clicked.connect(self._on_browse_kubeconfig)
        button_layout.addWidget(self.browse_kubeconfig_btn)

        kubeconfig_layout.addLayout(button_layout)
        layout.addWidget(kubeconfig_group)

        # Tracking mode selection
        mode_group = QGroupBox("Tracking Mode")
        mode_layout = QVBoxLayout(mode_group)

        self.pod_radio = QRadioButton("Single Pod")
        self.pod_radio.setChecked(True)
        self.pod_radio.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self.pod_radio)

        pod_desc = QLabel("Track logs from a specific pod")
        pod_desc.setStyleSheet("color: gray; margin-left: 20px;")
        mode_layout.addWidget(pod_desc)

        self.app_radio = QRadioButton("App/Deployment (Wildcard)")
        self.app_radio.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self.app_radio)

        app_desc = QLabel(
            "Track all pods matching app label (tail-only, follows kubectl logs -f -l app=name)"
        )
        app_desc.setStyleSheet("color: gray; margin-left: 20px;")
        app_desc.setWordWrap(True)
        mode_layout.addWidget(app_desc)

        layout.addWidget(mode_group)

        # Form layout for namespace and container
        form_layout = QFormLayout()

        # Namespace selector
        self.namespace_combo = QComboBox()
        self.namespace_combo.currentTextChanged.connect(self._on_namespace_changed)
        form_layout.addRow("Namespace:", self.namespace_combo)

        # Refresh button
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.clicked.connect(self._load_items)
        form_layout.addRow("", self.refresh_button)

        layout.addLayout(form_layout)

        # Pod/App list (changes based on mode)
        self.list_label = QLabel("Select Pod:")
        layout.addWidget(self.list_label)
        self.pod_list = QListWidget()
        self.pod_list.itemSelectionChanged.connect(self._on_item_selected)
        self.pod_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.pod_list)

        # Container selector (optional, only for pod mode)
        self.container_layout = QFormLayout()
        self.container_input = QLineEdit()
        self.container_input.setPlaceholderText("(optional) Specify container name")
        self.container_layout.addRow("Container:", self.container_input)
        layout.addLayout(self.container_layout)

        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)

        # Disable all controls until kubeconfig is selected
        self._set_controls_enabled(False)

    def _show_error(self, message: str) -> None:
        """Show error message.

        Args:
            message: Error message
        """
        self.status_label.setText(f"❌ {message}")
        self.status_label.setStyleSheet("color: red;")

    def _show_info(self, message: str) -> None:
        """Show info message.

        Args:
            message: Info message
        """
        self.status_label.setText(f"ℹ️ {message}")
        self.status_label.setStyleSheet("color: blue;")

    def _load_namespaces(self) -> None:
        """Load available namespaces from Kubernetes."""
        if not KUBERNETES_AVAILABLE:
            return

        try:
            # Load kubeconfig from user-selected file or default
            if self.kubeconfig_path:
                config.load_kube_config(config_file=self.kubeconfig_path)
            else:
                config.load_kube_config()
            v1 = client.CoreV1Api()

            namespaces = v1.list_namespace()
            namespace_names = [ns.metadata.name for ns in namespaces.items]

            self.namespace_combo.clear()
            self.namespace_combo.addItems(namespace_names)

            # Set default namespace
            if "default" in namespace_names:
                self.namespace_combo.setCurrentText("default")

            self._show_info(f"Loaded {len(namespace_names)} namespaces")
            self._load_pods()

        except ApiException as e:
            self._show_error(f"Kubernetes API error: {e.reason}")
            logger.error(f"Failed to load namespaces: {e}")
        except Exception as e:
            self._show_error(f"Error loading namespaces: {e}")
            logger.error(f"Failed to load namespaces: {e}", exc_info=True)

    def _on_mode_changed(self) -> None:
        """Handle tracking mode change."""
        if self.pod_radio.isChecked():
            self.tracking_mode = "pod"
            self.list_label.setText("Select Pod:")
            self.container_input.setEnabled(True)
        else:
            self.tracking_mode = "app"
            self.list_label.setText("Select App Label:")
            self.container_input.setEnabled(False)
            self.container_input.clear()

        self._load_items()

    def _load_items(self) -> None:
        """Load pods or apps based on current mode."""
        if self.tracking_mode == "pod":
            self._load_pods()
        else:
            self._load_apps()

    def _load_pods(self) -> None:
        """Load pods from the selected namespace."""
        if not KUBERNETES_AVAILABLE:
            return

        namespace = self.namespace_combo.currentText()
        if not namespace:
            return

        self.selected_namespace = namespace
        self.pod_list.clear()
        self._show_info(f"Loading pods from namespace '{namespace}'...")

        try:
            # Load kubeconfig from user-selected file or default
            if self.kubeconfig_path:
                config.load_kube_config(config_file=self.kubeconfig_path)
            else:
                config.load_kube_config()
            v1 = client.CoreV1Api()

            pods = v1.list_namespaced_pod(namespace)

            if not pods.items:
                self._show_info(f"No pods found in namespace '{namespace}'")
                return

            for pod in pods.items:
                pod_name = pod.metadata.name
                status = pod.status.phase

                # Add pod with status indicator
                status_icon = "✅" if status == "Running" else "⚠️"
                self.pod_list.addItem(f"{status_icon} {pod_name} ({status})")

            self._show_info(f"Loaded {len(pods.items)} pods from '{namespace}'")

        except ApiException as e:
            self._show_error(f"Kubernetes API error: {e.reason}")
            logger.error(f"Failed to load pods: {e}")
        except Exception as e:
            self._show_error(f"Error loading pods: {e}")
            logger.error(f"Failed to load pods: {e}", exc_info=True)

    def _load_apps(self) -> None:
        """Load unique app labels from pods in the namespace."""
        if not KUBERNETES_AVAILABLE:
            return

        namespace = self.namespace_combo.currentText()
        if not namespace:
            return

        self.selected_namespace = namespace
        self.pod_list.clear()
        self._show_info(f"Loading app labels from namespace '{namespace}'...")

        try:
            # Load kubeconfig from user-selected file or default
            if self.kubeconfig_path:
                config.load_kube_config(config_file=self.kubeconfig_path)
            else:
                config.load_kube_config()
            v1 = client.CoreV1Api()

            pods = v1.list_namespaced_pod(namespace)

            if not pods.items:
                self._show_info(f"No pods found in namespace '{namespace}'")
                return

            # Collect unique app labels
            app_labels = set()
            for pod in pods.items:
                if pod.metadata.labels and "app" in pod.metadata.labels:
                    app_labels.add(pod.metadata.labels["app"])

            if not app_labels:
                self._show_info(
                    f"No pods with 'app' label found in namespace '{namespace}'"
                )
                return

            # Add app labels to list
            for app_label in sorted(app_labels):
                # Count pods with this label
                pod_count = sum(
                    1
                    for pod in pods.items
                    if pod.metadata.labels
                    and pod.metadata.labels.get("app") == app_label
                )
                self.pod_list.addItem(f"🏷️ {app_label} ({pod_count} pods)")

            self._show_info(f"Loaded {len(app_labels)} app labels from '{namespace}'")

        except ApiException as e:
            self._show_error(f"Kubernetes API error: {e.reason}")
            logger.error(f"Failed to load apps: {e}")
        except Exception as e:
            self._show_error(f"Error loading apps: {e}")
            logger.error(f"Failed to load apps: {e}", exc_info=True)

    def _set_controls_enabled(self, enabled: bool) -> None:
        """Enable or disable all controls except kubeconfig selection.

        Args:
            enabled: True to enable controls, False to disable
        """
        self.pod_radio.setEnabled(enabled)
        self.app_radio.setEnabled(enabled)
        self.namespace_combo.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)
        self.pod_list.setEnabled(enabled)
        self.container_input.setEnabled(enabled)

    def _on_browse_kubeconfig(self) -> None:
        """Handle browse kubeconfig button click."""
        from pathlib import Path
        import os

        # Check if default kubeconfig exists
        default_kubeconfig = Path.home() / ".kube" / "config"

        # If default exists, offer to use it directly
        if default_kubeconfig.exists():
            from PySide6.QtWidgets import QMessageBox

            reply = QMessageBox.question(
                self,
                "Use Default Kubeconfig?",
                f"Found kubeconfig at default location:\n{default_kubeconfig}\n\n"
                "Would you like to use this file?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply == QMessageBox.StandardButton.Yes:
                file_path = str(default_kubeconfig)
            else:
                # User wants to browse for a different file
                file_path = self._browse_for_kubeconfig()
        else:
            # No default found, show instructions and browse
            from PySide6.QtWidgets import QMessageBox

            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setWindowTitle("Locating Kubeconfig")
            msg.setText("Kubeconfig not found at default location.")
            msg.setInformativeText(
                "The file browser will open in your home directory.\n\n"
                "To access hidden folders:\n"
                "• Press Cmd+Shift+. (period) to show hidden files\n"
                "• Navigate to the .kube folder\n"
                "• Select the 'config' file"
            )
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()

            file_path = self._browse_for_kubeconfig()

        if file_path:
            self.kubeconfig_path = file_path
            self.kubeconfig_label.setText(f"✅ {os.path.basename(file_path)}")
            self.kubeconfig_label.setStyleSheet("color: green; font-weight: bold;")

            # Save globally for future dialogs
            if self._settings:
                self._settings.set_kubeconfig_path(file_path)

            # Enable controls now that we have kubeconfig
            self._set_controls_enabled(True)

            # Load namespaces with selected config
            self._show_info("Loading namespaces...")
            self._load_namespaces()

    def _browse_for_kubeconfig(self) -> str:
        """Open file browser for kubeconfig selection.

        Returns:
            Selected file path or empty string if cancelled
        """
        from pathlib import Path

        # Start in home directory
        home_dir = str(Path.home())

        # Create dialog with options to show hidden files
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Select Kubeconfig File")
        dialog.setDirectory(home_dir)
        dialog.setNameFilter("Config Files (config);;All Files (*)")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)

        # Try to enable showing hidden files (platform-dependent)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, False)

        if dialog.exec():
            files = dialog.selectedFiles()
            if files:
                return files[0]

        return ""

    def _on_namespace_changed(self, namespace: str) -> None:
        """Handle namespace selection change.

        Args:
            namespace: Selected namespace
        """
        if namespace:
            self._load_items()

    def _on_item_selected(self) -> None:
        """Handle pod/app selection."""
        selected_items = self.pod_list.selectedItems()
        if selected_items:
            display_text = selected_items[0].text()

            if self.tracking_mode == "pod":
                # Extract pod name from display text (remove status icon and status)
                # Format: "✅ pod-name (Running)"
                pod_name = display_text.split(" ", 1)[1].rsplit(" (", 1)[0]
                self.selected_pod = pod_name
                self.app_label = None
            else:
                # Extract app label from display text
                # Format: "🏷️ app-name (3 pods)"
                app_label = display_text.split(" ", 1)[1].rsplit(" (", 1)[0]
                self.app_label = app_label
                self.selected_pod = None

            self.ok_button.setEnabled(True)
        else:
            self.selected_pod = None
            self.app_label = None
            self.ok_button.setEnabled(False)

    def _on_item_double_clicked(self, item) -> None:
        """Handle pod/app double-click.

        Args:
            item: Clicked item
        """
        self.accept()

    def get_selection(self) -> tuple[str, str, str, Optional[str], Optional[str]]:
        """Get the selected namespace, tracking mode, pod/app, and container.

        Returns:
            Tuple of (namespace, tracking_mode, pod_name_or_app_label, container_name, app_label)
        """
        container = self.container_input.text().strip()

        if self.tracking_mode == "pod":
            return (
                self.selected_namespace,
                "pod",
                self.selected_pod or "",
                container if container else None,
                None,
            )
        else:
            return (
                self.selected_namespace,
                "app",
                self.app_label or "",
                None,
                self.app_label,
            )
