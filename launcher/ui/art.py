"""Artwork drawn in code: the stage backdrop, framed screenshots and avatars.

Apps without a banner still get a header with character: a backdrop built
from the app's accent colour (glows, a fine diagonal texture and the app's name
as a giant watermark), with the app's screenshot shown framed on the right.
"""

from __future__ import annotations

import hashlib

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QTransform,
)

from . import theme


def _seed(text: str) -> int:
    return int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16)


def shifted(color: QColor, degrees: int, saturation: float = 1.0, value: float = 1.0) -> QColor:
    h, s, v, a = color.getHsvF()
    h = 0.0 if h < 0 else h
    out = QColor.fromHsvF((h + degrees / 360.0) % 1.0, min(1.0, s * saturation), min(1.0, v * value), a)
    return out


def with_alpha(color: QColor | str, alpha: int) -> QColor:
    c = QColor(color)
    c.setAlpha(max(0, min(255, alpha)))
    return c


def draw_cover(p: QPainter, rect: QRectF, pixmap: QPixmap, focus_y: float = 0.35):
    """Draws `pixmap` filling `rect` (cropping the excess, like CSS background-size: cover)."""
    if pixmap.isNull():
        return
    pw = pixmap.width() / pixmap.devicePixelRatio()
    ph = pixmap.height() / pixmap.devicePixelRatio()
    scale = max(rect.width() / pw, rect.height() / ph)
    w, h = pw * scale, ph * scale
    x = rect.left() + (rect.width() - w) / 2
    y = rect.top() + (rect.height() - h) * focus_y
    p.drawPixmap(QRectF(x, y, w, h), pixmap, QRectF(0, 0, pixmap.width(), pixmap.height()))


def paint_backdrop(p: QPainter, rect: QRectF, accent: str, name: str):
    """Procedural backdrop for an app: dark base, accent glows, texture and a watermark."""
    pal = theme.palette()
    base = QColor(accent)
    seed = _seed(name)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.fillRect(rect, QColor(pal.bg))

    # Two soft glows: the accent on the right, a neighbouring hue lower down.
    w, h = rect.width(), rect.height()
    cx = rect.left() + w * (0.70 + (seed % 9) / 100.0)
    glow = QRadialGradient(QPointF(cx, rect.top() + h * 0.34), w * 0.62)
    glow.setColorAt(0.0, with_alpha(base, 120))
    glow.setColorAt(0.45, with_alpha(base, 38))
    glow.setColorAt(1.0, with_alpha(base, 0))
    p.fillRect(rect, glow)
    second = shifted(base, 38 if seed % 2 else -38, 1.0, 0.85)
    glow2 = QRadialGradient(QPointF(rect.left() + w * 0.18, rect.bottom() + h * 0.05), w * 0.55)
    glow2.setColorAt(0.0, with_alpha(second, 70))
    glow2.setColorAt(1.0, with_alpha(second, 0))
    p.fillRect(rect, glow2)

    # Fine diagonal texture, fading out towards the left.
    texture = QPixmap(int(w), int(h))
    texture.fill(Qt.GlobalColor.transparent)
    tp = QPainter(texture)
    tp.setRenderHint(QPainter.RenderHint.Antialiasing)
    tp.setPen(QPen(QColor(255, 255, 255, 16), 1))
    step = 18
    for i in range(-int(h), int(w), step):
        tp.drawLine(QPointF(i, h), QPointF(i + h, 0))
    tp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    fade = QLinearGradient(0, 0, w, 0)
    fade.setColorAt(0.0, QColor(0, 0, 0, 0))
    fade.setColorAt(0.45, QColor(0, 0, 0, 40))
    fade.setColorAt(1.0, QColor(0, 0, 0, 255))
    tp.fillRect(texture.rect(), fade)
    tp.end()
    p.drawPixmap(rect.topLeft(), texture)

    # Giant watermark with the app's name.
    font = QFont()
    font.setFamilies(theme.TITLE_FAMILIES)
    font.setPixelSize(int(h * 0.42))
    font.setWeight(QFont.Weight.Bold)
    p.setFont(font)
    p.setPen(QColor(255, 255, 255, 9))
    p.drawText(QRectF(rect.left() - w * 0.02, rect.top() + h * 0.30, w * 1.6, h * 0.7),
               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name.upper())
    p.restore()


def paint_screenshot(p: QPainter, area: QRectF, pixmap: QPixmap, accent: str, tilt: float = -7.0):
    """The app's screenshot, framed with a glow and a slight 3D tilt, fitted inside `area`."""
    if pixmap.isNull() or area.width() < 40 or area.height() < 40:
        return
    pw = pixmap.width() / pixmap.devicePixelRatio()
    ph = pixmap.height() / pixmap.devicePixelRatio()
    scale = min(area.width() / pw, area.height() / ph, 1.0)
    w, h = pw * scale, ph * scale
    target = QRectF(-w / 2, -h / 2, w, h)
    center = area.center()

    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    transform = QTransform()
    transform.translate(center.x(), center.y())
    transform.rotate(tilt, Qt.Axis.YAxis, 1400)
    p.setTransform(transform, True)

    # Glow: stacked translucent rounded rects (a cheap blur).
    accent_color = QColor(accent)
    for i in range(14, 0, -1):
        grow = i * 3.2
        path = QPainterPath()
        path.addRoundedRect(target.adjusted(-grow, -grow * 0.8, grow, grow * 1.1), 14 + grow, 14 + grow)
        p.fillPath(path, with_alpha(accent_color, 7))
    # Shadow under the frame.
    shadow = QPainterPath()
    shadow.addRoundedRect(target.translated(0, 14).adjusted(4, 4, -4, 6), 12, 12)
    p.fillPath(shadow, QColor(0, 0, 0, 120))

    frame = QPainterPath()
    frame.addRoundedRect(target, 10, 10)
    p.setClipPath(frame)
    p.drawPixmap(target, pixmap, QRectF(0, 0, pixmap.width(), pixmap.height()))
    # Sheen from the top-left corner.
    sheen = QLinearGradient(target.topLeft(), target.bottomRight())
    sheen.setColorAt(0.0, QColor(255, 255, 255, 26))
    sheen.setColorAt(0.35, QColor(255, 255, 255, 0))
    p.fillRect(target, sheen)
    p.setClipping(False)
    p.setPen(QPen(QColor(255, 255, 255, 40), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(frame)
    p.restore()


def paint_legibility(p: QPainter, rect: QRectF, dim: float = 0.0):
    """Gradients that keep text readable over any artwork (left, bottom and top)."""
    bg = QColor(theme.palette().bg)
    left = QLinearGradient(rect.left(), 0, rect.left() + rect.width() * 0.62, 0)
    left.setColorAt(0.0, with_alpha(bg, 235))
    left.setColorAt(0.55, with_alpha(bg, 120))
    left.setColorAt(1.0, with_alpha(bg, 0))
    p.fillRect(rect, left)
    bottom = QLinearGradient(0, rect.bottom(), 0, rect.top() + rect.height() * 0.42)
    bottom.setColorAt(0.0, with_alpha(bg, 255))
    bottom.setColorAt(0.35, with_alpha(bg, 190))
    bottom.setColorAt(1.0, with_alpha(bg, 0))
    p.fillRect(rect, bottom)
    top = QLinearGradient(0, rect.top(), 0, rect.top() + 110)
    top.setColorAt(0.0, with_alpha(bg, 170))
    top.setColorAt(1.0, with_alpha(bg, 0))
    p.fillRect(rect, top)
    if dim > 0:
        p.fillRect(rect, with_alpha(bg, int(255 * dim)))


def rounded(pixmap: QPixmap, size: int, radius: float, dpr: float = 2.0) -> QPixmap:
    """`pixmap` scaled to fill a size×size square with rounded corners."""
    out = QPixmap(int(size * dpr), int(size * dpr))
    out.setDevicePixelRatio(dpr)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    p.setClipPath(path)
    draw_cover(p, QRectF(0, 0, size, size), pixmap, 0.5)
    p.end()
    return out


def app_avatar(name: str, accent: str, size: int = 40, dpr: float = 2.0) -> QPixmap:
    """Gradient tile with the app's initials (used until a real icon is known)."""
    words = [w for w in name.replace("-", " ").split() if w[:1].isalnum()]
    initials = "".join(w[0] for w in words[:2]).upper() or "?"
    base = QColor(accent)
    out = QPixmap(int(size * dpr), int(size * dpr))
    out.setDevicePixelRatio(dpr)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), size * 0.24, size * 0.24)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, base.lighter(118))
    grad.setColorAt(1.0, shifted(base, 28, 1.0, 0.55))
    p.fillPath(path, grad)
    sheen = QLinearGradient(0, 0, 0, size)
    sheen.setColorAt(0.0, QColor(255, 255, 255, 50))
    sheen.setColorAt(0.5, QColor(255, 255, 255, 0))
    p.fillPath(path, sheen)
    font = QFont()
    font.setFamilies(theme.DISPLAY_FAMILIES)
    font.setPixelSize(int(size * 0.40))
    p.setFont(font)
    p.setPen(QColor(theme.on_color(accent)))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, initials)
    p.end()
    return out
