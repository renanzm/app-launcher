"""Bottom bar: version info, progress and the big play/install button."""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QAbstractButton, QGridLayout, QHBoxLayout, QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from ..i18n import tr
from . import art, icons, theme
from .widgets import ElidedLabel, label


class PlayButton(QAbstractButton):
    """Large accent button (PLAY / INSTALL / UPDATE) painted with a gradient and a glow on hover."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(204, 56)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self._accent = QColor(theme.palette().accent)
        self._icon = "play"
        self._mode = "normal"           # normal | running | busy
        self._hover = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_hover_value)

    def _on_hover_value(self, value):
        self._hover = float(value)
        self.update()

    def set_accent(self, color: str):
        self._accent = QColor(color)
        self.update()

    def set_state(self, text: str, icon: str = "play", mode: str = "normal"):
        self.setText(text)
        self._icon, self._mode = icon, mode
        self.update()

    def _animate(self, end: float):
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(end)
        self._anim.start()

    def enterEvent(self, event):
        super().enterEvent(event)
        if self.isEnabled():
            self._animate(1.0)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._animate(0.0)

    def paintEvent(self, event):
        pal = theme.palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 8, 8)
        enabled = self.isEnabled() and self._mode == "normal"
        accent = self._accent

        if enabled:
            top = accent.lighter(int(112 + 14 * self._hover))
            bottom = accent.darker(int(122 - 10 * self._hover))
            if self.isDown():
                top, bottom = accent.darker(110), accent.darker(135)
            grad = QLinearGradient(r.topLeft(), r.bottomLeft())
            grad.setColorAt(0.0, top)
            grad.setColorAt(1.0, bottom)
            p.fillPath(path, grad)
            sheen = QLinearGradient(r.topLeft(), r.bottomLeft())
            sheen.setColorAt(0.0, QColor(255, 255, 255, 46))
            sheen.setColorAt(0.5, QColor(255, 255, 255, 0))
            p.fillPath(path, sheen)
            p.setPen(QPen(art.with_alpha(accent.lighter(150), 120 + int(80 * self._hover)), 1))
            p.drawPath(path)
            text_color = QColor(theme.on_color(accent.name()))
        elif self._mode == "running":
            p.fillPath(path, art.with_alpha(QColor(pal.success), 28))
            p.setPen(QPen(art.with_alpha(QColor(pal.success), 150), 1))
            p.drawPath(path)
            text_color = QColor(pal.success)
        else:
            p.fillPath(path, QColor(pal.surface_2))
            p.setPen(QPen(QColor(pal.border_strong), 1))
            p.drawPath(path)
            text_color = QColor(pal.faint if self._mode != "busy" else pal.muted)

        font = theme.display_font(16.5, QFont.Weight.Normal, spacing=2.0)
        p.setFont(font)
        metrics = p.fontMetrics()
        text = self.text().upper()
        icon_size = 18
        gap = 10
        total = icon_size + gap + metrics.horizontalAdvance(text)
        x = r.center().x() - total / 2
        icon_name = "check" if self._mode == "running" else self._icon
        pm = icons.pixmap(icon_name, text_color, icon_size)
        p.drawPixmap(int(x), int(r.center().y() - icon_size / 2), pm)
        p.setPen(text_color)
        p.drawText(QRectF(x + icon_size + gap, r.top(), total, r.height()),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        p.end()


class ProgressStrip(QWidget):
    """Thin progress bar with an accent gradient; indeterminate mode animates a moving segment."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._value: float | None = 0.0
        self._accent = QColor(theme.palette().accent)
        self._phase = 0.0
        self._spin = QVariantAnimation(self)
        self._spin.setStartValue(0.0)
        self._spin.setEndValue(1.0)
        self._spin.setDuration(1300)
        self._spin.setLoopCount(-1)
        self._spin.valueChanged.connect(self._on_phase)

    def _on_phase(self, value):
        self._phase = float(value)
        self.update()

    def set_accent(self, color: str):
        self._accent = QColor(color)
        self.update()

    def set_value(self, value: float | None):
        """0..1, or None for indeterminate."""
        self._value = value
        if value is None:
            if self._spin.state() != QVariantAnimation.State.Running:
                self._spin.start()
        else:
            self._spin.stop()
        self.update()

    def paintEvent(self, event):
        pal = theme.palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(0, 1, self.width(), 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(pal.surface_3))
        p.drawRoundedRect(track, 3, 3)
        if self._value is None:
            seg = track.width() * 0.28
            x = track.left() - seg + (track.width() + seg) * self._phase
            fill = QRectF(max(track.left(), x), track.top(),
                          min(x + seg, track.right()) - max(track.left(), x), track.height())
        else:
            fill = QRectF(track.left(), track.top(), track.width() * max(0.0, min(1.0, self._value)), track.height())
        if fill.width() > 0.5:
            grad = QLinearGradient(fill.topLeft(), fill.topRight())
            grad.setColorAt(0.0, self._accent.darker(115))
            grad.setColorAt(1.0, self._accent.lighter(135))
            glow = QRectF(fill).adjusted(-1, -1, 1, 1)
            p.setBrush(art.with_alpha(self._accent, 60))
            p.drawRoundedRect(glow, 4, 4)
            p.setBrush(grad)
            p.drawRoundedRect(fill, 3, 3)
        p.end()


class ActionBar(QWidget):
    """Info grid on the left, status/progress in the middle, options + play on the right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ActionBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedHeight(96)
        pal = theme.palette()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(34, 0, 22, 0)
        lay.setSpacing(22)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(3)
        self._values = {}
        for row, (key, text) in enumerate((("installed", tr("Installed")), ("latest", tr("Latest")),
                                           ("size", tr("Size")))):
            grid.addWidget(label(text, "info-label"), row, 0)
            value = label("—", "info-value")
            grid.addWidget(value, row, 1)
            self._values[key] = value
        info = QWidget()
        info.setLayout(grid)
        info.setFixedWidth(240)
        lay.addWidget(info, 0, Qt.AlignmentFlag.AlignVCenter)

        middle = QVBoxLayout()
        middle.setSpacing(7)
        middle.addStretch()
        top = QHBoxLayout()
        top.setSpacing(8)
        self.status = ElidedLabel("", "status")
        self.detail = label("", "status-detail")
        self.detail.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.status, 1)
        top.addWidget(self.detail)
        middle.addLayout(top)
        bar_row = QHBoxLayout()
        bar_row.setSpacing(8)
        self.progress = ProgressStrip()
        bar_row.addWidget(self.progress, 1)
        self.cancel = QToolButton()
        self.cancel.setObjectName("CancelButton")
        self.cancel.setIcon(icons.icon("close", pal.muted, 14))
        self.cancel.setIconSize(QSize(14, 14))
        self.cancel.setFixedSize(22, 22)
        self.cancel.setToolTip(tr("Cancel"))
        self.cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        bar_row.addWidget(self.cancel)
        middle.addLayout(bar_row)
        self.hint = ElidedLabel("", "status-detail", Qt.TextElideMode.ElideMiddle)
        middle.addWidget(self.hint)
        middle.addStretch()
        lay.addLayout(middle, 1)

        self.options = QToolButton()
        self.options.setObjectName("OptionsButton")
        self.options.setIcon(icons.icon("settings", pal.muted, 20, disabled_color=pal.faint))
        self.options.setIconSize(QSize(20, 20))
        self.options.setFixedSize(56, 56)
        self.options.setToolTip(tr("More options"))
        self.options.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self.options, 0, Qt.AlignmentFlag.AlignVCenter)

        self.play = PlayButton()
        lay.addWidget(self.play, 0, Qt.AlignmentFlag.AlignVCenter)
        self.set_busy(False)

    def set_info(self, key: str, text: str, color: str = ""):
        widget = self._values[key]
        widget.setText(text)
        widget.setStyleSheet(f"color: {color};" if color else "")

    def set_accent(self, color: str):
        self.play.set_accent(color)
        self.progress.set_accent(color)

    def set_busy(self, busy: bool, cancellable: bool = False):
        """While busy: status + percentage, progress bar, then transfer details in the hint line."""
        self.progress.setVisible(busy)
        self.cancel.setVisible(busy and cancellable)
        if not busy:
            self.progress.set_value(0.0)
            self.detail.setText("")
