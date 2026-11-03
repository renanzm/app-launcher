"""Tema escuro único, aplicado no QApplication (todas as janelas herdam).

A cor de destaque vem de `accent_color` na configuração; o restante da
paleta é neutro, para o launcher combinar com qualquer marca.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QApplication, QWidget

from . import icons

FONT_FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Inter", "Arial"]


@dataclass(frozen=True)
class Palette:
    accent: str
    accent_hover: str
    accent_soft: str
    on_accent: str
    bg: str = "#0F1115"
    surface: str = "#161920"
    surface_2: str = "#1E222B"
    surface_3: str = "#262B36"
    border: str = "#2A2F3A"
    border_strong: str = "#3A4150"
    text: str = "#E9EBF1"
    muted: str = "#9AA1B1"
    faint: str = "#626A7B"
    success: str = "#3FB950"
    warning: str = "#D9A23A"
    danger: str = "#F2554B"


def make_palette(accent_hex: str) -> Palette:
    accent = QColor(accent_hex)
    # Texto escuro sobre cores claras, branco sobre as demais (WCAG, aproximado).
    r, g, b = accent.redF(), accent.greenF(), accent.blueF()
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    soft = QColor(accent)
    soft.setAlpha(40)
    return Palette(
        accent=accent.name(),
        accent_hover=accent.lighter(115).name(),
        accent_soft=f"rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.16)",
        on_accent="#0F1115" if luminance > 0.6 else "#FFFFFF",
    )


_palette: Palette | None = None


def palette() -> Palette:
    return _palette or make_palette("#7C5CFF")


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
    QDialog, QMessageBox {{ background-color: {pal.bg}; }}
    QLabel {{ background: transparent; }}
    QLabel[role="window-title"] {{ font-size: 10.5pt; font-weight: 600; }}
    QLabel[role="heading"] {{ font-size: 13pt; font-weight: 600; }}
    QLabel[role="subheading"] {{ font-size: 10.5pt; font-weight: 600; }}
    QLabel[role="body"] {{ color: {pal.text}; }}
    QLabel[role="muted"] {{ color: {pal.muted}; }}
    QLabel[role="caption"] {{ color: {pal.muted}; font-size: 8.5pt; }}
    QLabel[role="overline"] {{
        color: {pal.faint}; font-size: 7.5pt; font-weight: 700; letter-spacing: 1px;
    }}
    QLabel[role="value"] {{ font-size: 10.5pt; font-weight: 600; }}
    QLabel[role="callout"] {{
        color: {pal.muted}; background: {pal.surface}; border: 1px solid {pal.border};
        border-radius: 10px; padding: 10px 12px;
    }}
    QLabel[role="callout-warning"] {{
        color: {pal.warning}; background: rgba(217, 162, 58, 0.08);
        border: 1px solid rgba(217, 162, 58, 0.30); border-radius: 10px; padding: 10px 12px;
    }}

    QFrame[role="tile"] {{
        background: {pal.surface}; border: 1px solid {pal.border}; border-radius: 12px;
    }}
    QFrame[role="divider"] {{ background: {pal.border}; max-height: 1px; min-height: 1px; border: none; }}
    QFrame[role="option-card"] {{
        background: {pal.surface}; border: 1px solid {pal.border}; border-radius: 12px;
    }}
    QFrame[role="option-card"]:hover {{ border-color: {pal.accent}; background: {pal.surface_2}; }}

    QPushButton {{
        background: {pal.surface_2}; border: 1px solid {pal.border};
        border-radius: 10px; padding: 9px 16px; font-weight: 500;
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

    QComboBox {{
        background: {pal.surface}; border: 1px solid {pal.border}; border-radius: 12px;
        padding: 8px 12px; min-height: 40px;
    }}
    QComboBox:hover {{ border-color: {pal.border_strong}; background: {pal.surface_2}; }}
    QComboBox:disabled {{ color: {pal.faint}; }}
    QComboBox::drop-down {{ border: none; width: 34px; }}
    QComboBox::down-arrow {{ image: url({assets['chevron']}); width: 16px; height: 16px; }}
    QComboBox QAbstractItemView {{
        background: {pal.surface}; border: 1px solid {pal.border}; border-radius: 10px;
        padding: 4px; selection-background-color: {pal.accent_soft}; selection-color: {pal.text};
    }}
    QComboBox QAbstractItemView::item {{ min-height: 40px; padding: 2px 6px; border-radius: 8px; }}

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
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
        background: none; height: 0;
    }}

    QMenu {{
        background: {pal.surface}; border: 1px solid {pal.border}; border-radius: 10px; padding: 5px;
    }}
    QMenu::item {{ padding: 8px 18px 8px 10px; border-radius: 7px; }}
    QMenu::item:selected {{ background: {pal.surface_3}; }}
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
    """Altera uma propriedade usada nos seletores do QSS e reaplica o estilo."""
    widget.setProperty(prop, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
