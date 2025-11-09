"""Content Controller - Unified content display and control management."""

import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from logarithmic.fonts import FontManager

logger = logging.getLogger(__name__)


class ContentController:
    """Manages content display with consistent controls and behavior.
    
    Provides unified handling of:
    - Live/scroll mode
    - Pause/resume
    - Clear content
    - Status bar
    - Auto-scrolling
    """
    
    def __init__(
        self,
        fonts: FontManager,
        identifier: str,
        show_filename_in_status: bool = True
    ):
        """Initialize content controller.
        
        Args:
            fonts: Font manager instance
            identifier: Identifier for this content (filename or group name)
            show_filename_in_status: Whether to show filename in status bar
        """
        self._fonts = fonts
        self._identifier = identifier
        self._show_filename = show_filename_in_status
        
        # State
        self._is_live = True
        self._is_paused = False
        self._line_count = 0
        
        # Widgets
        self._container: QWidget | None = None
        self._text_edit: QPlainTextEdit | None = None
        self._go_live_btn: QPushButton | None = None
        self._pause_btn: QPushButton | None = None
        self._clear_btn: QPushButton | None = None
        self._status_bar: QLabel | None = None
        
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
                padding: 5px 15px;
                border-radius: 3px;
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
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Text edit
        self._text_edit = QPlainTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._text_edit.setFont(self._fonts.get_mono_font(9))
        
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
                padding: 5px;
                border-top: 1px solid #555555;
            }
        """)
        layout.addWidget(self._status_bar)
        
        self._update_status()
        return self._container
    
    def append_text(self, content: str) -> None:
        """Append text to the content view.
        
        Args:
            content: Text content to append
        """
        if not self._text_edit or self._is_paused:
            return
        
        # Count lines
        self._line_count += content.count('\n')
        
        # Append content
        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(content)
        self._text_edit.setTextCursor(cursor)
        
        # Auto-scroll if in live mode
        if self._is_live:
            self._text_edit.moveCursor(QTextCursor.MoveOperation.End)
        
        self._update_status()
    
    def set_text(self, content: str) -> None:
        """Set the entire text content (replaces existing).
        
        Args:
            content: Text content to set
        """
        if not self._text_edit:
            return
        
        self._text_edit.setPlainText(content)
        self._line_count = content.count('\n')
        
        # Auto-scroll if in live mode
        if self._is_live:
            self._text_edit.moveCursor(QTextCursor.MoveOperation.End)
        
        self._update_status()
    
    def clear(self) -> None:
        """Clear the content view."""
        if not self._text_edit:
            return
        
        self._text_edit.clear()
        self._line_count = 0
        self._update_status()
    
    def get_text(self) -> str:
        """Get current text content.
        
        Returns:
            Current text content
        """
        if not self._text_edit:
            return ""
        return self._text_edit.toPlainText()
    
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
        
        logger.debug(f"Pause {'enabled' if checked else 'disabled'} for {self._identifier}")
    
    def _on_clear(self) -> None:
        """Handle Clear button click."""
        self.clear()
        logger.debug(f"Cleared content for {self._identifier}")
    
    def _update_status(self) -> None:
        """Update status bar text."""
        if not self._status_bar:
            return
        
        # Build status text
        parts = []
        
        if self._show_filename:
            parts.append(f"📄 {self._identifier}")
        
        parts.append(f"📊 {self._line_count:,} lines")
        
        mode = "🔴 LIVE" if self._is_live else "⏸ SCROLL"
        parts.append(mode)
        
        if self._is_paused:
            parts.append("[PAUSED]")
        
        status_text = "  |  ".join(parts)
        self._status_bar.setText(status_text)
