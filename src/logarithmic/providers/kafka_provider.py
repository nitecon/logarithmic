"""Kafka topic log provider (stub for future implementation)."""

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


class KafkaProvider(LogProvider):
    """Provider for Kafka topic logs.

    This is a stub implementation. To be completed in future iterations.

    Kafka is a streaming platform - we only support tail mode (streaming)
    as reading the entire topic history would be impractical for large topics.

    Configuration should include:
    - bootstrap_servers: Kafka broker addresses
    - topic: Topic name
    - group_id: Consumer group ID
    - offset: Starting offset (latest, earliest, or specific)
    """

    def __init__(
        self,
        config: ProviderConfig,
        log_manager: "LogManager",
        path_key: str
    ) -> None:
        """Initialize Kafka provider.

        Args:
            config: Provider configuration
            log_manager: Log manager instance
            path_key: Unique identifier
        """
        super().__init__(config, log_manager, path_key)

        self._bootstrap_servers = config.get("bootstrap_servers")
        self._topic = config.get("topic")
        self._group_id = config.get("group_id", "logarithmic-consumer")
        self._offset = config.get("offset", "latest")

        if not self._bootstrap_servers or not self._topic:
            raise ValueError("KafkaProvider requires 'bootstrap_servers' and 'topic' in config")

    def start(self) -> None:
        """Start consuming from Kafka topic."""
        logger.info(f"Starting KafkaProvider for {self._path_key}")
        # TODO: Implement Kafka consumer
        self._running = True
        raise NotImplementedError("KafkaProvider not yet implemented")

    def stop(self) -> None:
        """Stop consuming from Kafka topic."""
        logger.info(f"Stopping KafkaProvider for {self._path_key}")
        # TODO: Implement cleanup
        self._running = False

    def pause(self) -> None:
        """Pause consuming messages."""
        self._paused = True
        logger.debug(f"KafkaProvider paused for {self._path_key}")

    def resume(self) -> None:
        """Resume consuming messages."""
        self._paused = False
        logger.debug(f"KafkaProvider resumed for {self._path_key}")

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
            Display name with topic info
        """
        return f"📨 {self._topic}"

    def get_status_info(self) -> dict[str, Any]:
        """Get status information.

        Returns:
            Status dictionary
        """
        return {
            "provider_type": "kafka",
            "bootstrap_servers": self._bootstrap_servers,
            "topic": self._topic,
            "group_id": self._group_id,
            "offset": self._offset,
            "running": self._running,
            "paused": self._paused,
        }

    def _define_capabilities(self) -> ProviderCapabilities:
        """Define Kafka provider capabilities.

        Kafka is a streaming platform - we only support tail/streaming mode.
        Reading the entire topic history is not practical for most use cases.

        Returns:
            Capabilities for Kafka provider
        """
        return ProviderCapabilities(
            supports_full_log=False,  # Kafka is stream-only
            supports_tail=True,
            tail_line_limit=200,
            description="Streams messages from Kafka topic (tail-only, no full history)"
        )

    @classmethod
    def create_config(
        cls,
        bootstrap_servers: str,
        topic: str,
        group_id: str = "logarithmic-consumer",
        offset: str = "latest"
    ) -> ProviderConfig:
        """Create a Kafka provider configuration.

        Args:
            bootstrap_servers: Kafka broker addresses (comma-separated)
            topic: Topic name
            group_id: Consumer group ID
            offset: Starting offset (latest, earliest)

        Returns:
            Provider configuration
        """
        config_dict = {
            "bootstrap_servers": bootstrap_servers,
            "topic": topic,
            "group_id": group_id,
            "offset": offset,
        }

        return ProviderConfig(ProviderType.KAFKA, **config_dict)
