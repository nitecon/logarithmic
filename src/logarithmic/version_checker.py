"""Version checker for Logarithmic application.

Checks GitHub releases for newer versions and notifies the user.
"""

import logging
import os
import subprocess  # nosec B404 - subprocess used only with hardcoded git commands
from dataclasses import dataclass

from PySide6.QtCore import QObject
from PySide6.QtCore import QThread
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

GITHUB_REPO = "Nitecon/logarithmic"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"


@dataclass
class VersionInfo:
    """Version information from GitHub."""

    tag_name: str
    version: str
    html_url: str
    published_at: str
    body: str


def get_current_version() -> str:
    """Get the current application version.

    Priority:
    1. APP_VERSION environment variable (set by PyInstaller build)
    2. Git tag with dev suffix if dirty/ahead (for development)
    3. Fallback to hardcoded version

    Returns:
        Current version string (without 'v' prefix)
    """
    # Check environment variable first (set during build)
    env_version = os.environ.get("APP_VERSION")
    if env_version:
        return env_version.lstrip("v")

    # Try git for development - use describe with dirty flag
    try:
        # Get full describe output including commits ahead and dirty state
        result = subprocess.run(  # nosec B603 B607 - hardcoded git command, no user input
            ["git", "describe", "--tags", "--dirty", "--always"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            version = result.stdout.strip().lstrip("v")
            # If version contains commits ahead (e.g., "1.2.8-5-g1234567") or dirty flag
            # it means we're in development
            if "-" in version:
                # Extract base version and mark as dev
                base_version = version.split("-")[0]
                return f"{base_version}-dev"
            return version
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass

    # Fallback
    return "1.0.0"


def parse_version(version_str: str) -> tuple[tuple[int, ...], bool]:
    """Parse version string into comparable tuple.

    Args:
        version_str: Version string like "1.2.8", "v1.2.8", or "1.2.8-dev"

    Returns:
        Tuple of (version_tuple, is_dev) where version_tuple is integers for comparison
        and is_dev indicates if this is a development version
    """
    clean = version_str.lstrip("v")
    is_dev = clean.endswith("-dev")
    if is_dev:
        clean = clean[:-4]  # Remove "-dev" suffix

    parts = []
    for part in clean.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return (tuple(parts), is_dev)


def is_newer_version(latest: str, current: str) -> bool:
    """Check if latest version is newer than current.

    Dev versions (e.g., "1.2.8-dev") are considered older than their base release,
    so if current is "1.2.8-dev" and latest is "1.2.8", an update is available.

    Args:
        latest: Latest version string (from GitHub releases)
        current: Current version string (may include -dev suffix)

    Returns:
        True if latest is newer than current
    """
    latest_parts, latest_is_dev = parse_version(latest)
    current_parts, current_is_dev = parse_version(current)

    # If versions are equal, dev version is older than release
    if latest_parts == current_parts:
        # If current is dev and latest is not, update available
        return current_is_dev and not latest_is_dev

    # Otherwise compare version numbers
    return latest_parts > current_parts


class VersionCheckWorker(QObject):
    """Worker to check for updates in background thread."""

    finished = Signal(object)  # VersionInfo or None
    error = Signal(str)

    def run(self) -> None:
        """Check GitHub API for latest release."""
        try:
            import urllib.request

            req = urllib.request.Request(
                GITHUB_API_URL,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Logarithmic-App",
                },
            )

            with urllib.request.urlopen(req, timeout=10) as response:  # nosec B310 - URL is hardcoded GitHub API
                import json

                data = json.loads(response.read().decode())

                version_info = VersionInfo(
                    tag_name=data.get("tag_name", ""),
                    version=data.get("tag_name", "").lstrip("v"),
                    html_url=data.get("html_url", GITHUB_RELEASES_URL),
                    published_at=data.get("published_at", ""),
                    body=data.get("body", ""),
                )

                self.finished.emit(version_info)

        except Exception as e:
            logger.debug(f"Version check failed: {e}")
            self.error.emit(str(e))


class UpdateAvailableDialog(QDialog):
    """Dialog to notify user of available update."""

    def __init__(
        self,
        current_version: str,
        latest_version: str,
        release_url: str,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the update dialog.

        Args:
            current_version: Current app version
            latest_version: Latest available version
            release_url: URL to the release page
            parent: Parent widget
        """
        super().__init__(parent)
        self.release_url = release_url

        self.setWindowTitle("Update Available")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Title
        title = QLabel(f"<h3>Logarithmic {latest_version} is available!</h3>")
        layout.addWidget(title)

        # Current version info
        info = QLabel(
            f"You are currently running version <b>{current_version}</b>.<br><br>"
            f"A new version <b>{latest_version}</b> is available for download.<br><br>"
            "<i>Note: Distribution to app stores may take a short period of time.</i>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Buttons
        button_layout = QHBoxLayout()

        download_btn = QPushButton("View Release")
        download_btn.clicked.connect(self._open_release_page)
        button_layout.addWidget(download_btn)

        later_btn = QPushButton("Later")
        later_btn.clicked.connect(self.accept)
        button_layout.addWidget(later_btn)

        layout.addLayout(button_layout)

    def _open_release_page(self) -> None:
        """Open the release page in browser."""
        import webbrowser

        webbrowser.open(self.release_url)
        self.accept()


class VersionChecker(QObject):
    """Manages version checking on application startup."""

    update_available = Signal(str, str, str)  # current, latest, url
    no_update_available = Signal(str)  # current version
    check_failed = Signal(str)  # error message

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the version checker.

        Args:
            parent: Parent QObject
        """
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: VersionCheckWorker | None = None
        self._current_version = get_current_version()

    def check_for_updates(self) -> None:
        """Start background check for updates."""
        logger.info(f"Checking for updates (current version: {self._current_version})")

        self._thread = QThread()
        self._worker = VersionCheckWorker()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_check_complete)
        self._worker.error.connect(self._on_check_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)

        self._thread.start()

    def _on_check_complete(self, version_info: VersionInfo | None) -> None:
        """Handle successful version check.

        Args:
            version_info: Version information from GitHub
        """
        if version_info is None:
            return

        logger.info(f"Latest version: {version_info.version}")

        if is_newer_version(version_info.version, self._current_version):
            logger.info(
                f"Update available: {self._current_version} -> {version_info.version}"
            )
            self.update_available.emit(
                self._current_version,
                version_info.version,
                version_info.html_url,
            )
        else:
            logger.info("Application is up to date")
            self.no_update_available.emit(self._current_version)

    def _on_check_error(self, error: str) -> None:
        """Handle version check error.

        Args:
            error: Error message
        """
        logger.debug(f"Version check error (non-critical): {error}")
        self.check_failed.emit(error)

    def _cleanup(self) -> None:
        """Clean up thread resources."""
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._thread:
            self._thread.deleteLater()
            self._thread = None

    def stop(self) -> None:
        """Stop the version check thread if running."""
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(1000)  # Wait up to 1 second

    @property
    def current_version(self) -> str:
        """Get the current application version."""
        return self._current_version
