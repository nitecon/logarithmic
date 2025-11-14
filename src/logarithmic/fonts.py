"""Font management - loads and provides custom fonts for the application."""

import logging
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtGui import QFontDatabase

logger = logging.getLogger(__name__)


class FontManager:
    """Manages custom fonts for the application.

    Fonts used:
    - Michroma: Window titles and headers
    - Oxanium: UI elements (buttons, labels, status bar)
    - Red Hat Mono: Log content display
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        """Singleton pattern to ensure fonts are loaded only once."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize font manager and load custom fonts."""
        if self._initialized:
            return

        self._font_dir = Path(__file__).parent.parent.parent / "fonts"
        self._michroma_id = None
        self._oxanium_id = None
        self._red_hat_mono_id = None

        self._load_fonts()
        self._initialized = True

    def _load_fonts(self) -> None:
        """Load all custom fonts from the fonts directory."""
        # Load Michroma (for titles)
        michroma_path = self._font_dir / "Michroma" / "Michroma-Regular.ttf"
        if michroma_path.exists():
            self._michroma_id = QFontDatabase.addApplicationFont(str(michroma_path))
            if self._michroma_id != -1:
                families = QFontDatabase.applicationFontFamilies(self._michroma_id)
                logger.info(f"Loaded Michroma font: {families}")
            else:
                logger.error(f"Failed to load Michroma font from {michroma_path}")
        else:
            logger.warning(f"Michroma font not found at {michroma_path}")

        # Load Oxanium (for UI elements)
        oxanium_path = self._font_dir / "Oxanium" / "Oxanium-VariableFont_wght.ttf"
        if oxanium_path.exists():
            self._oxanium_id = QFontDatabase.addApplicationFont(str(oxanium_path))
            if self._oxanium_id != -1:
                families = QFontDatabase.applicationFontFamilies(self._oxanium_id)
                logger.info(f"Loaded Oxanium font: {families}")
            else:
                logger.error(f"Failed to load Oxanium font from {oxanium_path}")
        else:
            logger.warning(f"Oxanium font not found at {oxanium_path}")

        # Load Red Hat Mono (for log content)
        red_hat_path = (
            self._font_dir / "Red_Hat_Mono" / "RedHatMono-VariableFont_wght.ttf"
        )
        if red_hat_path.exists():
            self._red_hat_mono_id = QFontDatabase.addApplicationFont(str(red_hat_path))
            if self._red_hat_mono_id != -1:
                families = QFontDatabase.applicationFontFamilies(self._red_hat_mono_id)
                logger.info(f"Loaded Red Hat Mono font: {families}")
            else:
                logger.error(f"Failed to load Red Hat Mono font from {red_hat_path}")
        else:
            logger.warning(f"Red Hat Mono font not found at {red_hat_path}")

    def get_title_font(self, size: int = 12, bold: bool = False) -> QFont:
        """Get font for window titles and headers (Michroma).

        Args:
            size: Font size in points
            bold: Whether to make the font bold

        Returns:
            QFont configured for titles
        """
        font = QFont("Michroma", size)
        if bold:
            font.setWeight(QFont.Weight.Bold)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        return font

    def get_ui_font(self, size: int = 10, bold: bool = False) -> QFont:
        """Get font for UI elements (Oxanium).

        Args:
            size: Font size in points
            bold: Whether to make the font bold

        Returns:
            QFont configured for UI elements
        """
        font = QFont("Oxanium", size)
        if bold:
            font.setWeight(QFont.Weight.Bold)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        return font

    def get_mono_font(self, size: int = 9) -> QFont:
        """Get monospace font for log content (Red Hat Mono).

        Args:
            size: Font size in points

        Returns:
            QFont configured for monospace content
        """
        font = QFont("Red Hat Mono", size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        return font


# Global instance
_font_manager = None


def get_font_manager() -> FontManager:
    """Get the global FontManager instance.

    Returns:
        FontManager singleton instance
    """
    global _font_manager
    if _font_manager is None:
        _font_manager = FontManager()
    return _font_manager
