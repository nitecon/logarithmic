"""Tests for the ContentController filtering functionality."""

from unittest.mock import MagicMock


class TestContentControllerFiltering:
    """Tests for ContentController filter methods."""

    def test_filter_content_empty_filter(self) -> None:
        """Test that empty filter returns original content."""
        from logarithmic.content_controller import ContentController
        from logarithmic.fonts import FontManager

        fonts = MagicMock(spec=FontManager)
        controller = ContentController(fonts, "test.log")

        content = "Line 1\nLine 2\nLine 3"
        controller._filter_text = ""

        result = controller._filter_content(content)
        assert result == content

    def test_filter_content_case_insensitive(self) -> None:
        """Test case-insensitive filtering."""
        from logarithmic.content_controller import ContentController
        from logarithmic.fonts import FontManager

        fonts = MagicMock(spec=FontManager)
        controller = ContentController(fonts, "test.log")

        content = "ERROR: Something failed\nINFO: All good\nerror: lowercase"
        controller._filter_text = "error"
        controller._filter_case_insensitive = True

        result = controller._filter_content(content)
        lines = result.split("\n")

        assert len(lines) == 2
        assert "ERROR: Something failed" in lines
        assert "error: lowercase" in lines

    def test_filter_content_case_sensitive(self) -> None:
        """Test case-sensitive filtering."""
        from logarithmic.content_controller import ContentController
        from logarithmic.fonts import FontManager

        fonts = MagicMock(spec=FontManager)
        controller = ContentController(fonts, "test.log")

        content = "ERROR: Something failed\nINFO: All good\nerror: lowercase"
        controller._filter_text = "ERROR"
        controller._filter_case_insensitive = False

        result = controller._filter_content(content)
        lines = result.split("\n")

        assert len(lines) == 1
        assert "ERROR: Something failed" in lines

    def test_filter_content_no_matches(self) -> None:
        """Test filtering with no matches returns empty."""
        from logarithmic.content_controller import ContentController
        from logarithmic.fonts import FontManager

        fonts = MagicMock(spec=FontManager)
        controller = ContentController(fonts, "test.log")

        content = "Line 1\nLine 2\nLine 3"
        controller._filter_text = "NOTFOUND"
        controller._filter_case_insensitive = True

        result = controller._filter_content(content)
        assert result == ""

    def test_filter_content_partial_match(self) -> None:
        """Test filtering matches partial strings."""
        from logarithmic.content_controller import ContentController
        from logarithmic.fonts import FontManager

        fonts = MagicMock(spec=FontManager)
        controller = ContentController(fonts, "test.log")

        content = "Application started\nUser logged in\nApplication stopped"
        controller._filter_text = "Application"
        controller._filter_case_insensitive = True

        result = controller._filter_content(content)
        lines = result.split("\n")

        assert len(lines) == 2
        assert "Application started" in lines
        assert "Application stopped" in lines

    def test_get_text_returns_full_content(self) -> None:
        """Test that get_text returns full unfiltered content."""
        from logarithmic.content_controller import ContentController
        from logarithmic.fonts import FontManager

        fonts = MagicMock(spec=FontManager)
        controller = ContentController(fonts, "test.log")

        controller._full_content = "Full content here"
        controller._filter_text = "something"

        result = controller.get_text()
        assert result == "Full content here"

    def test_clear_resets_filter_state(self) -> None:
        """Test that clear resets all content and filter state."""
        from logarithmic.content_controller import ContentController
        from logarithmic.fonts import FontManager

        fonts = MagicMock(spec=FontManager)
        controller = ContentController(fonts, "test.log")

        # Set up state
        controller._full_content = "Some content"
        controller._line_count = 10
        controller._filtered_line_count = 5
        controller._text_edit = MagicMock()

        controller.clear()

        assert controller._full_content == ""
        assert controller._line_count == 0
        assert controller._filtered_line_count == 0


class TestContentControllerState:
    """Tests for ContentController state management."""

    def test_is_paused_default(self) -> None:
        """Test default paused state is False."""
        from logarithmic.content_controller import ContentController
        from logarithmic.fonts import FontManager

        fonts = MagicMock(spec=FontManager)
        controller = ContentController(fonts, "test.log")

        assert controller.is_paused() is False

    def test_is_live_default(self) -> None:
        """Test default live state is True."""
        from logarithmic.content_controller import ContentController
        from logarithmic.fonts import FontManager

        fonts = MagicMock(spec=FontManager)
        controller = ContentController(fonts, "test.log")

        assert controller.is_live() is True

    def test_filter_state_initialization(self) -> None:
        """Test filter state is properly initialized."""
        from logarithmic.content_controller import ContentController
        from logarithmic.fonts import FontManager

        fonts = MagicMock(spec=FontManager)
        controller = ContentController(fonts, "test.log")

        assert controller._filter_text == ""
        assert controller._filter_case_insensitive is True
        assert controller._filtered_line_count == 0
        assert controller._full_content == ""
