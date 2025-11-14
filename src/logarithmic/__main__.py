"""Main entry point for the Logarithmic application."""

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from logarithmic.logging_config import configure_logging
from logarithmic.main_window import MainWindow


def main() -> int:
    """Run the Logarithmic application.

    Returns:
        Exit code
    """
    # Enable high DPI scaling for Retina displays
    # Note: In Qt 6, high DPI scaling is enabled by default
    # We only need to set the rounding policy for better scaling on Retina displays
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Configure structured logging
    configure_logging()

    logger = logging.getLogger(__name__)
    logger.info("Starting Logarithmic application")

    app = QApplication(sys.argv)
    app.setApplicationName("Logarithmic")
    app.setOrganizationName("Logarithmic")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
