"""Custom exceptions for the Logarithmic application."""


class LogarithmicException(Exception):
    """Base exception for all Logarithmic errors."""

    pass


class FileAccessError(LogarithmicException):
    """Raised when a file cannot be accessed or read."""

    pass


class InvalidPathError(LogarithmicException):
    """Raised when a provided file path is invalid."""

    pass


class ProviderError(LogarithmicException):
    """Base exception for log provider errors."""

    pass


class KubernetesConnectionError(ProviderError):
    """Raised when unable to connect to Kubernetes cluster."""

    pass


class KubernetesApiError(ProviderError):
    """Raised when Kubernetes API returns an error."""

    pass


class StreamInterruptedError(LogarithmicException):
    """Raised when a log stream is interrupted."""

    pass


class ConfigurationError(LogarithmicException):
    """Raised when there is a configuration error."""

    pass


class McpServerError(LogarithmicException):
    """Raised when MCP server encounters an error."""

    pass
