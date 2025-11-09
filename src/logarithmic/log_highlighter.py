"""Log syntax highlighter for colorizing log lines based on keywords."""

import logging
import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtGui import QSyntaxHighlighter
from PySide6.QtGui import QTextCharFormat

logger = logging.getLogger(__name__)


class LogHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for log content.
    
    Highlights log lines based on keywords:
    - Error keywords: Red
    - Warning keywords: Orange
    - Verbose keywords: Gray
    - Default: Normal color
    """
    
    def __init__(self, document, theme_colors: dict):
        """Initialize the highlighter.
        
        Args:
            document: QTextDocument to highlight
            theme_colors: Dictionary with color settings
        """
        super().__init__(document)
        
        self._theme_colors = theme_colors
        self._update_formats()
        
        # Keywords to match (case-insensitive)
        self._error_keywords = [
            'error', 'fatal', 'critical', 'exception', 'fail', 'failed', 'failure'
        ]
        self._warning_keywords = [
            'warning', 'warn', 'caution', 'deprecated'
        ]
        self._verbose_keywords = [
            'verbose', 'debug', 'trace'
        ]
    
    def _update_formats(self) -> None:
        """Update text formats based on theme colors."""
        # Error format
        self._error_format = QTextCharFormat()
        self._error_format.setForeground(QColor(self._theme_colors.get("error_color", "#FF4444")))
        
        # Warning format
        self._warning_format = QTextCharFormat()
        self._warning_format.setForeground(QColor(self._theme_colors.get("warning_color", "#FFA500")))
        
        # Verbose format
        self._verbose_format = QTextCharFormat()
        self._verbose_format.setForeground(QColor(self._theme_colors.get("verbose_color", "#888888")))
        
        # Default format
        self._default_format = QTextCharFormat()
        self._default_format.setForeground(QColor(self._theme_colors.get("default_color", "#CCCCCC")))
    
    def update_theme(self, theme_colors: dict) -> None:
        """Update theme colors and rehighlight.
        
        Args:
            theme_colors: New theme color dictionary
        """
        self._theme_colors = theme_colors
        self._update_formats()
        self.rehighlight()
    
    def highlightBlock(self, text: str) -> None:
        """Highlight a single block (line) of text.
        
        Args:
            text: Text to highlight
        """
        if not text:
            return
        
        # Convert to lowercase for case-insensitive matching
        text_lower = text.lower()
        
        # Check for error keywords
        for keyword in self._error_keywords:
            if keyword in text_lower:
                self.setFormat(0, len(text), self._error_format)
                return
        
        # Check for warning keywords
        for keyword in self._warning_keywords:
            if keyword in text_lower:
                self.setFormat(0, len(text), self._warning_format)
                return
        
        # Check for verbose keywords
        for keyword in self._verbose_keywords:
            if keyword in text_lower:
                self.setFormat(0, len(text), self._verbose_format)
                return
        
        # Default color
        self.setFormat(0, len(text), self._default_format)
