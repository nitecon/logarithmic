"""Provider registry for managing available log providers."""

import logging
from typing import TYPE_CHECKING

from logarithmic.providers.base import LogProvider
from logarithmic.providers.base import ProviderConfig
from logarithmic.providers.base import ProviderFactory
from logarithmic.providers.base import ProviderType

if TYPE_CHECKING:
    from logarithmic.log_manager import LogManager

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry for available log providers.

    This singleton manages the registration and creation of providers.
    """

    _instance: "ProviderRegistry | None" = None

    def __init__(self) -> None:
        """Initialize the registry."""
        self._factories: dict[ProviderType, ProviderFactory] = {}
        self._metadata: dict[ProviderType, dict] = {}

    @classmethod
    def get_instance(cls) -> "ProviderRegistry":
        """Get the singleton instance.

        Returns:
            Registry instance
        """
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._register_builtin_providers()
        return cls._instance

    def register_provider(
        self,
        provider_type: ProviderType,
        factory: ProviderFactory,
        display_name: str,
        description: str,
        icon: str = "📄",
    ) -> None:
        """Register a provider type.

        Args:
            provider_type: Type of provider
            factory: Factory function to create provider instances
            display_name: Human-readable name
            description: Description of the provider
            icon: Emoji icon for UI
        """
        self._factories[provider_type] = factory
        self._metadata[provider_type] = {
            "display_name": display_name,
            "description": description,
            "icon": icon,
        }
        logger.info(f"Registered provider: {provider_type.value} ({display_name})")

    def create_provider(
        self, config: ProviderConfig, log_manager: "LogManager", path_key: str
    ) -> LogProvider:
        """Create a provider instance.

        Args:
            config: Provider configuration
            log_manager: Log manager instance
            path_key: Unique identifier

        Returns:
            Provider instance

        Raises:
            ValueError: If provider type not registered
        """
        provider_type = config.provider_type

        if provider_type not in self._factories:
            raise ValueError(f"Unknown provider type: {provider_type}")

        factory = self._factories[provider_type]
        return factory(config, log_manager, path_key)

    def get_available_providers(self) -> list[dict]:
        """Get list of available provider types.

        Returns:
            List of provider metadata dictionaries
        """
        return [
            {"type": provider_type.value, **metadata}
            for provider_type, metadata in self._metadata.items()
        ]

    def get_provider_metadata(self, provider_type: ProviderType) -> dict:
        """Get metadata for a provider type.

        Args:
            provider_type: Provider type

        Returns:
            Metadata dictionary

        Raises:
            ValueError: If provider type not registered
        """
        if provider_type not in self._metadata:
            raise ValueError(f"Unknown provider type: {provider_type}")

        return self._metadata[provider_type]

    def is_registered(self, provider_type: ProviderType) -> bool:
        """Check if a provider type is registered.

        Args:
            provider_type: Provider type

        Returns:
            True if registered
        """
        return provider_type in self._factories

    def _register_builtin_providers(self) -> None:
        """Register built-in providers."""
        from logarithmic.providers.file_provider import FileProvider
        from logarithmic.providers.kubernetes_provider import KubernetesProvider

        # Register file provider
        self.register_provider(
            provider_type=ProviderType.FILE,
            factory=FileProvider,
            display_name="File",
            description="Watch log files on the local filesystem",
            icon="📄",
        )

        # Always register Kubernetes provider (will show error if library not installed)
        self.register_provider(
            provider_type=ProviderType.KUBERNETES,
            factory=KubernetesProvider,
            display_name="Kubernetes Pods",
            description="Stream logs from Kubernetes pods",
            icon="☸️",
        )
        logger.info("Kubernetes provider registered")
