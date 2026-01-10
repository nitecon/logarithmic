"""Tests for the version checker module."""

from unittest.mock import patch


class TestVersionParsing:
    """Tests for version parsing and comparison functions."""

    def test_parse_version_simple(self) -> None:
        """Test parsing simple version strings."""
        from logarithmic.version_checker import parse_version

        assert parse_version("1.2.3") == ((1, 2, 3), False)
        assert parse_version("1.0.0") == ((1, 0, 0), False)
        assert parse_version("10.20.30") == ((10, 20, 30), False)

    def test_parse_version_with_v_prefix(self) -> None:
        """Test parsing version strings with 'v' prefix."""
        from logarithmic.version_checker import parse_version

        assert parse_version("v1.2.3") == ((1, 2, 3), False)
        assert parse_version("v1.0.0") == ((1, 0, 0), False)

    def test_parse_version_two_parts(self) -> None:
        """Test parsing version with only two parts."""
        from logarithmic.version_checker import parse_version

        assert parse_version("1.2") == ((1, 2), False)

    def test_parse_version_invalid_parts(self) -> None:
        """Test parsing version with invalid parts defaults to 0."""
        from logarithmic.version_checker import parse_version

        assert parse_version("1.2.beta") == ((1, 2, 0), False)
        assert parse_version("1.x.3") == ((1, 0, 3), False)

    def test_parse_version_dev_suffix(self) -> None:
        """Test parsing version with -dev suffix."""
        from logarithmic.version_checker import parse_version

        assert parse_version("1.2.8-dev") == ((1, 2, 8), True)
        assert parse_version("v1.2.8-dev") == ((1, 2, 8), True)


class TestVersionComparison:
    """Tests for version comparison function."""

    def test_is_newer_version_true(self) -> None:
        """Test that newer versions are detected."""
        from logarithmic.version_checker import is_newer_version

        assert is_newer_version("1.2.9", "1.2.8") is True
        assert is_newer_version("1.3.0", "1.2.8") is True
        assert is_newer_version("2.0.0", "1.2.8") is True

    def test_is_newer_version_false(self) -> None:
        """Test that older/same versions return False."""
        from logarithmic.version_checker import is_newer_version

        assert is_newer_version("1.2.8", "1.2.8") is False
        assert is_newer_version("1.2.7", "1.2.8") is False
        assert is_newer_version("1.1.9", "1.2.8") is False
        assert is_newer_version("0.9.9", "1.2.8") is False

    def test_is_newer_version_with_v_prefix(self) -> None:
        """Test version comparison with 'v' prefix."""
        from logarithmic.version_checker import is_newer_version

        assert is_newer_version("v1.2.9", "v1.2.8") is True
        assert is_newer_version("v1.2.8", "1.2.8") is False

    def test_is_newer_version_dev_suffix(self) -> None:
        """Test that dev versions are considered older than their base release."""
        from logarithmic.version_checker import is_newer_version

        # Dev version of 1.2.8 should see 1.2.8 release as newer
        assert is_newer_version("1.2.8", "1.2.8-dev") is True
        # Dev version should not see older release as newer
        assert is_newer_version("1.2.7", "1.2.8-dev") is False
        # Dev version should see newer release as newer
        assert is_newer_version("1.2.9", "1.2.8-dev") is True
        # Same dev versions are not newer
        assert is_newer_version("1.2.8-dev", "1.2.8-dev") is False


class TestGetCurrentVersion:
    """Tests for getting current version."""

    def test_get_current_version_from_env(self) -> None:
        """Test getting version from environment variable."""
        from logarithmic.version_checker import get_current_version

        with patch.dict("os.environ", {"APP_VERSION": "2.0.0"}):
            assert get_current_version() == "2.0.0"

    def test_get_current_version_strips_v_prefix(self) -> None:
        """Test that 'v' prefix is stripped from env version."""
        from logarithmic.version_checker import get_current_version

        with patch.dict("os.environ", {"APP_VERSION": "v2.0.0"}):
            assert get_current_version() == "2.0.0"

    def test_get_current_version_fallback(self) -> None:
        """Test fallback version when env and git unavailable."""
        from logarithmic.version_checker import get_current_version

        with patch.dict("os.environ", {}, clear=True):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = FileNotFoundError()
                version = get_current_version()
                # Should return fallback or git tag
                assert version is not None
                assert len(version) > 0


class TestVersionInfo:
    """Tests for VersionInfo dataclass."""

    def test_version_info_creation(self) -> None:
        """Test creating VersionInfo instance."""
        from logarithmic.version_checker import VersionInfo

        info = VersionInfo(
            tag_name="v1.2.8",
            version="1.2.8",
            html_url="https://github.com/Nitecon/logarithmic/releases/tag/v1.2.8",
            published_at="2026-01-10T00:00:00Z",
            body="Release notes here",
        )

        assert info.tag_name == "v1.2.8"
        assert info.version == "1.2.8"
        assert "github.com" in info.html_url
        assert info.body == "Release notes here"
