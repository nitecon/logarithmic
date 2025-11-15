"""Shutdown Dialog - displays progress while application is closing."""

import logging

from PySide6.QtCore import QSize
from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QProgressBar
from PySide6.QtWidgets import QVBoxLayout

logger = logging.getLogger(__name__)


class ShutdownDialog(QDialog):
    """Dialog shown during application shutdown.

    Displays a progress indicator and status message while the application
    is closing down threads, providers, and watchers.
    """

    def __init__(self, parent=None) -> None:
        """Initialize the shutdown dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Shutting Down")
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        self.setFixedSize(QSize(400, 150))

        # Create layout
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Title label
        self._title_label = QLabel("Shutting down Logarithmic...")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = self._title_label.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        layout.addWidget(self._title_label)

        # Status label
        self._status_label = QLabel("Stopping log watchers and providers...")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # Progress bar (indeterminate)
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(0)  # Indeterminate mode
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setMinimumHeight(8)
        layout.addWidget(self._progress_bar)

        # Add stretch to center content
        layout.addStretch()

        self.setLayout(layout)

        # Animation timer for status text
        self._animation_timer = QTimer()
        self._animation_timer.timeout.connect(self._animate_status)
        self._animation_dots = 0
        self._base_status = "Stopping log watchers and providers"

    def showEvent(self, event) -> None:
        """Handle show event.

        Args:
            event: Show event
        """
        super().showEvent(event)
        # Start animation
        self._animation_timer.start(500)  # Update every 500ms
        logger.info("Shutdown dialog shown")

    def hideEvent(self, event) -> None:
        """Handle hide event.

        Args:
            event: Hide event
        """
        super().hideEvent(event)
        # Stop animation
        self._animation_timer.stop()
        logger.info("Shutdown dialog hidden")

    def _animate_status(self) -> None:
        """Animate the status text with dots."""
        self._animation_dots = (self._animation_dots + 1) % 4
        dots = "." * self._animation_dots
        self._status_label.setText(f"{self._base_status}{dots}")

    def update_status(self, status: str) -> None:
        """Update the status message.

        Args:
            status: New status message
        """
        self._base_status = status
        self._animation_dots = 0
        self._status_label.setText(status)

    def closeEvent(self, event) -> None:
        """Prevent dialog from being closed by user.

        Args:
            event: Close event
        """
        # Ignore close events - only parent can close this
        event.ignore()
