"""File-based log provider - wraps existing file watching logic."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from logarithmic.file_watcher import FileWatcherThread
from logarithmic.providers.base import LogProvider
from logarithmic.providers.base import ProviderCapabilities
from logarithmic.providers.base import ProviderConfig
from logarithmic.providers.base import ProviderMode
from logarithmic.providers.base import ProviderType
from logarithmic.wildcard_watcher import WildcardFileWatcher

if TYPE_CHECKING:
    from logarithmic.log_manager import LogManager

logger = logging.getLogger(__name__)


class FileProvider(LogProvider):
    """Provider for file-based log sources.

    Supports both single files and wildcard patterns.
    """

    def __init__(
        self, config: ProviderConfig, log_manager: "LogManager", path_key: str
    ) -> None:
        """Initialize file provider.

        Args:
            config: Provider configuration with 'path' or 'pattern'
            log_manager: Log manager instance
            path_key: Unique identifier
        """
        super().__init__(config, log_manager, path_key)

        # Get file path or pattern from config
        self._file_path = config.get("path")
        self._pattern = config.get("pattern")
        self._is_wildcard = config.get("is_wildcard", False)

        if not self._file_path and not self._pattern:
            raise ValueError("FileProvider requires 'path' or 'pattern' in config")

        self._watcher: FileWatcherThread | WildcardFileWatcher | None = None

    def start(self) -> None:
        """Start watching the file."""
        if self._running:
            logger.warning(f"FileProvider already running for {self._path_key}")
            return

        logger.info(
            f"Starting FileProvider for {self._path_key} in {self._config.mode.value} mode"
        )

        # Determine tail settings based on mode
        tail_only = self._config.mode == ProviderMode.TAIL_ONLY
        tail_lines = self._capabilities.tail_line_limit

        if self._is_wildcard:
            # Use wildcard watcher
            pattern = self._pattern or self._file_path
            self._watcher = WildcardFileWatcher(
                pattern=pattern,
                log_manager=self._log_manager,
                path_key=self._path_key,
                tail_only=tail_only,
                tail_lines=tail_lines,
            )
        else:
            # Use regular file watcher
            file_path = Path(self._file_path)
            self._watcher = FileWatcherThread(
                file_path=file_path,
                log_manager=self._log_manager,
                path_key=self._path_key,
                tail_only=tail_only,
                tail_lines=tail_lines,
            )

        # Connect error signal
        self._watcher.error_occurred.connect(self._on_error)

        # Start the watcher thread
        self._watcher.start()
        self._running = True
        logger.info(f"FileProvider started for {self._path_key}")

    def stop(self) -> None:
        """Stop watching the file."""
        if not self._running:
            return

        logger.info(f"Stopping FileProvider for {self._path_key}")

        if self._watcher:
            self._watcher.stop()
            self._watcher.wait(5000)  # Wait up to 5 seconds
            self._watcher = None

        self._running = False
        logger.info(f"FileProvider stopped for {self._path_key}")

    def pause(self) -> None:
        """Pause reading the file."""
        if self._watcher:
            self._watcher.pause()
            self._paused = True
            logger.debug(f"FileProvider paused for {self._path_key}")

    def resume(self) -> None:
        """Resume reading the file."""
        if self._watcher:
            self._watcher.resume()
            self._paused = False
            logger.debug(f"FileProvider resumed for {self._path_key}")

    def is_running(self) -> bool:
        """Check if provider is running.

        Returns:
            True if running
        """
        return self._running

    def is_paused(self) -> bool:
        """Check if provider is paused.

        Returns:
            True if paused
        """
        return self._paused

    def get_display_name(self) -> str:
        """Get display name (filename or pattern).

        Returns:
            Display name
        """
        if self._is_wildcard:
            pattern = self._pattern or self._file_path
            return f"🔍 {Path(pattern).name}"
        else:
            return Path(self._file_path).name

    def get_status_info(self) -> dict[str, Any]:
        """Get status information.

        Returns:
            Status dictionary
        """
        return {
            "provider_type": "file",
            "is_wildcard": self._is_wildcard,
            "path": self._file_path,
            "pattern": self._pattern,
            "running": self._running,
            "paused": self._paused,
        }

    def _define_capabilities(self) -> ProviderCapabilities:
        """Define file provider capabilities.

        Returns:
            Capabilities for file provider
        """
        return ProviderCapabilities(
            supports_full_log=True,
            supports_tail=True,
            tail_line_limit=10000,  # Files can handle large tail limits
            description="Reads entire file history and tails new content",
        )

    def _on_error(self, error_message: str) -> None:
        """Handle error from watcher.

        Args:
            error_message: Error message
        """
        logger.error(f"FileProvider error for {self._path_key}: {error_message}")
        self.error_occurred.emit(error_message)

    @classmethod
    def create_config(
        cls,
        path: str,
        is_wildcard: bool = False,
        mode: ProviderMode = ProviderMode.FULL_LOG,
    ) -> ProviderConfig:
        """Create a file provider configuration.

        Args:
            path: File path or wildcard pattern
            is_wildcard: Whether this is a wildcard pattern
            mode: Operating mode (full log or tail only)

        Returns:
            Provider configuration
        """
        config_dict = {
            "path": path,
            "is_wildcard": is_wildcard,
        }

        if is_wildcard:
            config_dict["pattern"] = path

        return ProviderConfig(ProviderType.FILE, mode, **config_dict)
