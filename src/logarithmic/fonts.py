"""Font management - loads and provides custom fonts for the application."""

import logging
import platform
import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtGui import QFontDatabase

logger = logging.getLogger(__name__)


def get_platform_font_multiplier() -> float:
    """Get font size multiplier based on platform.

    macOS renders fonts smaller than Windows/Linux at the same point size,
    so we need to scale up on macOS for consistent appearance.

    Returns:
        Font size multiplier (1.0 = no scaling)
    """
    system = platform.system()
    if system == "Darwin":  # macOS
        return 1.3  # Scale up by 30% on macOS
    elif system == "Windows":
        return 1.0  # Windows baseline
    elif system == "Linux":
        return 1.0  # Linux similar to Windows
    else:
        return 1.0  # Default for unknown platforms


def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and PyInstaller bundles.

    Args:
        relative_path: Path relative to project root

    Returns:
        Absolute path to resource
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)  # type: ignore
        logger.debug(f"Running in PyInstaller bundle, base path: {base_path}")
    except AttributeError:
        # Not in a PyInstaller bundle (dev mode)
        # Go up from src/logarithmic/fonts.py to project root
        base_path = Path(__file__).parent.parent.parent
        logger.debug(f"Running in dev mode, base path: {base_path}")

    resource_path = base_path / relative_path
    logger.debug(f"Resource path for '{relative_path}': {resource_path}")
    return resource_path


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

        # Use resource path helper to find fonts in both dev and bundled modes
        self._font_dir = get_resource_path("fonts")
        self._michroma_id = None
        self._oxanium_id = None
        self._red_hat_mono_id = None

        # Get platform-specific font multiplier
        self._font_multiplier = get_platform_font_multiplier()
        logger.info(
            f"Platform: {platform.system()}, Font multiplier: {self._font_multiplier}"
        )

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

    def get_title_font(self, size: int = 13, bold: bool = False) -> QFont:
        """Get font for window titles and headers (Michroma).

        Args:
            size: Font size in points (will be scaled for platform)
            bold: Whether to make the font bold

        Returns:
            QFont configured for titles
        """
        scaled_size = int(size * self._font_multiplier)
        font = QFont("Michroma", scaled_size)
        if bold:
            font.setWeight(QFont.Weight.Bold)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        return font

    def get_ui_font(self, size: int = 13, bold: bool = False) -> QFont:
        """Get font for UI elements (Oxanium).

        Args:
            size: Font size in points (will be scaled for platform)
            bold: Whether to make the font bold

        Returns:
            QFont configured for UI elements
        """
        scaled_size = int(size * self._font_multiplier)
        font = QFont("Oxanium", scaled_size)
        if bold:
            font.setWeight(QFont.Weight.Bold)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        return font

    def get_mono_font(self, size: int = 13) -> QFont:
        """Get monospace font for log content (Red Hat Mono).

        Args:
            size: Font size in points (will be scaled for platform)

        Returns:
            QFont configured for monospace content
        """
        scaled_size = int(size * self._font_multiplier)
        font = QFont("Red Hat Mono", scaled_size)
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
