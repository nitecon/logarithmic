"""Content Controller - Unified content display and control management."""

import logging
from typing import Callable

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from logarithmic.fonts import FontManager
from logarithmic.log_highlighter import LogHighlighter

logger = logging.getLogger(__name__)


class ContentController:
    """Manages content display with consistent controls and behavior.

    Provides unified handling of:
    - Live/scroll mode
    - Pause/resume
    - Clear content
    - Status bar
    - Auto-scrolling
    - Line filtering
    """

    def __init__(
        self,
        fonts: FontManager,
        identifier: str,
        show_filename_in_status: bool = True,
        theme_colors: dict | None = None,
        prefix_lines: bool = False,
    ):
        """Initialize content controller.

        Args:
            fonts: Font manager instance
            identifier: Identifier for this content (filename or group name)
            show_filename_in_status: Whether to show filename in status bar
            theme_colors: Theme color settings
            prefix_lines: Whether to prefix each line with identifier (for combined mode)
        """
        self._fonts = fonts
        self._identifier = identifier
        self._show_filename = show_filename_in_status
        self._theme_colors = theme_colors or {}
        self._prefix_lines = prefix_lines

        # State
        self._is_live = True
        self._is_paused = False
        self._line_count = 0
        self._full_content: str = ""  # Store full content for filtering
        self._filter_text: str = ""
        self._filter_case_insensitive: bool = True
        self._filtered_line_count: int = 0

        # Widgets
        self._container: QWidget | None = None
        self._text_edit: QPlainTextEdit | None = None
        self._go_live_btn: QPushButton | None = None
        self._pause_btn: QPushButton | None = None
        self._clear_btn: QPushButton | None = None
        self._filter_input: QLineEdit | None = None
        self._filter_case_checkbox: QCheckBox | None = None
        self._filter_clear_btn: QPushButton | None = None
        self._status_bar: QLabel | None = None
        self._highlighter: LogHighlighter | None = None

        # Callbacks
        self._on_pause_callback: Callable[[bool], None] | None = None

    def create_widget(self) -> QWidget:
        """Create the content widget with controls.

        Returns:
            Container widget with text edit and controls
        """
        self._container = QWidget()
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)

        # Controls
        controls_layout = QHBoxLayout()

        # Go Live button (hidden by default)
        self._go_live_btn = QPushButton("Go Live")
        self._go_live_btn.setFont(self._fonts.get_ui_font(10, bold=True))
        self._go_live_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 0.4em 1.2em;
                border-radius: 0.3em;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self._go_live_btn.hide()
        self._go_live_btn.clicked.connect(self._on_go_live)
        controls_layout.addWidget(self._go_live_btn)

        # Pause button
        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setFont(self._fonts.get_ui_font(10))
        self._pause_btn.setCheckable(True)
        self._pause_btn.toggled.connect(self._on_pause_toggled)
        controls_layout.addWidget(self._pause_btn)

        # Clear button
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFont(self._fonts.get_ui_font(10))
        self._clear_btn.clicked.connect(self._on_clear)
        controls_layout.addWidget(self._clear_btn)

        # Separator
        separator = QLabel(" | ")
        separator.setFont(self._fonts.get_ui_font(10))
        controls_layout.addWidget(separator)

        # Filter label
        filter_label = QLabel("Filter:")
        filter_label.setFont(self._fonts.get_ui_font(10))
        controls_layout.addWidget(filter_label)

        # Filter input
        self._filter_input = QLineEdit()
        self._filter_input.setFont(self._fonts.get_ui_font(10))
        self._filter_input.setPlaceholderText("Type to filter lines...")
        self._filter_input.setMinimumWidth(150)
        self._filter_input.setMaximumWidth(250)
        self._filter_input.textChanged.connect(self._on_filter_changed)
        controls_layout.addWidget(self._filter_input)

        # Case insensitive checkbox
        self._filter_case_checkbox = QCheckBox("Ignore Case")
        self._filter_case_checkbox.setFont(self._fonts.get_ui_font(10))
        self._filter_case_checkbox.setChecked(True)
        self._filter_case_checkbox.toggled.connect(self._on_filter_case_changed)
        controls_layout.addWidget(self._filter_case_checkbox)

        # Clear filter button
        self._filter_clear_btn = QPushButton("✕")
        self._filter_clear_btn.setFont(self._fonts.get_ui_font(10))
        self._filter_clear_btn.setToolTip("Clear filter")
        self._filter_clear_btn.setMaximumWidth(30)
        self._filter_clear_btn.clicked.connect(self._on_filter_clear)
        controls_layout.addWidget(self._filter_clear_btn)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Text edit
        self._text_edit = QPlainTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._text_edit.setFont(self._fonts.get_mono_font(9))

        # Create syntax highlighter
        self._highlighter = LogHighlighter(
            self._text_edit.document(), self._theme_colors
        )

        # Connect scroll detection
        scrollbar = self._text_edit.verticalScrollBar()
        scrollbar.valueChanged.connect(self._on_scroll_changed)

        layout.addWidget(self._text_edit)

        # Status bar
        self._status_bar = QLabel()
        self._status_bar.setFont(self._fonts.get_ui_font(10))
        self._status_bar.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                color: #cccccc;
                padding: 0.4em;
                border-top: 1px solid #555555;
            }
        """)
        layout.addWidget(self._status_bar)

        self._update_status()
        return self._container

    def append_text(self, content: str, source: str | None = None) -> None:
        """Append text to the content view.

        Args:
            content: Text to append
            source: Optional source identifier for prefixing (used in combined mode)
        """
        if not self._text_edit or not content:
            return

        # Prefix lines if needed (for combined mode)
        if source and self._prefix_lines:
            lines = content.split("\n")
            prefixed_lines = [f"[{source}] {line}" if line else line for line in lines]
            content = "\n".join(prefixed_lines)

        # Count new lines
        new_lines = content.count("\n")
        self._line_count += new_lines

        # Store in full content buffer
        self._full_content += content

        # If filter is active, only append matching lines
        if self._filter_text:
            filtered_content = self._filter_content(content)
            if filtered_content:
                cursor = self._text_edit.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.insertText(filtered_content)
        else:
            # No filter, append directly
            cursor = self._text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(content)

        # Auto-scroll if in live mode
        if self._is_live:
            self._text_edit.verticalScrollBar().setValue(
                self._text_edit.verticalScrollBar().maximum()
            )

        self._update_status()

    def set_text(self, content: str) -> None:
        """Set the entire text content (replaces existing).

        Args:
            content: Text content to set
        """
        if not self._text_edit:
            return

        # Store full content
        self._full_content = content
        self._line_count = content.count("\n")

        # Apply filter if active
        if self._filter_text:
            filtered = self._filter_content(content)
            self._text_edit.setPlainText(filtered)
        else:
            self._text_edit.setPlainText(content)

        # Auto-scroll if in live mode
        if self._is_live:
            self._text_edit.moveCursor(QTextCursor.MoveOperation.End)

        self._update_status()

    def clear(self) -> None:
        """Clear the content view."""
        if not self._text_edit:
            return

        self._text_edit.clear()
        self._full_content = ""
        self._line_count = 0
        self._filtered_line_count = 0
        self._update_status()

    def get_text(self) -> str:
        """Get current text content (full unfiltered content).

        Returns:
            Full text content (not filtered)
        """
        return self._full_content

    def is_paused(self) -> bool:
        """Check if content is paused.

        Returns:
            True if paused
        """
        return self._is_paused

    def is_live(self) -> bool:
        """Check if in live mode.

        Returns:
            True if in live mode
        """
        return self._is_live

    def set_pause_callback(self, callback: Callable[[bool], None]) -> None:
        """Set callback for pause state changes.

        Args:
            callback: Function to call when pause state changes
        """
        self._on_pause_callback = callback

    def _on_scroll_changed(self) -> None:
        """Handle scroll position change."""
        if not self._text_edit:
            return

        scrollbar = self._text_edit.verticalScrollBar()
        is_at_bottom = scrollbar.value() >= scrollbar.maximum() - 10

        if not is_at_bottom and self._is_live:
            # User scrolled up, exit live mode
            self._is_live = False
            if self._go_live_btn:
                self._go_live_btn.show()
            self._update_status()
            logger.debug(f"Exited live mode for {self._identifier}")

    def _on_go_live(self) -> None:
        """Handle Go Live button click."""
        self._is_live = True
        if self._go_live_btn:
            self._go_live_btn.hide()

        # Scroll to bottom
        if self._text_edit:
            self._text_edit.moveCursor(QTextCursor.MoveOperation.End)

        self._update_status()
        logger.debug(f"Entered live mode for {self._identifier}")

    def _on_pause_toggled(self, checked: bool) -> None:
        """Handle Pause button toggle.

        Args:
            checked: Whether pause is enabled
        """
        self._is_paused = checked
        self._update_status()

        # Call callback if set
        if self._on_pause_callback:
            self._on_pause_callback(checked)

        logger.debug(
            f"Pause {'enabled' if checked else 'disabled'} for {self._identifier}"
        )

    def _on_clear(self) -> None:
        """Handle Clear button click."""
        self.clear()
        logger.debug(f"Cleared content for {self._identifier}")

    def _on_filter_changed(self, text: str) -> None:
        """Handle filter text change.

        Args:
            text: New filter text
        """
        self._filter_text = text
        self._apply_filter()

    def _on_filter_case_changed(self, checked: bool) -> None:
        """Handle case sensitivity checkbox change.

        Args:
            checked: Whether case insensitive is enabled
        """
        self._filter_case_insensitive = checked
        if self._filter_text:
            self._apply_filter()

    def _on_filter_clear(self) -> None:
        """Handle clear filter button click."""
        if self._filter_input:
            self._filter_input.clear()
        self._filter_text = ""
        self._apply_filter()

    def _filter_content(self, content: str) -> str:
        """Filter content to only include matching lines.

        Args:
            content: Content to filter

        Returns:
            Filtered content with only matching lines
        """
        if not self._filter_text:
            return content

        lines = content.split("\n")
        filter_text = self._filter_text

        if self._filter_case_insensitive:
            filter_text = filter_text.lower()
            matching_lines = [line for line in lines if filter_text in line.lower()]
        else:
            matching_lines = [line for line in lines if filter_text in line]

        return "\n".join(matching_lines)

    def _apply_filter(self) -> None:
        """Apply current filter to full content."""
        if not self._text_edit:
            return

        if self._filter_text:
            filtered = self._filter_content(self._full_content)
            self._text_edit.setPlainText(filtered)
            self._filtered_line_count = filtered.count("\n")
        else:
            self._text_edit.setPlainText(self._full_content)
            self._filtered_line_count = 0

        # Auto-scroll if in live mode
        if self._is_live:
            self._text_edit.moveCursor(QTextCursor.MoveOperation.End)

        self._update_status()
        logger.debug(f"Applied filter '{self._filter_text}' for {self._identifier}")

    def _update_status(self) -> None:
        """Update status bar text."""
        if not self._status_bar:
            return

        # Build status text
        parts = []

        if self._show_filename:
            parts.append(f"📄 {self._identifier}")

        if self._filter_text:
            parts.append(
                f"📊 {self._filtered_line_count:,}/{self._line_count:,} lines (filtered)"
            )
        else:
            parts.append(f"📊 {self._line_count:,} lines")

        mode = "🔴 LIVE" if self._is_live else "⏸ SCROLL"
        parts.append(mode)

        if self._is_paused:
            parts.append("[PAUSED]")

        status_text = "  |  ".join(parts)
        self._status_bar.setText(status_text)

    def set_log_font_size(self, size: int) -> None:
        """Set log content font size.

        Args:
            size: Font size in points
        """
        if self._text_edit:
            font = self._fonts.get_mono_font(size)
            self._text_edit.setFont(font)

    def set_ui_font_size(self, size: int) -> None:
        """Set UI elements font size.

        Args:
            size: Font size in points
        """
        font = self._fonts.get_ui_font(size)
        if self._pause_btn:
            self._pause_btn.setFont(font)
        if self._clear_btn:
            self._clear_btn.setFont(font)
        if self._go_live_btn:
            self._go_live_btn.setFont(self._fonts.get_ui_font(size, bold=True))
        if self._filter_input:
            self._filter_input.setFont(font)
        if self._filter_case_checkbox:
            self._filter_case_checkbox.setFont(font)
        if self._filter_clear_btn:
            self._filter_clear_btn.setFont(font)

    def set_status_font_size(self, size: int) -> None:
        """Set status bar font size.

        Args:
            size: Font size in points
        """
        if self._status_bar:
            font = self._fonts.get_ui_font(size)
            self._status_bar.setFont(font)

    def update_theme(self, theme_colors: dict) -> None:
        """Update theme colors.

        Args:
            theme_colors: New theme color dictionary
        """
        self._theme_colors = theme_colors
        if self._highlighter:
            self._highlighter.update_theme(theme_colors)
