"""Tela de abertura desenhada em código (marca + nome do launcher)."""

from __future__ import annotations

import time

from PyQt6.QtCore import QEasingCurve, QEventLoop, QPropertyAnimation, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

from . import icons, theme

MIN_DURATION_MS = 1200
FADE_MS = 220


class Splash(QWidget):
    def __init__(self, app_name: str, subtitle: str = "Carregando…"):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.SplashScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._name = app_name
        self._subtitle = subtitle
        self._phase = 0.0
        self.setFixedSize(340, 200)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._shown_at = None

    def _tick(self):
        self._phase = (self._phase + 0.018) % 1.0
        self.update()

    def paintEvent(self, event):
        pal = theme.palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(card, 18, 18)
        p.fillPath(path, QColor(pal.bg))
        p.setPen(QPen(QColor(pal.border), 1))
        p.drawPath(path)

        icons.paint_mark(p, QRectF(card.center().x() - 28, 34, 56, 56), QColor(pal.accent))

        font = QFont(theme.FONT_FAMILIES[0])
        font.setFamilies(theme.FONT_FAMILIES)
        font.setPointSizeF(13)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(QColor(pal.text))
        p.drawText(QRectF(0, 104, self.width(), 26), Qt.AlignmentFlag.AlignCenter, self._name)
        font.setPointSizeF(9)
        font.setWeight(QFont.Weight.Normal)
        p.setFont(font)
        p.setPen(QColor(pal.muted))
        p.drawText(QRectF(0, 130, self.width(), 20), Qt.AlignmentFlag.AlignCenter, self._subtitle)

        # Barra indeterminada.
        track = QRectF(110, 166, self.width() - 220, 4)
        bar = QPainterPath()
        bar.addRoundedRect(track, 2, 2)
        p.fillPath(bar, QColor(pal.surface_2))
        seg_w = track.width() * 0.35
        x = track.left() - seg_w + (track.width() + seg_w) * self._phase
        seg = QRectF(max(track.left(), x), track.top(),
                     min(x + seg_w, track.right()) - max(track.left(), x), track.height())
        if seg.width() > 0:
            seg_path = QPainterPath()
            seg_path.addRoundedRect(seg, 2, 2)
            p.fillPath(seg_path, QColor(pal.accent))
        p.end()

    def _animate_opacity(self, start: float, end: float):
        loop = QEventLoop()
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(FADE_MS)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(loop.quit)
        anim.start()
        loop.exec()

    def present(self):
        screen = self.screen().availableGeometry()
        self.move(screen.center() - self.rect().center())
        self.setWindowOpacity(0.0)
        self.show()
        self._timer.start(16)
        self._animate_opacity(0.0, 1.0)
        self.setWindowOpacity(1.0)
        self._shown_at = time.monotonic()

    def wait_minimum(self):
        """Garante o tempo mínimo de exibição sem bloquear o event loop."""
        if self._shown_at is None:
            return
        remaining = MIN_DURATION_MS - int((time.monotonic() - self._shown_at) * 1000)
        if remaining > 0:
            loop = QEventLoop()
            QTimer.singleShot(remaining, loop.quit)
            loop.exec()

    def dismiss(self):
        self._animate_opacity(self.windowOpacity(), 0.0)
        self._timer.stop()
        self.close()
