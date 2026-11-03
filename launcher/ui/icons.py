"""Ícones de linha desenhados com QPainter (sem arquivos de imagem).

Cada ícone é desenhado num canvas lógico 24×24 e renderizado em QPixmap com
o devicePixelRatio da tela, então fica nítido em monitores com escala.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
)


def _pen(color: QColor, width: float = 1.8) -> QPen:
    pen = QPen(color)
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _settings(p: QPainter, c: QColor):
    p.setPen(_pen(c))
    path = QPainterPath()
    teeth, r_out, r_in = 8, 9.0, 6.6
    for i in range(teeth * 2):
        r = r_out if i % 2 == 0 else r_in
        for k in (-0.22, 0.22):
            a = math.radians((i + 0.5 + k) * 360 / (teeth * 2))
            pt = QPointF(12 + r * math.cos(a), 12 + r * math.sin(a))
            if i == 0 and k < 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
    path.closeSubpath()
    p.drawPath(path)
    p.drawEllipse(QPointF(12, 12), 2.8, 2.8)


def _download(p: QPainter, c: QColor):
    p.setPen(_pen(c))
    p.drawLine(QPointF(12, 4), QPointF(12, 14.5))
    p.drawPolyline([QPointF(7.5, 10.5), QPointF(12, 15), QPointF(16.5, 10.5)])
    p.drawPolyline([QPointF(4.5, 15.5), QPointF(4.5, 19.5), QPointF(19.5, 19.5), QPointF(19.5, 15.5)])


def _help(p: QPainter, c: QColor):
    p.setPen(_pen(c))
    p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
    path = QPainterPath(QPointF(9.4, 9.6))
    path.cubicTo(QPointF(9.4, 6.6), QPointF(14.8, 6.6), QPointF(14.8, 9.6))
    path.cubicTo(QPointF(14.8, 11.6), QPointF(12, 11.6), QPointF(12, 13.6))
    p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    p.drawEllipse(QPointF(12, 16.6), 1.1, 1.1)


def _minimize(p: QPainter, c: QColor):
    p.setPen(_pen(c, 1.6))
    p.drawLine(QPointF(7, 12.5), QPointF(17, 12.5))


def _close(p: QPainter, c: QColor):
    p.setPen(_pen(c, 1.6))
    p.drawLine(QPointF(7.5, 7.5), QPointF(16.5, 16.5))
    p.drawLine(QPointF(16.5, 7.5), QPointF(7.5, 16.5))


def _play(p: QPainter, c: QColor):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    path = QPainterPath(QPointF(8, 5.5))
    path.lineTo(QPointF(18.5, 12))
    path.lineTo(QPointF(8, 18.5))
    path.closeSubpath()
    p.drawPath(path)


def _refresh(p: QPainter, c: QColor):
    p.setPen(_pen(c))
    rect = QRectF(4.5, 4.5, 15, 15)
    path = QPainterPath()
    path.arcMoveTo(rect, 60)
    path.arcTo(rect, 60, 280)
    p.drawPath(path)
    p.drawPolyline([QPointF(15.5, 3.2), QPointF(16.2, 6.4), QPointF(13, 7.2)])


def _more(p: QPainter, c: QColor):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    for x in (6, 12, 18):
        p.drawEllipse(QPointF(x, 12), 1.6, 1.6)


def _folder(p: QPainter, c: QColor):
    p.setPen(_pen(c))
    path = QPainterPath(QPointF(3.5, 7))
    path.lineTo(3.5, 18.5)
    path.lineTo(20.5, 18.5)
    path.lineTo(20.5, 8.5)
    path.lineTo(11.5, 8.5)
    path.lineTo(9.5, 5.5)
    path.lineTo(4.5, 5.5)
    path.closeSubpath()
    p.drawPath(path)


def _box(p: QPainter, c: QColor):
    p.setPen(_pen(c))
    path = QPainterPath(QPointF(12, 3.5))
    path.lineTo(20, 7.5)
    path.lineTo(20, 16.5)
    path.lineTo(12, 20.5)
    path.lineTo(4, 16.5)
    path.lineTo(4, 7.5)
    path.closeSubpath()
    p.drawPath(path)
    p.drawPolyline([QPointF(4, 7.5), QPointF(12, 11.5), QPointF(20, 7.5)])
    p.drawLine(QPointF(12, 11.5), QPointF(12, 20.5))


def _shield(p: QPainter, c: QColor):
    p.setPen(_pen(c))
    path = QPainterPath(QPointF(12, 3.5))
    path.lineTo(19, 6.5)
    path.cubicTo(QPointF(19, 13), QPointF(16.5, 17.5), QPointF(12, 20.5))
    path.cubicTo(QPointF(7.5, 17.5), QPointF(5, 13), QPointF(5, 6.5))
    path.closeSubpath()
    p.drawPath(path)
    p.drawPolyline([QPointF(9, 12), QPointF(11.2, 14.2), QPointF(15.2, 10)])


def _trash(p: QPainter, c: QColor):
    p.setPen(_pen(c))
    p.drawLine(QPointF(4.5, 7), QPointF(19.5, 7))
    p.drawPolyline([QPointF(9.5, 7), QPointF(9.5, 4.5), QPointF(14.5, 4.5), QPointF(14.5, 7)])
    path = QPainterPath(QPointF(6.5, 7))
    path.lineTo(7.5, 19.5)
    path.lineTo(16.5, 19.5)
    path.lineTo(17.5, 7)
    p.drawPath(path)


def _wrench(p: QPainter, c: QColor):
    p.setPen(_pen(c))
    path = QPainterPath(QPointF(14.5, 4.2))
    path.cubicTo(QPointF(11.5, 3.6), QPointF(9, 6.6), QPointF(10.2, 9.6))
    path.lineTo(4.6, 15.2)
    path.cubicTo(QPointF(3.6, 16.2), QPointF(3.6, 18.4), QPointF(4.8, 19.4))
    path.cubicTo(QPointF(5.8, 20.4), QPointF(7.8, 20.4), QPointF(8.8, 19.4))
    path.lineTo(14.4, 13.8)
    path.cubicTo(QPointF(17.4, 15), QPointF(20.4, 12.5), QPointF(19.8, 9.5))
    path.lineTo(17, 12.3)
    path.lineTo(14.2, 11.6)
    path.lineTo(13.5, 8.8)
    path.closeSubpath()
    p.drawPath(path)


def _chevron_down(p: QPainter, c: QColor):
    p.setPen(_pen(c, 2.0))
    p.drawPolyline([QPointF(7, 10), QPointF(12, 15), QPointF(17, 10)])


def _check(p: QPainter, c: QColor):
    p.setPen(_pen(c, 2.6))
    p.drawPolyline([QPointF(6, 12.5), QPointF(10.2, 16.5), QPointF(18, 8)])


def _user(p: QPainter, c: QColor):
    p.setPen(_pen(c))
    p.drawEllipse(QPointF(12, 8.5), 3.8, 3.8)
    path = QPainterPath(QPointF(4.8, 20))
    path.cubicTo(QPointF(5.5, 15.5), QPointF(8.5, 14), QPointF(12, 14))
    path.cubicTo(QPointF(15.5, 14), QPointF(18.5, 15.5), QPointF(19.2, 20))
    p.drawPath(path)


def _lock(p: QPainter, c: QColor):
    p.setPen(_pen(c))
    p.drawRoundedRect(QRectF(5, 10.5, 14, 10), 2.2, 2.2)
    path = QPainterPath(QPointF(8.2, 10.5))
    path.lineTo(8.2, 8)
    path.cubicTo(QPointF(8.2, 3.2), QPointF(15.8, 3.2), QPointF(15.8, 8))
    path.lineTo(15.8, 10.5)
    p.drawPath(path)


_PAINTERS = {
    "settings": _settings, "download": _download, "help": _help,
    "minimize": _minimize, "close": _close, "play": _play, "refresh": _refresh,
    "more": _more, "folder": _folder, "box": _box, "shield": _shield,
    "trash": _trash, "wrench": _wrench, "chevron-down": _chevron_down,
    "check": _check, "user": _user, "lock": _lock,
}


def pixmap(name: str, color: str | QColor, size: int = 18, dpr: float = 2.0) -> QPixmap:
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 24.0, size / 24.0)
    p.setBrush(Qt.BrushStyle.NoBrush)
    _PAINTERS[name](p, QColor(color))
    p.end()
    return pm


def icon(name: str, color: str | QColor, size: int = 18,
         disabled_color: str | QColor | None = None) -> QIcon:
    ic = QIcon()
    ic.addPixmap(pixmap(name, color, size), QIcon.Mode.Normal)
    if disabled_color is not None:
        ic.addPixmap(pixmap(name, disabled_color, size), QIcon.Mode.Disabled)
    return ic


# ---------------------------------------------------------------------------
# Marca do launcher e avatares de aplicativo
# ---------------------------------------------------------------------------

def paint_mark(p: QPainter, rect: QRectF, accent: QColor):
    """Marca do launcher: quadrado arredondado em gradiente com um "play" em camadas."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = rect.width()
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0.0, accent.lighter(135))
    grad.setColorAt(1.0, accent.darker(140))
    tile = QPainterPath()
    tile.addRoundedRect(rect, s * 0.26, s * 0.26)
    p.fillPath(tile, grad)

    def chevron(offset: float, alpha: int):
        path = QPainterPath()
        x0 = rect.left() + s * (0.30 + offset)
        path.moveTo(x0, rect.top() + s * 0.27)
        path.lineTo(x0 + s * 0.30, rect.top() + s * 0.50)
        path.lineTo(x0, rect.top() + s * 0.73)
        pen = QPen(QColor(255, 255, 255, alpha))
        pen.setWidthF(max(1.5, s * 0.105))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    chevron(-0.04, 110)
    chevron(0.14, 255)
    p.restore()


def mark_pixmap(accent: str | QColor, size: int = 64, dpr: float = 2.0) -> QPixmap:
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    paint_mark(p, QRectF(0, 0, size, size), QColor(accent))
    p.end()
    return pm


def avatar_pixmap(text: str, accent: str | QColor, size: int = 36, dpr: float = 2.0) -> QPixmap:
    """Avatar com as iniciais do aplicativo (fallback quando não há ícone)."""
    words = [w for w in text.replace("-", " ").split() if w[:1].isalnum()]
    initials = "".join(w[0] for w in words[:2]).upper() or "?"
    base = QColor(accent)
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    bg = QColor(base)
    bg.setAlpha(46)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), size * 0.28, size * 0.28)
    p.fillPath(path, bg)
    font = p.font()
    font.setPixelSize(int(size * 0.38))
    font.setWeight(font.Weight.DemiBold)
    p.setFont(font)
    p.setPen(base.lighter(150))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, initials)
    p.end()
    return pm
