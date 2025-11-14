"""Kubernetes pod log provider."""

import logging
from typing import TYPE_CHECKING
from typing import Any

from PySide6.QtCore import QThread
from PySide6.QtCore import Signal

from logarithmic.providers.base import LogProvider
from logarithmic.providers.base import ProviderCapabilities
from logarithmic.providers.base import ProviderConfig
from logarithmic.providers.base import ProviderMode
from logarithmic.providers.base import ProviderType

if TYPE_CHECKING:
    from logarithmic.log_manager import LogManager

logger = logging.getLogger(__name__)

# Check if kubernetes library is available
try:
    from kubernetes import client
    from kubernetes import config
    from kubernetes import watch
    from kubernetes.client.rest import ApiException

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    logger.warning(
        "kubernetes library not installed. Install with: pip install kubernetes"
    )


class K8sLogStreamer(QThread):
    """Thread for streaming Kubernetes pod logs."""

    new_lines = Signal(str)
    error_occurred = Signal(str)

    def __init__(
        self,
        namespace: str,
        pod_name: str,
        container: str | None,
        tail_lines: int,
        log_manager: "LogManager",
        path_key: str,
        is_label_selector: bool = False,
    ) -> None:
        """Initialize K8s log streamer.

        Args:
            namespace: Kubernetes namespace
            pod_name: Pod name or label selector (e.g., "app=myapp")
            container: Container name (optional)
            tail_lines: Number of lines to tail
            log_manager: Log manager instance
            path_key: Unique identifier
            is_label_selector: If True, pod_name is a label selector
        """
        super().__init__()
        self._namespace = namespace
        self._pod_name = pod_name
        self._container = container
        self._tail_lines = tail_lines
        self._log_manager = log_manager
        self._path_key = path_key
        self._is_label_selector = is_label_selector
        self._running = False
        self._paused = False

    def run(self) -> None:
        """Stream logs from Kubernetes pod or pods matching label selector."""
        if not KUBERNETES_AVAILABLE:
            self.error_occurred.emit("Kubernetes library not installed")
            return

        self._running = True
        logger.info(f"Starting K8s log stream for {self._namespace}/{self._pod_name}")

        try:
            # Load kubeconfig
            config.load_kube_config()
            v1 = client.CoreV1Api()

            if self._is_label_selector:
                # Stream logs from all pods matching label selector
                self._stream_label_selector_logs(v1)
            else:
                # Stream logs from single pod
                self._stream_single_pod_logs(v1)

        except ApiException as e:
            error_msg = f"Kubernetes API error: {e.reason}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
        except Exception as e:
            error_msg = f"Error streaming K8s logs: {e}"
            logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)
        finally:
            self._running = False
            logger.info(
                f"K8s log stream stopped for {self._namespace}/{self._pod_name}"
            )

    def _stream_single_pod_logs(self, v1: "client.CoreV1Api") -> None:
        """Stream logs from a single pod.

        Args:
            v1: Kubernetes CoreV1Api client
        """
        w = watch.Watch()

        kwargs = {
            "name": self._pod_name,
            "namespace": self._namespace,
            "follow": True,
            "tail_lines": self._tail_lines,
            "_preload_content": False,
        }

        if self._container:
            kwargs["container"] = self._container

        for line in w.stream(v1.read_namespaced_pod_log, **kwargs):
            if not self._running:
                break

            if self._paused:
                continue

            # Add newline if not present
            if not line.endswith("\n"):
                line += "\n"

            # Publish to log manager
            self._log_manager.publish_content(self._path_key, line)
            self.new_lines.emit(line)

    def _stream_label_selector_logs(self, v1: "client.CoreV1Api") -> None:
        """Stream logs from all pods matching a label selector.

        This mimics `kubectl logs -f -l app=myapp` behavior.
        Continuously watches for pod changes and streams from new pods.

        Args:
            v1: Kubernetes CoreV1Api client
        """
        import threading
        from queue import Queue

        # Track active streaming threads
        active_threads: dict[str, threading.Thread] = {}
        Queue()

        def stream_pod_logs(pod_name: str) -> None:
            """Stream logs from a single pod in a separate thread."""
            logger.info(f"Starting log stream for pod: {pod_name}")
            try:
                w = watch.Watch()
                kwargs = {
                    "name": pod_name,
                    "namespace": self._namespace,
                    "follow": True,
                    "tail_lines": self._tail_lines,
                    "_preload_content": False,
                }

                for line in w.stream(v1.read_namespaced_pod_log, **kwargs):
                    if not self._running or pod_name not in active_threads:
                        break

                    if self._paused:
                        continue

                    # Add newline if not present
                    if not line.endswith("\n"):
                        line += "\n"

                    # Prefix with pod name for clarity
                    prefixed_line = f"[{pod_name}] {line}"

                    # Publish to log manager
                    self._log_manager.publish_content(self._path_key, prefixed_line)
                    self.new_lines.emit(prefixed_line)

            except ApiException as e:
                if self._running:
                    logger.warning(f"Pod {pod_name} log stream ended: {e.reason}")
            except Exception as e:
                if self._running:
                    logger.error(f"Error streaming from pod {pod_name}: {e}")
            finally:
                logger.info(f"Log stream ended for pod: {pod_name}")
                if pod_name in active_threads:
                    del active_threads[pod_name]

        # Watch for pod changes
        w = watch.Watch()
        try:
            for event in w.stream(
                v1.list_namespaced_pod,
                namespace=self._namespace,
                label_selector=self._pod_name,
                timeout_seconds=0,  # Watch indefinitely
            ):
                if not self._running:
                    break

                event_type = event["type"]
                pod = event["object"]
                pod_name = pod.metadata.name
                pod_phase = pod.status.phase

                logger.debug(f"Pod event: {event_type} - {pod_name} ({pod_phase})")

                if event_type == "ADDED" or event_type == "MODIFIED":
                    # Only stream from Running pods
                    if pod_phase == "Running" and pod_name not in active_threads:
                        logger.info(f"New running pod detected: {pod_name}")
                        # Start streaming in a separate thread
                        thread = threading.Thread(
                            target=stream_pod_logs, args=(pod_name,), daemon=True
                        )
                        active_threads[pod_name] = thread
                        thread.start()

                        # Notify about new pod
                        notification = f"[SYSTEM] Now streaming from pod: {pod_name}\n"
                        self._log_manager.publish_content(self._path_key, notification)
                        self.new_lines.emit(notification)

                elif event_type == "DELETED":
                    if pod_name in active_threads:
                        logger.info(f"Pod deleted: {pod_name}")
                        # Thread will stop naturally when pod is gone
                        notification = f"[SYSTEM] Pod terminated: {pod_name}\n"
                        self._log_manager.publish_content(self._path_key, notification)
                        self.new_lines.emit(notification)

        except ApiException as e:
            error_msg = f"Error watching pods: {e.reason}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error watching pods: {e}"
            logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)
        finally:
            # Clean up all streaming threads
            logger.info("Stopping all pod log streams")
            for pod_name in list(active_threads.keys()):
                if pod_name in active_threads:
                    del active_threads[pod_name]

    def stop(self) -> None:
        """Stop streaming logs."""
        self._running = False

    def pause(self) -> None:
        """Pause streaming."""
        self._paused = True

    def resume(self) -> None:
        """Resume streaming."""
        self._paused = False


class KubernetesProvider(LogProvider):
    """Provider for Kubernetes pod logs.

    Configuration should include:
    - namespace: Kubernetes namespace
    - pod_name: Pod name
    - container: Container name (optional)
    - context: Kubeconfig context (optional)
    - is_deployment: Whether this is tracking a deployment (wildcard)
    """

    def __init__(
        self, config: ProviderConfig, log_manager: "LogManager", path_key: str
    ) -> None:
        """Initialize Kubernetes provider.

        Args:
            config: Provider configuration
            log_manager: Log manager instance
            path_key: Unique identifier
        """
        super().__init__(config, log_manager, path_key)

        self._namespace = config.get("namespace", "default")
        self._pod_name = config.get("pod_name")
        self._container = config.get("container")
        self._context = config.get("context")
        self._is_deployment = config.get("is_deployment", False)

        if not self._pod_name:
            raise ValueError("KubernetesProvider requires 'pod_name' in config")

        self._streamer: K8sLogStreamer | None = None

    def start(self) -> None:
        """Start streaming pod logs."""
        if not KUBERNETES_AVAILABLE:
            error_msg = (
                "Kubernetes library not installed. Install with: pip install kubernetes"
            )
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return

        logger.info(f"Starting KubernetesProvider for {self._path_key}")

        # Determine tail lines based on mode
        tail_lines = self._capabilities.tail_line_limit
        if self._config.mode == ProviderMode.FULL_LOG:
            # For full log, use a larger tail (K8s API limitation)
            tail_lines = 10000

        # Create and start streamer thread
        self._streamer = K8sLogStreamer(
            namespace=self._namespace,
            pod_name=self._pod_name,
            container=self._container,
            tail_lines=tail_lines,
            log_manager=self._log_manager,
            path_key=self._path_key,
            is_label_selector=self._is_deployment,
        )

        self._streamer.new_lines.connect(
            lambda text: None
        )  # Already published to log manager
        self._streamer.error_occurred.connect(self._on_error)
        self._streamer.start()

        self._running = True
        logger.info(f"KubernetesProvider started for {self._path_key}")

    def stop(self) -> None:
        """Stop streaming pod logs."""
        logger.info(f"Stopping KubernetesProvider for {self._path_key}")

        if hasattr(self, "_streamer") and self._streamer:
            self._streamer.stop()
            self._streamer.wait(5000)  # Wait up to 5 seconds

        self._running = False
        logger.info(f"KubernetesProvider stopped for {self._path_key}")

    def pause(self) -> None:
        """Pause log streaming."""
        if hasattr(self, "_streamer") and self._streamer:
            self._streamer.pause()
        self._paused = True
        logger.debug(f"KubernetesProvider paused for {self._path_key}")

    def resume(self) -> None:
        """Resume log streaming."""
        if hasattr(self, "_streamer") and self._streamer:
            self._streamer.resume()
        self._paused = False
        logger.debug(f"KubernetesProvider resumed for {self._path_key}")

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
            Display name with pod info
        """
        if self._container:
            return f"☸️ {self._namespace}/{self._pod_name}/{self._container}"
        return f"☸️ {self._namespace}/{self._pod_name}"

    def get_status_info(self) -> dict[str, Any]:
        """Get status information.

        Returns:
            Status dictionary
        """
        return {
            "provider_type": "kubernetes",
            "namespace": self._namespace,
            "pod_name": self._pod_name,
            "container": self._container,
            "context": self._context,
            "running": self._running,
            "paused": self._paused,
        }

    def _define_capabilities(self) -> ProviderCapabilities:
        """Define Kubernetes provider capabilities.

        Kubernetes logs are typically streamed and we don't want to load
        the entire history. We support both modes but recommend tail-only.

        Returns:
            Capabilities for Kubernetes provider
        """
        return ProviderCapabilities(
            supports_full_log=True,  # Can read full history if needed
            supports_tail=True,
            tail_line_limit=200,  # Reasonable limit for pod logs
            description="Streams pod logs with optional history (last 200 lines recommended)",
        )

    def _on_error(self, error_message: str) -> None:
        """Handle error from streamer.

        Args:
            error_message: Error message
        """
        logger.error(f"KubernetesProvider error for {self._path_key}: {error_message}")
        self.error_occurred.emit(error_message)

    @classmethod
    def create_config(
        cls,
        namespace: str,
        pod_name: str,
        container: str | None = None,
        context: str | None = None,
        is_deployment: bool = False,
        mode: ProviderMode = ProviderMode.TAIL_ONLY,
    ) -> ProviderConfig:
        """Create a Kubernetes provider configuration.

        Args:
            namespace: Kubernetes namespace
            pod_name: Pod name
            container: Container name (optional)
            context: Kubeconfig context (optional)
            is_deployment: Whether tracking a deployment (wildcard)
            mode: Operating mode (default: TAIL_ONLY)

        Returns:
            Provider configuration
        """
        config_dict = {
            "namespace": namespace,
            "pod_name": pod_name,
            "is_deployment": is_deployment,
        }

        if container:
            config_dict["container"] = container
        if context:
            config_dict["context"] = context

        return ProviderConfig(ProviderType.KUBERNETES, mode, **config_dict)
