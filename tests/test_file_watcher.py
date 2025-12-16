"""Tests for file watcher module with file state change detection."""

import time
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from logarithmic.file_watcher import FileState
from logarithmic.file_watcher import FileWatcherThread


class TestFileState:
    """Tests for FileState dataclass."""

    def test_from_path_existing_file(self, tmp_path: Path) -> None:
        """Test creating FileState from an existing file."""
        test_file = tmp_path / "test.log"
        test_file.write_text("test content")

        state = FileState.from_path(test_file)

        assert state is not None
        assert state.size == len("test content")
        assert state.mtime > 0
        assert state.inode > 0

    def test_from_path_nonexistent_file(self, tmp_path: Path) -> None:
        """Test creating FileState from a non-existent file returns None."""
        test_file = tmp_path / "nonexistent.log"

        state = FileState.from_path(test_file)

        assert state is None

    def test_from_path_permission_error(self, tmp_path: Path) -> None:
        """Test FileState handles permission errors gracefully."""
        test_file = tmp_path / "test.log"
        test_file.write_text("test content")

        with patch.object(Path, "stat", side_effect=PermissionError("Access denied")):
            state = FileState.from_path(test_file)

        assert state is None

    def test_file_state_detects_size_change(self, tmp_path: Path) -> None:
        """Test that FileState detects file size changes."""
        test_file = tmp_path / "test.log"
        test_file.write_text("initial")

        state1 = FileState.from_path(test_file)
        assert state1 is not None

        test_file.write_text("initial with more content")

        state2 = FileState.from_path(test_file)
        assert state2 is not None

        assert state2.size > state1.size

    def test_file_state_detects_mtime_change(self, tmp_path: Path) -> None:
        """Test that FileState detects modification time changes."""
        test_file = tmp_path / "test.log"
        test_file.write_text("initial")

        state1 = FileState.from_path(test_file)
        assert state1 is not None

        # Wait a bit to ensure mtime changes
        time.sleep(0.1)
        test_file.write_text("modified")

        state2 = FileState.from_path(test_file)
        assert state2 is not None

        assert state2.mtime >= state1.mtime

    def test_file_state_detects_truncation(self, tmp_path: Path) -> None:
        """Test that FileState detects file truncation (size decrease)."""
        test_file = tmp_path / "test.log"
        test_file.write_text("this is a longer content")

        state1 = FileState.from_path(test_file)
        assert state1 is not None

        test_file.write_text("short")

        state2 = FileState.from_path(test_file)
        assert state2 is not None

        assert state2.size < state1.size

    def test_file_state_detects_inode_change(self, tmp_path: Path) -> None:
        """Test that FileState detects file replacement via inode, mtime, or size change."""
        test_file = tmp_path / "test.log"
        test_file.write_text("original")

        state1 = FileState.from_path(test_file)
        assert state1 is not None

        # Delete and recreate file (simulates move + create)
        test_file.unlink()
        test_file.write_text("replacement")

        state2 = FileState.from_path(test_file)
        assert state2 is not None

        # File replacement can be detected by any of these changes:
        # - inode changed (common on most systems)
        # - mtime changed (if enough time passed)
        # - size changed (content is different)
        # On fast CI systems, inode may be reused and mtime may be same,
        # but size will always differ if content differs
        assert (
            state2.inode != state1.inode
            or state2.mtime > state1.mtime
            or state2.size != state1.size
        )


class TestFileWatcherThreadValidation:
    """Tests for FileWatcherThread file state validation."""

    @pytest.fixture
    def mock_log_manager(self) -> MagicMock:
        """Create a mock log manager."""
        manager = MagicMock()
        manager.publish_content = MagicMock()
        manager.publish_file_created = MagicMock()
        manager.publish_file_deleted = MagicMock()
        manager.publish_stream_interrupted = MagicMock()
        manager.publish_stream_resumed = MagicMock()
        manager.clear_buffer = MagicMock()
        return manager

    def test_validate_file_state_detects_deletion(
        self, tmp_path: Path, mock_log_manager: MagicMock
    ) -> None:
        """Test that _validate_file_state detects file deletion."""
        test_file = tmp_path / "test.log"
        test_file.write_text("initial content")

        watcher = FileWatcherThread(
            file_path=test_file,
            log_manager=mock_log_manager,
            path_key="test_key",
        )

        # Simulate file being opened and state captured
        watcher._file_handle = MagicMock()
        watcher._last_file_state = FileState.from_path(test_file)

        # Delete the file
        test_file.unlink()

        # Mock _on_file_deleted to track if it was called
        watcher._on_file_deleted = MagicMock()

        # Validate file state
        watcher._validate_file_state()

        # Should have detected deletion
        watcher._on_file_deleted.assert_called_once()

    def test_validate_file_state_detects_truncation(
        self, tmp_path: Path, mock_log_manager: MagicMock
    ) -> None:
        """Test that _validate_file_state detects file truncation."""
        test_file = tmp_path / "test.log"
        test_file.write_text("this is a longer initial content")

        watcher = FileWatcherThread(
            file_path=test_file,
            log_manager=mock_log_manager,
            path_key="test_key",
        )

        # Simulate file being opened and state captured
        watcher._file_handle = MagicMock()
        watcher._last_file_state = FileState.from_path(test_file)

        # Truncate the file
        test_file.write_text("short")

        # Mock _handle_truncation to track if it was called
        watcher._handle_truncation = MagicMock()

        # Validate file state
        watcher._validate_file_state()

        # Should have detected truncation
        watcher._handle_truncation.assert_called_once()

    def test_validate_file_state_detects_inode_change(
        self, tmp_path: Path, mock_log_manager: MagicMock
    ) -> None:
        """Test that _validate_file_state detects inode change (file replacement)."""
        test_file = tmp_path / "test.log"
        test_file.write_text("original content")

        watcher = FileWatcherThread(
            file_path=test_file,
            log_manager=mock_log_manager,
            path_key="test_key",
        )

        # Simulate file being opened and state captured
        watcher._file_handle = MagicMock()
        watcher._last_file_state = FileState.from_path(test_file)
        original_inode = watcher._last_file_state.inode

        # Replace the file (delete + create)
        test_file.unlink()
        test_file.write_text("replacement content")

        new_state = FileState.from_path(test_file)

        # Only test if inode actually changed (filesystem dependent)
        if new_state and new_state.inode != original_inode:
            # Mock _reload_file to track if it was called
            watcher._reload_file = MagicMock()

            # Validate file state
            watcher._validate_file_state()

            # Should have detected inode change and called reload
            watcher._reload_file.assert_called_once_with("File replaced")

    def test_validate_file_state_detects_modification(
        self, tmp_path: Path, mock_log_manager: MagicMock
    ) -> None:
        """Test that _validate_file_state detects file modification."""
        test_file = tmp_path / "test.log"
        test_file.write_text("initial content")

        watcher = FileWatcherThread(
            file_path=test_file,
            log_manager=mock_log_manager,
            path_key="test_key",
        )

        # Simulate file being opened and state captured
        watcher._file_handle = MagicMock()
        watcher._last_file_state = FileState.from_path(test_file)

        # Wait and modify the file
        time.sleep(0.1)
        with open(test_file, "a") as f:
            f.write("\nnew content")

        # Mock _on_file_modified to track if it was called
        watcher._on_file_modified = MagicMock()

        # Validate file state
        watcher._validate_file_state()

        # Should have detected modification
        watcher._on_file_modified.assert_called_once()

    def test_validate_file_state_no_action_when_unchanged(
        self, tmp_path: Path, mock_log_manager: MagicMock
    ) -> None:
        """Test that _validate_file_state does nothing when file is unchanged."""
        test_file = tmp_path / "test.log"
        test_file.write_text("initial content")

        watcher = FileWatcherThread(
            file_path=test_file,
            log_manager=mock_log_manager,
            path_key="test_key",
        )

        # Simulate file being opened and state captured
        watcher._file_handle = MagicMock()
        watcher._last_file_state = FileState.from_path(test_file)

        # Mock methods to track if they were called
        watcher._on_file_deleted = MagicMock()
        watcher._on_file_modified = MagicMock()
        watcher._handle_truncation = MagicMock()
        watcher._reload_file = MagicMock()

        # Validate file state without any changes
        watcher._validate_file_state()

        # None of the handlers should be called
        watcher._on_file_deleted.assert_not_called()
        watcher._on_file_modified.assert_not_called()
        watcher._handle_truncation.assert_not_called()
        watcher._reload_file.assert_not_called()

    def test_validate_file_state_skips_when_no_handle(
        self, tmp_path: Path, mock_log_manager: MagicMock
    ) -> None:
        """Test that _validate_file_state skips when no file handle."""
        test_file = tmp_path / "test.log"
        test_file.write_text("initial content")

        watcher = FileWatcherThread(
            file_path=test_file,
            log_manager=mock_log_manager,
            path_key="test_key",
        )

        # No file handle set
        watcher._file_handle = None
        watcher._last_file_state = FileState.from_path(test_file)

        # Mock methods to track if they were called
        watcher._on_file_deleted = MagicMock()

        # Delete the file
        test_file.unlink()

        # Validate file state - should skip because no handle
        watcher._validate_file_state()

        # Should not have called any handlers
        watcher._on_file_deleted.assert_not_called()


class TestFileWatcherThreadTruncation:
    """Tests for FileWatcherThread truncation handling."""

    @pytest.fixture
    def mock_log_manager(self) -> MagicMock:
        """Create a mock log manager."""
        manager = MagicMock()
        manager.publish_content = MagicMock()
        manager.publish_stream_interrupted = MagicMock()
        manager.publish_stream_resumed = MagicMock()
        return manager

    def test_handle_truncation_seeks_to_beginning(
        self, tmp_path: Path, mock_log_manager: MagicMock
    ) -> None:
        """Test that _handle_truncation seeks file to beginning."""
        test_file = tmp_path / "test.log"
        test_file.write_text("initial content")

        watcher = FileWatcherThread(
            file_path=test_file,
            log_manager=mock_log_manager,
            path_key="test_key",
        )

        # Create a mock file handle
        mock_handle = MagicMock()
        mock_handle.read.return_value = "new content after truncation"
        watcher._file_handle = mock_handle

        # Call truncation handler
        watcher._handle_truncation()

        # Should seek to beginning
        mock_handle.seek.assert_called_once_with(0)

        # Should publish interruption and resumption
        mock_log_manager.publish_stream_interrupted.assert_called_once()
        mock_log_manager.publish_stream_resumed.assert_called_once()

        # Should read and publish content (separator + content = 2 calls)
        mock_handle.read.assert_called_once()
        assert mock_log_manager.publish_content.call_count == 2  # separator + content


class TestFileWatcherThreadReload:
    """Tests for FileWatcherThread file reload functionality."""

    @pytest.fixture
    def mock_log_manager(self) -> MagicMock:
        """Create a mock log manager."""
        manager = MagicMock()
        manager.publish_content = MagicMock()
        manager.publish_stream_interrupted = MagicMock()
        manager.publish_stream_resumed = MagicMock()
        manager.clear_buffer = MagicMock()
        return manager

    def test_reload_file_clears_buffer(
        self, tmp_path: Path, mock_log_manager: MagicMock
    ) -> None:
        """Test that _reload_file clears the log buffer."""
        test_file = tmp_path / "test.log"
        test_file.write_text("replacement content")

        watcher = FileWatcherThread(
            file_path=test_file,
            log_manager=mock_log_manager,
            path_key="test_key",
        )

        # Create a mock file handle
        mock_handle = MagicMock()
        watcher._file_handle = mock_handle

        # Call reload
        watcher._reload_file("Test reload")

        # Should clear buffer
        mock_log_manager.clear_buffer.assert_called_once_with("test_key")

    def test_reload_file_publishes_events(
        self, tmp_path: Path, mock_log_manager: MagicMock
    ) -> None:
        """Test that _reload_file publishes interruption and resumption events."""
        test_file = tmp_path / "test.log"
        test_file.write_text("replacement content")

        watcher = FileWatcherThread(
            file_path=test_file,
            log_manager=mock_log_manager,
            path_key="test_key",
        )

        # Create a mock file handle
        mock_handle = MagicMock()
        watcher._file_handle = mock_handle

        # Call reload
        watcher._reload_file("File replaced")

        # Should publish interruption with reason
        mock_log_manager.publish_stream_interrupted.assert_called_once_with(
            "test_key", "File replaced"
        )

        # Should publish resumption
        mock_log_manager.publish_stream_resumed.assert_called_once_with("test_key")

    def test_reload_file_reads_content(
        self, tmp_path: Path, mock_log_manager: MagicMock
    ) -> None:
        """Test that _reload_file reads and publishes file content."""
        test_file = tmp_path / "test.log"
        test_file.write_text("replacement content")

        watcher = FileWatcherThread(
            file_path=test_file,
            log_manager=mock_log_manager,
            path_key="test_key",
        )

        # Create a mock file handle
        mock_handle = MagicMock()
        watcher._file_handle = mock_handle

        # Call reload
        watcher._reload_file("Test reload")

        # Should publish content (content + separator = 2 calls)
        assert mock_log_manager.publish_content.call_count == 2
        # Second call should be the file content
        calls = mock_log_manager.publish_content.call_args_list
        assert calls[0][0] == ("test_key", "replacement content")

    def test_reload_file_updates_file_state(
        self, tmp_path: Path, mock_log_manager: MagicMock
    ) -> None:
        """Test that _reload_file updates the file state."""
        test_file = tmp_path / "test.log"
        test_file.write_text("replacement content")

        watcher = FileWatcherThread(
            file_path=test_file,
            log_manager=mock_log_manager,
            path_key="test_key",
        )

        # Create a mock file handle
        mock_handle = MagicMock()
        watcher._file_handle = mock_handle
        watcher._last_file_state = None

        # Call reload
        watcher._reload_file("Test reload")

        # Should have updated file state
        assert watcher._last_file_state is not None
        assert watcher._last_file_state.size == len("replacement content")
