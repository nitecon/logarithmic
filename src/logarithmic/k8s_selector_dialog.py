"""Kubernetes pod selector dialog."""

import logging
from typing import Optional

from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtWidgets import QFormLayout
from PySide6.QtWidgets import QGroupBox
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QListWidget
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QRadioButton
from PySide6.QtWidgets import QVBoxLayout

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

    def __init__(self, parent=None):
        """Initialize the dialog.

        Args:
            parent: Parent widget
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

        self._setup_ui()

        if KUBERNETES_AVAILABLE:
            self._load_namespaces()
        else:
            self._show_error(
                "Kubernetes library not installed. Install with: pip install kubernetes"
            )

    def _setup_ui(self) -> None:
        """Setup the UI."""
        layout = QVBoxLayout(self)

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
