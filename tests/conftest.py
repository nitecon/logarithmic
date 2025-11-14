"""Pytest configuration and shared fixtures for Logarithmic tests."""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test files.

    Yields:
        Path to a temporary directory that will be cleaned up after the test.
    """
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_log_file(temp_dir: Path) -> Path:
    """Create a sample log file for testing.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        Path to the created log file.
    """
    log_file = temp_dir / "test.log"
    log_file.write_text(
        "2024-01-01 10:00:00 INFO Starting application\n"
        "2024-01-01 10:00:01 DEBUG Loading configuration\n"
        "2024-01-01 10:00:02 WARNING Missing optional setting\n"
        "2024-01-01 10:00:03 ERROR Failed to connect\n"
        "2024-01-01 10:00:04 INFO Retrying connection\n"
    )
    return log_file


@pytest.fixture
def mock_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mock the settings directory for testing.

    Args:
        tmp_path: Pytest's temporary path fixture
        monkeypatch: Pytest's monkeypatch fixture

    Returns:
        Path to the mocked settings directory.
    """
    settings_dir = tmp_path / ".logarithmic"
    settings_dir.mkdir(parents=True, exist_ok=True)

    # Mock the home directory to use tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    return settings_dir
