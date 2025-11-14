"""Google Cloud Pub/Sub log provider (stub for future implementation)."""

import logging
from typing import TYPE_CHECKING
from typing import Any

from logarithmic.providers.base import LogProvider
from logarithmic.providers.base import ProviderCapabilities
from logarithmic.providers.base import ProviderConfig
from logarithmic.providers.base import ProviderType

if TYPE_CHECKING:
    from logarithmic.log_manager import LogManager

logger = logging.getLogger(__name__)


class PubSubProvider(LogProvider):
    """Provider for Google Cloud Pub/Sub logs.

    This is a stub implementation. To be completed in future iterations.

    Pub/Sub is a message streaming service - we only support tail mode
    as there is no concept of "full history" in Pub/Sub (messages are
    acknowledged and removed).

    Configuration should include:
    - project_id: GCP project ID
    - subscription_id: Pub/Sub subscription ID
    - credentials_path: Path to service account JSON (optional)
    """

    def __init__(
        self, config: ProviderConfig, log_manager: "LogManager", path_key: str
    ) -> None:
        """Initialize Pub/Sub provider.

        Args:
            config: Provider configuration
            log_manager: Log manager instance
            path_key: Unique identifier
        """
        super().__init__(config, log_manager, path_key)

        self._project_id = config.get("project_id")
        self._subscription_id = config.get("subscription_id")
        self._credentials_path = config.get("credentials_path")

        if not self._project_id or not self._subscription_id:
            raise ValueError(
                "PubSubProvider requires 'project_id' and 'subscription_id' in config"
            )

    def start(self) -> None:
        """Start consuming from Pub/Sub subscription."""
        logger.info(f"Starting PubSubProvider for {self._path_key}")
        # TODO: Implement Pub/Sub subscriber
        self._running = True
        raise NotImplementedError("PubSubProvider not yet implemented")

    def stop(self) -> None:
        """Stop consuming from Pub/Sub subscription."""
        logger.info(f"Stopping PubSubProvider for {self._path_key}")
        # TODO: Implement cleanup
        self._running = False

    def pause(self) -> None:
        """Pause consuming messages."""
        self._paused = True
        logger.debug(f"PubSubProvider paused for {self._path_key}")

    def resume(self) -> None:
        """Resume consuming messages."""
        self._paused = False
        logger.debug(f"PubSubProvider resumed for {self._path_key}")

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
        """Get display name.

        Returns:
            Display name with subscription info
        """
        return f"☁️ {self._project_id}/{self._subscription_id}"

    def get_status_info(self) -> dict[str, Any]:
        """Get status information.

        Returns:
            Status dictionary
        """
        return {
            "provider_type": "pubsub",
            "project_id": self._project_id,
            "subscription_id": self._subscription_id,
            "running": self._running,
            "paused": self._paused,
        }

    def _define_capabilities(self) -> ProviderCapabilities:
        """Define Pub/Sub provider capabilities.

        Pub/Sub is a message streaming service with no history retention
        once messages are acknowledged. Only tail/streaming mode is supported.

        Returns:
            Capabilities for Pub/Sub provider
        """
        return ProviderCapabilities(
            supports_full_log=False,  # Pub/Sub has no persistent history
            supports_tail=True,
            tail_line_limit=200,
            description="Streams messages from Pub/Sub subscription (tail-only, no history)",
        )

    @classmethod
    def create_config(
        cls, project_id: str, subscription_id: str, credentials_path: str | None = None
    ) -> ProviderConfig:
        """Create a Pub/Sub provider configuration.

        Args:
            project_id: GCP project ID
            subscription_id: Pub/Sub subscription ID
            credentials_path: Path to service account JSON (optional)

        Returns:
            Provider configuration
        """
        config_dict = {
            "project_id": project_id,
            "subscription_id": subscription_id,
        }

        if credentials_path:
            config_dict["credentials_path"] = credentials_path

        return ProviderConfig(ProviderType.PUBSUB, **config_dict)
