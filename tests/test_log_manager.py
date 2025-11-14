"""Tests for the log manager module."""

from unittest.mock import Mock

from logarithmic.log_manager import LogManager
from logarithmic.log_manager import LogSubscriber


class MockSubscriber:
    """Mock subscriber for testing."""

    def __init__(self) -> None:
        self.content_calls: list[tuple[str, str]] = []
        self.cleared_calls: list[str] = []
        self.interrupted_calls: list[tuple[str, str]] = []
        self.resumed_calls: list[str] = []

    def on_log_content(self, path: str, content: str) -> None:
        """Handle log content."""
        self.content_calls.append((path, content))

    def on_log_cleared(self, path: str) -> None:
        """Handle log cleared."""
        self.cleared_calls.append(path)

    def on_stream_interrupted(self, path: str, reason: str) -> None:
        """Handle stream interrupted."""
        self.interrupted_calls.append((path, reason))

    def on_stream_resumed(self, path: str) -> None:
        """Handle stream resumed."""
        self.resumed_calls.append(path)


def test_log_manager_subscribe() -> None:
    """Test subscribing to log updates."""
    manager = LogManager()
    subscriber = MockSubscriber()

    # Register the log first
    manager.register_log("test.log")
    manager.subscribe("test.log", subscriber)

    # Publish content
    manager.publish_content("test.log", "Test content")

    assert len(subscriber.content_calls) == 1
    assert subscriber.content_calls[0] == ("test.log", "Test content")


def test_log_manager_unsubscribe() -> None:
    """Test unsubscribing from log updates."""
    manager = LogManager()
    subscriber = MockSubscriber()

    manager.register_log("test.log")
    manager.subscribe("test.log", subscriber)
    manager.unsubscribe("test.log", subscriber)

    # Publish content - should not be received
    manager.publish_content("test.log", "Test content")

    assert len(subscriber.content_calls) == 0


def test_log_manager_multiple_subscribers() -> None:
    """Test multiple subscribers to the same log."""
    manager = LogManager()
    subscriber1 = MockSubscriber()
    subscriber2 = MockSubscriber()

    manager.register_log("test.log")
    manager.subscribe("test.log", subscriber1)
    manager.subscribe("test.log", subscriber2)

    manager.publish_content("test.log", "Test content")

    assert len(subscriber1.content_calls) == 1
    assert len(subscriber2.content_calls) == 1


def test_log_manager_cleared() -> None:
    """Test log cleared notification."""
    manager = LogManager()
    subscriber = MockSubscriber()

    manager.register_log("test.log")
    manager.subscribe("test.log", subscriber)

    # Clear the buffer
    manager.clear_log("test.log")

    assert len(subscriber.cleared_calls) == 1
    assert subscriber.cleared_calls[0] == "test.log"


def test_log_manager_stream_interrupted() -> None:
    """Test stream interrupted notification."""
    manager = LogManager()
    subscriber = MockSubscriber()

    manager.register_log("test.log")
    manager.subscribe("test.log", subscriber)
    manager.publish_stream_interrupted("test.log", "Connection lost")

    assert len(subscriber.interrupted_calls) == 1
    assert subscriber.interrupted_calls[0] == ("test.log", "Connection lost")


def test_log_manager_stream_resumed() -> None:
    """Test stream resumed notification."""
    manager = LogManager()
    subscriber = MockSubscriber()

    manager.register_log("test.log")
    manager.subscribe("test.log", subscriber)
    manager.publish_stream_resumed("test.log")

    assert len(subscriber.resumed_calls) == 1
    assert subscriber.resumed_calls[0] == "test.log"


def test_log_manager_subscriber_error_handling() -> None:
    """Test that errors in subscribers don't affect other subscribers."""
    manager = LogManager()

    # Create a subscriber that raises an error
    bad_subscriber = Mock(spec=LogSubscriber)
    bad_subscriber.on_log_content.side_effect = Exception("Subscriber error")

    good_subscriber = MockSubscriber()

    manager.register_log("test.log")
    manager.subscribe("test.log", bad_subscriber)
    manager.subscribe("test.log", good_subscriber)

    # Should not raise, and good subscriber should still receive
    manager.publish_content("test.log", "Test content")

    assert len(good_subscriber.content_calls) == 1
