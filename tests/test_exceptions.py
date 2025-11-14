"""Tests for custom exceptions."""

import pytest
from logarithmic.exceptions import FileAccessError
from logarithmic.exceptions import InvalidPathError
from logarithmic.exceptions import LogarithmicException


def test_base_exception() -> None:
    """Test that base exception can be raised and caught."""
    with pytest.raises(LogarithmicException):
        raise LogarithmicException("Test error")


def test_file_access_error() -> None:
    """Test FileAccessError exception."""
    with pytest.raises(FileAccessError) as exc_info:
        raise FileAccessError("Cannot read file")
    
    assert "Cannot read file" in str(exc_info.value)
    assert isinstance(exc_info.value, LogarithmicException)


def test_invalid_path_error() -> None:
    """Test InvalidPathError exception."""
    with pytest.raises(InvalidPathError) as exc_info:
        raise InvalidPathError("Invalid path provided")
    
    assert "Invalid path provided" in str(exc_info.value)
    assert isinstance(exc_info.value, LogarithmicException)


def test_exception_inheritance() -> None:
    """Test that all custom exceptions inherit from base exception."""
    assert issubclass(FileAccessError, LogarithmicException)
    assert issubclass(InvalidPathError, LogarithmicException)
