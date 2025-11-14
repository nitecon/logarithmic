"""Base provider interface for log sources."""

import logging
from abc import ABCMeta
from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal

if TYPE_CHECKING:
    from logarithmic.log_manager import LogManager

logger = logging.getLogger(__name__)


# Custom metaclass that combines QObject's metaclass with ABCMeta
class QABCMeta(type(QObject), ABCMeta):  # type: ignore
    """Metaclass that combines Qt's metaclass with ABC."""
    pass


class ProviderType(str, Enum):
    """Types of log providers."""

    FILE = "file"
    KUBERNETES = "kubernetes"
    KAFKA = "kafka"
    PUBSUB = "pubsub"


@dataclass
class ProviderCapabilities:
    """Defines what capabilities a provider supports.

    Attributes:
        supports_full_log: Whether provider can read entire log history
        supports_tail: Whether provider can tail/stream new entries only
        tail_line_limit: Maximum lines to read when tailing (default: 200)
        description: Human-readable description of capabilities
    """

    supports_full_log: bool = True
    supports_tail: bool = True
    tail_line_limit: int = 200
    description: str = ""

    def __post_init__(self) -> None:
        """Validate capabilities."""
        if not self.supports_full_log and not self.supports_tail:
            raise ValueError("Provider must support at least one capability")

        if self.tail_line_limit < 1:
            raise ValueError("tail_line_limit must be at least 1")


class ProviderMode(str, Enum):
    """Operating mode for a provider."""

    FULL_LOG = "full_log"  # Read entire history then tail
    TAIL_ONLY = "tail_only"  # Only tail new entries (skip history)


class ProviderConfig:
    """Base configuration for a provider instance.

    This is a simple data holder that providers can extend
    to store their specific configuration.
    """

    def __init__(
        self,
        provider_type: ProviderType,
        mode: ProviderMode = ProviderMode.FULL_LOG,
        **kwargs: Any
    ) -> None:
        """Initialize provider config.

        Args:
            provider_type: Type of provider
            mode: Operating mode (full log or tail only)
            **kwargs: Provider-specific configuration
        """
        self.provider_type = provider_type
        self.mode = mode
        self.config = kwargs

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        return self.config.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            "provider_type": self.provider_type.value,
            "mode": self.mode.value,
            **self.config
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderConfig":
        """Create from dictionary.

        Args:
            data: Dictionary with provider_type, mode, and config

        Returns:
            ProviderConfig instance
        """
        provider_type = ProviderType(data.pop("provider_type"))
        mode = ProviderMode(data.pop("mode", ProviderMode.FULL_LOG.value))
        return cls(provider_type, mode, **data)


class LogProvider(QObject, metaclass=QABCMeta):
    """Abstract base class for log providers.

    A provider is responsible for:
    - Connecting to a log source (file, k8s pod, kafka topic, etc.)
    - Reading log content
    - Publishing content to the LogManager
    - Managing lifecycle (start, stop, pause, resume)

    Signals:
        error_occurred: Emitted when an error occurs (error_message)
    """

    error_occurred = Signal(str)

    def __init__(
        self,
        config: ProviderConfig,
        log_manager: "LogManager",
        path_key: str
    ) -> None:
        """Initialize the provider.

        Args:
            config: Provider configuration
            log_manager: Central log manager for publishing events
            path_key: Unique identifier for this log source
        """
        super().__init__()
        self._config = config
        self._log_manager = log_manager
        self._path_key = path_key
        self._running = False
        self._paused = False
        self._capabilities = self._define_capabilities()

    @abstractmethod
    def start(self) -> None:
        """Start the provider (begin reading logs).

        This should be non-blocking and start background threads/tasks
        as needed.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the provider and clean up resources."""
        pass

    @abstractmethod
    def pause(self) -> None:
        """Pause log reading (but maintain connection)."""
        pass

    @abstractmethod
    def resume(self) -> None:
        """Resume log reading."""
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """Check if provider is running.

        Returns:
            True if running
        """
        pass

    @abstractmethod
    def is_paused(self) -> bool:
        """Check if provider is paused.

        Returns:
            True if paused
        """
        pass

    @abstractmethod
    def get_display_name(self) -> str:
        """Get human-readable display name for this log source.

        Returns:
            Display name (e.g., filename, pod name, topic name)
        """
        pass

    @abstractmethod
    def get_status_info(self) -> dict[str, Any]:
        """Get current status information.

        Returns:
            Dictionary with status details (provider-specific)
        """
        pass

    @abstractmethod
    def _define_capabilities(self) -> ProviderCapabilities:
        """Define the capabilities of this provider.

        This method should be implemented by each provider to declare
        what operations it supports.

        Returns:
            ProviderCapabilities instance
        """
        pass

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Get provider capabilities.

        Returns:
            Provider capabilities
        """
        return self._capabilities

    @property
    def config(self) -> ProviderConfig:
        """Get provider configuration.

        Returns:
            Provider configuration
        """
        return self._config

    @property
    def path_key(self) -> str:
        """Get the unique identifier for this log source.

        Returns:
            Path key
        """
        return self._path_key

    @property
    def provider_type(self) -> ProviderType:
        """Get the provider type.

        Returns:
            Provider type
        """
        return self._config.provider_type


class ProviderFactory(Protocol):
    """Protocol for provider factory functions."""

    def __call__(
        self,
        config: ProviderConfig,
        log_manager: "LogManager",
        path_key: str
    ) -> LogProvider:
        """Create a provider instance.

        Args:
            config: Provider configuration
            log_manager: Log manager instance
            path_key: Unique identifier

        Returns:
            Provider instance
        """
        ...
