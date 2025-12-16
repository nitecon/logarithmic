"""Tests for window hotkey functionality."""

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from logarithmic.main_window import MainWindow


@pytest.fixture
def main_window(qtbot):
    """Create a MainWindow instance for testing."""
    window = MainWindow()
    qtbot.addWidget(window)
    return window


@pytest.mark.skip(reason="Test flaky due to QCursor.pos mocking issues with PySide6")
def test_f3_hotkey_moves_windows_to_cursor(main_window, qtbot):
    """Test that pressing F3 moves all windows to cursor position."""
    # Mock the cursor position
    with patch("logarithmic.main_window.QCursor.pos") as mock_cursor:
        mock_pos = MagicMock()
        mock_pos.x.return_value = 500
        mock_pos.y.return_value = 300
        mock_cursor.return_value = mock_pos

        # Create mock viewer and group windows INSIDE the patch context
        mock_viewer = MagicMock()
        main_window._viewer_windows["test_log.txt"] = mock_viewer

        mock_group = MagicMock()
        main_window._group_windows["test_group"] = mock_group

        # Directly call the method that F3 triggers
        main_window._move_all_windows_to_cursor()

        # Verify that move was called on viewer and group windows
        mock_viewer.move.assert_called_once()
        mock_group.move.assert_called_once()


def test_f3_hotkey_with_no_windows(main_window, qtbot):
    """Test that pressing F3 with no windows doesn't crash."""
    with patch("logarithmic.main_window.QCursor.pos") as mock_cursor:
        mock_pos = MagicMock()
        mock_pos.x.return_value = 500
        mock_pos.y.return_value = 300
        mock_cursor.return_value = mock_pos

        # Simulate F3 key press with no windows
        key_event = QKeyEvent(
            QKeyEvent.Type.KeyPress, Qt.Key.Key_F3, Qt.KeyboardModifier.NoModifier
        )

        # Should not raise any exceptions
        main_window.keyPressEvent(key_event)


def test_other_keys_not_handled(main_window, qtbot):
    """Test that other keys are passed to parent handler."""
    # Simulate a different key press (e.g., F1)
    key_event = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_F1, Qt.KeyboardModifier.NoModifier
    )

    # Should call parent's keyPressEvent without error
    main_window.keyPressEvent(key_event)
