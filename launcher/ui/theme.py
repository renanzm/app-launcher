"""Single dark theme, applied on the QApplication (every window inherits it).

The accent colour comes from `accent_color` in the configuration (each app may
bring its own accent for its page); the rest of the palette is neutral, so the
launcher fits any brand. Headings use Bahnschrift — the condensed DIN face that
ships with Windows — for the game-launcher look, with Segoe UI for body text.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QApplication, QWidget

from . import icons

FONT_FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Inter", "Arial"]
DISPLAY_FAMILIES = ["Bahnschrift SemiBold SemiCondensed", "Bahnschrift", "Segoe UI Variable Display",
                    "Segoe UI Semibold", "Segoe UI"]
TITLE_FAMILIES = ["Bahnschrift Condensed", "Bahnschrift SemiBold Condensed", "Bahnschrift",
                  "Segoe UI Black", "Segoe UI"]


def _qss_families(families) -> str:
    return ", ".join(f'"{f}"' for f in families)


@dataclass(frozen=True)
class Palette:
    accent: str
    accent_hover: str
    accent_soft: str
    on_accent: str
    bg: str = "#0B0D12"
    chrome: str = "#0E1016"          # sidebar and action bar
    surface: str = "#141720"
    surface_2: str = "#1B1F29"
    surface_3: str = "#252A36"
    border: str = "#1F2430"
    border_strong: str = "#353C4B"
    text: str = "#ECEEF3"
    muted: str = "#9AA1B1"
    faint: str = "#5F6676"
    success: str = "#3FB950"
    warning: str = "#E0A43A"
    danger: str = "#F2554B"


def on_color(hex_color: str) -> str:
    """Dark text on light colours, white on the rest (WCAG, approximate)."""
    c = QColor(hex_color)
    luminance = 0.2126 * c.redF() + 0.7152 * c.greenF() + 0.0722 * c.blueF()
    return "#0B0D12" if luminance > 0.55 else "#FFFFFF"


def make_palette(accent_hex: str) -> Palette:
    accent = QColor(accent_hex)
    return Palette(
        accent=accent.name(),
        accent_hover=accent.lighter(115).name(),
        accent_soft=f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.16)",
        on_accent=on_color(accent_hex),
    )


_palette: Palette | None = None


def palette() -> Palette:
    return _palette or make_palette("#7C5CFF")


def display_font(point_size: float, weight: QFont.Weight = QFont.Weight.Normal,
                 families=None, spacing: float = 0.0) -> QFont:
    font = QFont()
    font.setFamilies(list(families or DISPLAY_FAMILIES))
    font.setPointSizeF(point_size)
    font.setWeight(weight)
    if spacing:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def _asset_dir() -> Path:
    path = Path(tempfile.gettempdir()) / "app-launcher-theme"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _qss_url(path: Path) -> str:
    return path.as_posix()


def _render_assets(pal: Palette) -> dict:
    folder = _asset_dir()
    out = {}
    for name, icon_name, color, size in (
        ("chevron", "chevron-down", pal.muted, 16),
        ("check", "check", pal.on_accent, 14),
    ):
        path = folder / f"{name}-{color.strip('#')}.png"
        if not path.exists():
            icons.pixmap(icon_name, color, size, dpr=2.0).save(str(path), "PNG")
        out[name] = _qss_url(path)
    return out


def stylesheet(pal: Palette, assets: dict) -> str:
    display = _qss_families(DISPLAY_FAMILIES)
    title = _qss_families(TITLE_FAMILIES)
    return f"""
    * {{
        color: {pal.text};
        outline: none;
    }}
    QWidget#Card {{
        background-color: {pal.bg};
        border: 1px solid {pal.border};
        border-radius: 16px;
    }}
    QWidget#LauncherWindow {{ background-color: {pal.bg}; }}
    QDialog, QMessageBox {{ background-color: {pal.bg}; }}
    QLabel {{ background: transparent; }}
    QLabel[role="window-title"] {{ font-size: 10.5pt; font-weight: 600; }}
    QLabel[role="heading"] {{ font-size: 13pt; font-weight: 600; }}
    QLabel[role="subheading"] {{ font-size: 10.5pt; font-weight: 600; }}
    QLabel[role="body"] {{ color: {pal.text}; }}
    QLabel[role="muted"] {{ color: {pal.muted}; }}
    QLabel[role="caption"] {{ color: {pal.muted}; font-size: 8.5pt; }}
    QLabel[role="faint"] {{ color: {pal.faint}; font-size: 8.5pt; }}
    QLabel[role="overline"] {{
        color: {pal.faint}; font-family: {display}; font-size: 8.5pt; letter-spacing: 1.5px;
    }}
    QLabel[role="value"] {{ font-size: 10.5pt; font-weight: 600; }}
    QLabel[role="callout"] {{
        color: {pal.muted}; background: {pal.surface}; border: 1px solid {pal.border};
        border-radius: 10px; padding: 10px 12px;
    }}
    QLabel[role="callout-warning"] {{
        color: {pal.warning}; background: rgba(224, 164, 58, 0.08);
        border: 1px solid rgba(224, 164, 58, 0.30); border-radius: 10px; padding: 10px 12px;
    }}

    /* -- launcher window ------------------------------------------------ */
    QWidget#Sidebar {{ background: {pal.chrome}; border-right: 1px solid {pal.border}; }}
    QWidget#ActionBar {{ background: {pal.chrome}; border-top: 1px solid {pal.border}; }}
    QLabel[role="brand"] {{ font-family: {display}; font-size: 12.5pt; letter-spacing: 1px; }}
    QLabel[role="brand-sub"] {{ color: {pal.faint}; font-size: 8pt; }}
    QLabel[role="section"] {{
        color: {pal.faint}; font-family: {display}; font-size: 8.5pt; letter-spacing: 2px;
    }}
    QPushButton[role="nav"] {{
        background: transparent; border: none; border-radius: 0;
        border-bottom: 2px solid transparent;
        color: {pal.muted}; font-family: {display}; font-size: 11.5pt; letter-spacing: 1px;
        padding: 0 2px; margin: 0 9px; min-height: 54px; max-height: 54px;
    }}
    QPushButton[role="nav"]:hover {{ color: {pal.text}; background: transparent; }}
    QPushButton[role="nav"]:checked {{ color: {pal.text}; border-bottom: 2px solid {pal.accent}; }}
    QPushButton[role="nav"]:disabled {{ color: {pal.faint}; background: transparent; border-color: transparent; }}
    QPushButton[role="sidebar-action"] {{
        background: transparent; border: 1px solid {pal.border}; border-radius: 8px;
        color: {pal.muted}; font-family: {display}; font-size: 10pt; letter-spacing: 1px;
        padding: 9px 12px; text-align: left;
    }}
    QPushButton[role="sidebar-action"]:hover {{
        color: {pal.text}; background: {pal.surface}; border-color: {pal.border_strong};
    }}
    QLabel[role="hero-title"] {{
        font-family: {title}; font-size: 40pt; font-weight: 700; letter-spacing: 1px;
    }}
    QLabel[role="hero-tagline"] {{ color: #D9DCE4; font-size: 12pt; }}
    QLabel[role="hero-text"] {{ color: {pal.muted}; font-size: 10pt; }}
    QLabel[role="chip"] {{
        background: rgba(255, 255, 255, 0.07); border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 11px; padding: 3px 10px; color: #D5D9E2; font-size: 8.5pt;
    }}
    QLabel[role="chip-warning"] {{
        background: rgba(224, 164, 58, 0.12); border: 1px solid rgba(224, 164, 58, 0.35);
        border-radius: 11px; padding: 3px 10px; color: {pal.warning}; font-size: 8.5pt;
    }}
    QFrame[role="glass"] {{
        background: rgba(9, 11, 15, 0.80); border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
    }}
    QFrame[role="glass"][clickable="true"]:hover {{
        background: rgba(16, 19, 26, 0.88); border-color: rgba(255, 255, 255, 0.20);
    }}
    QLabel[role="card-title"] {{ font-family: {display}; font-size: 12pt; }}
    QLabel[role="card-text"] {{ color: {pal.muted}; font-size: 9pt; }}
    QLabel[role="info-label"] {{ color: {pal.faint}; font-size: 9pt; }}
    QLabel[role="info-value"] {{ color: {pal.text}; font-size: 9pt; font-weight: 600; }}
    QLabel[role="status"] {{ color: {pal.muted}; font-size: 9pt; }}
    QLabel[role="status-detail"] {{ color: {pal.faint}; font-size: 8.5pt; }}

    QTextBrowser[role="notes"] {{
        background: transparent; border: none; color: {pal.text};
        selection-background-color: {pal.accent}; selection-color: {pal.on_accent};
    }}
    QListWidget[role="releases"] {{
        background: transparent; border: none; border-right: 1px solid {pal.border};
        border-radius: 0; padding: 6px 8px 6px 0;
    }}
    QListWidget[role="releases"]::item {{ padding: 0; margin: 2px 0; border-radius: 8px; }}
    QListWidget[role="releases"]::item:hover {{ background: {pal.surface}; }}
    QListWidget[role="releases"]::item:selected {{ background: {pal.surface_2}; }}

    /* -- generic widgets ----------------------------------------------- */
    QFrame[role="tile"] {{
        background: {pal.surface}; border: 1px solid {pal.border}; border-radius: 12px;
    }}
    QFrame[role="divider"] {{ background: {pal.border}; max-height: 1px; min-height: 1px; border: none; }}

    QPushButton {{
        background: {pal.surface_2}; border: 1px solid {pal.border};
        border-radius: 8px; padding: 9px 16px; font-weight: 500;
    }}
    QPushButton:hover {{ background: {pal.surface_3}; border-color: {pal.border_strong}; }}
    QPushButton:pressed {{ background: {pal.surface}; }}
    QPushButton:disabled {{ color: {pal.faint}; background: {pal.surface}; border-color: {pal.surface_2}; }}
    QPushButton[variant="primary"] {{
        background: {pal.accent}; border: 1px solid {pal.accent}; color: {pal.on_accent};
        font-weight: 600;
    }}
    QPushButton[variant="primary"]:hover {{ background: {pal.accent_hover}; border-color: {pal.accent_hover}; }}
    QPushButton[variant="primary"]:disabled {{
        background: {pal.surface_2}; border-color: {pal.border}; color: {pal.faint};
    }}
    QPushButton[variant="danger"] {{ color: {pal.danger}; }}
    QPushButton[variant="danger"]:hover {{ background: rgba(242, 85, 75, 0.12); border-color: rgba(242, 85, 75, 0.5); }}
    QPushButton[segment="left"] {{ border-top-right-radius: 0; border-bottom-right-radius: 0; }}
    QPushButton[segment="right"] {{
        border-top-left-radius: 0; border-bottom-left-radius: 0; border-left: none;
        padding: 9px 10px;
    }}

    QToolButton#IconButton {{ background: transparent; border: none; border-radius: 8px; padding: 5px; }}
    QToolButton#IconButton:hover {{ background: {pal.surface_2}; }}
    QToolButton#IconButton:pressed {{ background: {pal.surface_3}; }}
    QToolButton#CloseButton {{ background: transparent; border: none; border-radius: 8px; padding: 5px; }}
    QToolButton#CloseButton:hover {{ background: #C42B1C; }}
    QToolButton#WindowButton {{ background: transparent; border: none; border-radius: 0; }}
    QToolButton#WindowButton:hover {{ background: rgba(255, 255, 255, 0.08); }}
    QToolButton#WindowClose {{ background: transparent; border: none; border-radius: 0; }}
    QToolButton#WindowClose:hover {{ background: #C42B1C; }}
    QToolButton#OptionsButton {{
        background: {pal.surface_2}; border: 1px solid {pal.border_strong}; border-radius: 8px;
    }}
    QToolButton#OptionsButton:hover {{ background: {pal.surface_3}; }}
    QToolButton#OptionsButton:disabled {{ background: {pal.surface}; border-color: {pal.border}; }}
    QToolButton#CancelButton {{ background: transparent; border: none; border-radius: 6px; }}
    QToolButton#CancelButton:hover {{ background: rgba(242, 85, 75, 0.18); }}

    QComboBox {{
        background: {pal.surface}; border: 1px solid {pal.border}; border-radius: 10px;
        padding: 6px 12px; min-height: 26px;
    }}
    QComboBox:hover {{ border-color: {pal.border_strong}; background: {pal.surface_2}; }}
    QComboBox:disabled {{ color: {pal.faint}; }}
    QComboBox::drop-down {{ border: none; width: 30px; }}
    QComboBox::down-arrow {{ image: url({assets['chevron']}); width: 16px; height: 16px; }}
    QComboBox QAbstractItemView {{
        background: {pal.surface}; border: 1px solid {pal.border}; border-radius: 10px;
        padding: 4px; selection-background-color: {pal.accent_soft}; selection-color: {pal.text};
    }}
    QComboBox QAbstractItemView::item {{ min-height: 32px; padding: 2px 6px; border-radius: 8px; }}

    QLineEdit {{
        background: {pal.surface}; border: 1px solid {pal.border}; border-radius: 10px;
        padding: 9px 12px; selection-background-color: {pal.accent}; selection-color: {pal.on_accent};
    }}
    QLineEdit:hover {{ border-color: {pal.border_strong}; }}
    QLineEdit:focus {{ border-color: {pal.accent}; }}
    QLineEdit[role="code"] {{ font-size: 15pt; font-weight: 600; letter-spacing: 3px; }}

    QCheckBox {{ spacing: 8px; color: {pal.muted}; }}
    QCheckBox::indicator {{
        width: 16px; height: 16px; border-radius: 5px;
        border: 1px solid {pal.border_strong}; background: {pal.surface};
    }}
    QCheckBox::indicator:hover {{ border-color: {pal.accent}; }}
    QCheckBox::indicator:checked {{
        background: {pal.accent}; border-color: {pal.accent}; image: url({assets['check']});
    }}

    QProgressBar {{
        background: {pal.surface_2}; border: none; border-radius: 3px;
        min-height: 6px; max-height: 6px;
    }}
    QProgressBar::chunk {{ background: {pal.accent}; border-radius: 3px; }}

    QTreeWidget, QListWidget {{
        background: {pal.surface}; border: 1px solid {pal.border}; border-radius: 12px;
        padding: 4px; alternate-background-color: {pal.surface};
    }}
    QTreeWidget::item, QListWidget::item {{ padding: 7px 6px; border-radius: 8px; }}
    QTreeWidget::item:hover, QListWidget::item:hover {{ background: {pal.surface_2}; }}
    QTreeWidget::item:selected, QListWidget::item:selected {{
        background: {pal.accent_soft}; color: {pal.text};
    }}
    QTreeWidget::indicator, QListWidget::indicator {{
        width: 16px; height: 16px; border-radius: 5px;
        border: 1px solid {pal.border_strong}; background: {pal.bg};
    }}
    QTreeWidget::indicator:checked, QListWidget::indicator:checked {{
        background: {pal.accent}; border-color: {pal.accent}; image: url({assets['check']});
    }}
    QHeaderView {{ background: transparent; border: none; }}
    QHeaderView::section {{
        background: transparent; color: {pal.faint}; border: none;
        border-bottom: 1px solid {pal.border}; padding: 6px 8px;
        font-size: 8pt; font-weight: 700;
    }}

    QTabBar::tab {{
        background: transparent; color: {pal.muted}; border: none;
        padding: 7px 14px; margin-right: 4px; border-radius: 8px;
    }}
    QTabBar::tab:hover {{ color: {pal.text}; background: {pal.surface_2}; }}
    QTabBar::tab:selected {{ color: {pal.text}; background: {pal.accent_soft}; }}
    QTabWidget::pane {{ border: none; }}

    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {pal.surface_3}; border-radius: 3px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {pal.border_strong}; }}
    QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {pal.surface_3}; border-radius: 3px; min-width: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
        background: none; height: 0; width: 0;
    }}

    QMenu {{
        background: {pal.surface}; border: 1px solid {pal.border_strong}; border-radius: 10px; padding: 5px;
    }}
    QMenu::item {{ padding: 8px 22px 8px 10px; border-radius: 7px; }}
    QMenu::item:selected {{ background: {pal.surface_3}; }}
    QMenu::item:disabled {{ color: {pal.faint}; }}
    QMenu::icon {{ padding-left: 8px; }}
    QMenu::separator {{ height: 1px; background: {pal.border}; margin: 4px 6px; }}

    QToolTip {{
        background: {pal.surface_2}; color: {pal.text}; border: 1px solid {pal.border};
        border-radius: 6px; padding: 5px 8px;
    }}
    QMessageBox QLabel {{ color: {pal.text}; }}
    QMessageBox QPushButton {{ min-width: 84px; }}
    """


def apply(app: QApplication, accent_hex: str):
    global _palette
    _palette = make_palette(accent_hex)
    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setPointSizeF(9.5)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(font)
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet(_palette, _render_assets(_palette)))


def set_role(widget: QWidget, prop: str, value: str):
    """Changes a property used by the QSS selectors and re-applies the style."""
    widget.setProperty(prop, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
