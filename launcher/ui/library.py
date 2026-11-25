"""Sidebar: the launcher's brand and the library of applications."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QAbstractButton, QButtonGroup, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from ..i18n import tr
from . import art, icons, theme
from .widgets import DragArea, ElidedLabel, label

TILE_HEIGHT = 64
ICON_SIZE = 38


class AppTile(QAbstractButton):
    """One application in the library: icon, name and a coloured status line."""

    def __init__(self, name: str, accent: str, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(TILE_HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setToolTip(name)
        self._name = name
        self._accent = accent
        self._icon = art.app_avatar(name, accent, ICON_SIZE)
        self._icon_source = None                  # cacheKey of the pixmap shown (None = initials)
        self._status = ""
        self._status_color = theme.palette().faint
        self._badge = False
        self._progress: float | None = None

    def sizeHint(self) -> QSize:
        return QSize(220, TILE_HEIGHT)

    def set_icon(self, pixmap: QPixmap | None):
        source = pixmap.cacheKey() if pixmap is not None else None
        if source == self._icon_source:
            return
        self._icon_source = source
        self._icon = (art.rounded(pixmap, ICON_SIZE, 9) if pixmap is not None
                      else art.app_avatar(self._name, self._accent, ICON_SIZE))
        self.update()

    def set_status(self, text: str, color: str, badge: bool = False, progress: float | None = None):
        self._status, self._status_color, self._badge, self._progress = text, color, badge, progress
        self.update()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        pal = theme.palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(10, 3, -10, -3)
        accent = QColor(self._accent)
        checked, hover = self.isChecked(), self.underMouse()

        path = QPainterPath()
        path.addRoundedRect(r, 9, 9)
        if checked:
            grad = QLinearGradient(r.topLeft(), r.topRight())
            grad.setColorAt(0.0, art.with_alpha(accent, 58))
            grad.setColorAt(1.0, art.with_alpha(QColor(pal.surface_2), 160))
            p.fillPath(path, grad)
            p.setPen(art.with_alpha(accent, 90))
            p.drawPath(path)
            bar = QPainterPath()
            bar.addRoundedRect(QRectF(0, r.top() + 12, 3.5, r.height() - 24), 1.75, 1.75)
            p.fillPath(bar, accent)
        elif hover:
            p.fillPath(path, QColor(pal.surface))

        icon_rect = QRectF(r.left() + 10, r.center().y() - ICON_SIZE / 2, ICON_SIZE, ICON_SIZE)
        if not checked:
            p.setOpacity(0.82 if hover else 0.7)
        p.drawPixmap(icon_rect.toRect(), self._icon)
        p.setOpacity(1.0)
        if self._badge:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(pal.chrome))
            p.drawEllipse(QRectF(icon_rect.right() - 9, icon_rect.top() - 4, 13, 13))
            p.setBrush(accent.lighter(115))
            p.drawEllipse(QRectF(icon_rect.right() - 6.5, icon_rect.top() - 1.5, 8, 8))

        text_left = icon_rect.right() + 12
        text_width = r.right() - text_left - 8
        font = QFont(self.font())
        font.setPointSizeF(10)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(QColor(pal.text if checked or hover else "#C3C8D2"))
        name = p.fontMetrics().elidedText(self._name, Qt.TextElideMode.ElideRight, int(text_width))
        p.drawText(QRectF(text_left, r.top() + 11, text_width, 20),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        font.setPointSizeF(8.5)
        font.setWeight(QFont.Weight.Normal)
        p.setFont(font)
        p.setPen(QColor(self._status_color))
        status = p.fontMetrics().elidedText(self._status, Qt.TextElideMode.ElideRight, int(text_width))
        p.drawText(QRectF(text_left, r.top() + 31, text_width, 18),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, status)

        if self._progress is not None:
            track = QRectF(text_left, r.bottom() - 7, text_width, 3)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(pal.surface_3))
            p.drawRoundedRect(track, 1.5, 1.5)
            fill = QRectF(track.left(), track.top(), track.width() * max(0.0, min(1.0, self._progress)), 3)
            p.setBrush(accent)
            p.drawRoundedRect(fill, 1.5, 1.5)
        p.end()


class Sidebar(QWidget):
    """Brand on top, the library in the middle, actions and version at the bottom."""

    app_selected = pyqtSignal(int)

    def __init__(self, title: str, subtitle: str, apps, accent_for, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedWidth(240)
        pal = theme.palette()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 14)
        lay.setSpacing(0)

        # -- brand (drags the window) ----------------------------------------
        brand = DragArea()
        brand.setFixedHeight(76)
        brand_lay = QHBoxLayout(brand)
        brand_lay.setContentsMargins(20, 6, 16, 0)
        brand_lay.setSpacing(12)
        mark = QLabel()
        mark.setPixmap(icons.mark_pixmap(pal.accent, 34))
        mark.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        brand_lay.addWidget(mark)
        names = QVBoxLayout()
        names.setSpacing(0)
        self.brand_title = ElidedLabel(title.upper(), "brand")
        self.brand_sub = label(subtitle, "brand-sub")
        for w in (self.brand_title, self.brand_sub):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        names.addStretch()
        names.addWidget(self.brand_title)
        names.addWidget(self.brand_sub)
        names.addStretch()
        brand_lay.addLayout(names, 1)
        lay.addWidget(brand)

        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {pal.border};")
        lay.addWidget(line)
        lay.addSpacing(16)

        section = QHBoxLayout()
        section.setContentsMargins(20, 0, 20, 6)
        section.addWidget(label(tr("LIBRARY"), "section"))
        section.addStretch()
        section.addWidget(label(str(len(apps)), "section"))
        lay.addLayout(section)

        # -- tiles ---------------------------------------------------------
        holder = QWidget()
        tiles_lay = QVBoxLayout(holder)
        tiles_lay.setContentsMargins(0, 0, 0, 0)
        tiles_lay.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.tiles: list[AppTile] = []
        for index, app in enumerate(apps):
            tile = AppTile(app.name, accent_for(app))
            self.group.addButton(tile, index)
            tiles_lay.addWidget(tile)
            self.tiles.append(tile)
        tiles_lay.addStretch()
        self.group.idClicked.connect(self.app_selected.emit)

        scroll = QScrollArea()
        scroll.setWidget(holder)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        lay.addWidget(scroll, 1)

        # -- bottom --------------------------------------------------------
        self.bottom = QVBoxLayout()
        self.bottom.setContentsMargins(16, 8, 16, 0)
        self.bottom.setSpacing(10)
        lay.addLayout(self.bottom)
        self.footer = label("", "faint", wrap=True)
        self.footer.setContentsMargins(4, 0, 4, 0)
        self.bottom.addWidget(self.footer)

    def add_action(self, button):
        self.bottom.insertWidget(self.bottom.count() - 1, button)

    def select(self, index: int):
        if 0 <= index < len(self.tiles):
            self.tiles[index].setChecked(True)
