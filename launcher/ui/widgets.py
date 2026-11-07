"""Componentes reutilizáveis: janela sem moldura, barra de título, toggle e tarefas."""

from __future__ import annotations

import traceback

from PyQt6.QtCore import (
    QEasingCurve, QPoint, QPropertyAnimation, QRectF, QSize, Qt, QThread,
    pyqtProperty, pyqtSignal,
)
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QToolButton,
    QVBoxLayout, QWidget,
)

from ..i18n import tr
from . import icons, theme

_SHADOW_MARGIN = 14


def label(text: str = "", role: str = "body", wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("role", role)
    lbl.setWordWrap(wrap)
    return lbl


def divider() -> QFrame:
    line = QFrame()
    line.setProperty("role", "divider")
    return line


def icon_button(name: str, tooltip: str, object_name: str = "IconButton", size: int = 18) -> QToolButton:
    pal = theme.palette()
    btn = QToolButton()
    btn.setObjectName(object_name)
    btn.setIcon(icons.icon(name, pal.muted, size, disabled_color=pal.faint))
    btn.setIconSize(QSize(size, size))
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedSize(size + 14, size + 14)
    return btn


class TitleBar(QWidget):
    """Barra superior arrastável com marca, título e botões à direita."""

    def __init__(self, title: str, show_mark: bool = True, parent=None):
        super().__init__(parent)
        self._drag_offset: QPoint | None = None
        self.layout_ = QHBoxLayout(self)
        self.layout_.setContentsMargins(16, 12, 10, 4)
        self.layout_.setSpacing(4)
        if show_mark:
            mark = QLabel()
            mark.setPixmap(icons.mark_pixmap(theme.palette().accent, 22))
            self.layout_.addWidget(mark)
            self.layout_.addSpacing(6)
        self.title = label(title, "window-title")
        self.layout_.addWidget(self.title)
        self.layout_.addStretch()

    def add_button(self, button: QWidget):
        self.layout_.addWidget(button)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            win = self.window()
            self._drag_offset = event.globalPosition().toPoint() - win.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None


class _FramelessMixin:
    """Monta o cartão arredondado com sombra e o fade-in de abertura."""

    def _setup_frame(self, title: str, width: int, show_mark: bool, closable: bool):
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(_SHADOW_MARGIN, _SHADOW_MARGIN, _SHADOW_MARGIN, _SHADOW_MARGIN)
        self.card = QFrame()
        self.card.setObjectName("Card")
        self.card.setFixedWidth(width)
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        self.title_bar = TitleBar(title, show_mark=show_mark)
        card_layout.addWidget(self.title_bar)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(20, 10, 20, 20)
        self.body.setSpacing(10)
        card_layout.addLayout(self.body)

        if closable:
            close = icon_button("close", tr("Close"), "CloseButton", 16)
            close.clicked.connect(self.close)
            self.title_bar.add_button(close)
            self.close_button = close

        self._fade = None

    def _fade_in(self):
        if self._fade is not None:
            return
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(220)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()


class FramelessWindow(_FramelessMixin, QWidget):
    def __init__(self, title: str, width: int = 440, parent=None):
        super().__init__(parent)
        self._setup_frame(title, width, show_mark=True, closable=False)

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_in()


class FramelessDialog(_FramelessMixin, QDialog):
    def __init__(self, title: str, width: int = 420, parent=None, closable: bool = True):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Dialog, True)
        self._setup_frame(title, width, show_mark=False, closable=closable)
        if closable:
            self.close_button.clicked.disconnect()
            self.close_button.clicked.connect(self.reject)

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_in()


class ToggleSwitch(QWidget):
    """Interruptor animado."""

    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._checked = checked
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animate: bool = False):
        if checked == self._checked:
            return
        self._checked = checked
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(1.0 if checked else 0.0)
            self._anim.start()
        else:
            self._pos = 1.0 if checked else 0.0
            self.update()
        self.toggled.emit(checked)

    def _get_knob(self):
        return self._pos

    def _set_knob(self, value):
        self._pos = value
        self.update()

    knob = pyqtProperty(float, _get_knob, _set_knob)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.setChecked(not self._checked, animate=True)

    def paintEvent(self, event):
        pal = theme.palette()
        off, on = QColor(pal.surface_3), QColor(pal.accent)
        t = self._pos
        track = QColor(
            int(off.red() + (on.red() - off.red()) * t),
            int(off.green() + (on.green() - off.green()) * t),
            int(off.blue() + (on.blue() - off.blue()) * t),
        )
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, 40, 22), 11, 11)
        p.fillPath(path, track)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(3 + 18 * t, 3, 16, 16))
        p.end()


class StatusDot(QWidget):
    def __init__(self, color: str = "#626A7B", parent=None):
        super().__init__(parent)
        self.setFixedSize(8, 8)
        self._color = QColor(color)

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(QRectF(0, 0, 8, 8))
        p.end()


class VersionTile(QFrame):
    """Cartão "rótulo + valor" com indicador colorido."""

    def __init__(self, caption: str, parent=None):
        super().__init__(parent)
        self.setProperty("role", "tile")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(6)
        self.dot = StatusDot()
        head.addWidget(self.dot)
        head.addWidget(label(caption.upper(), "overline"))
        head.addStretch()
        lay.addLayout(head)
        self.value = label("—", "value")
        lay.addWidget(self.value)

    def set_value(self, text: str, color: str):
        self.value.setText(text)
        self.dot.set_color(color)


# ---------------------------------------------------------------------------
# Trabalho em segundo plano
# ---------------------------------------------------------------------------

class TaskContext:
    """Repassado à função da tarefa para reportar progresso e status."""

    def __init__(self, task: "Task"):
        self._task = task

    def progress(self, value: int):
        self._task.progress.emit(int(value))

    def status(self, text: str):
        self._task.status.emit(text)


class Task(QThread):
    """Executa `fn(ctx)` fora da thread da interface.

    Os sinais são conectados com QueuedConnection, então os callbacks rodam
    sempre na thread da interface, mesmo sendo lambdas.
    """

    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(object)

    _running: set = set()

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            result = self._fn(TaskContext(self))
        except Exception as exc:  # noqa: BLE001 — repassado para a interface
            exc.__traceback_text__ = traceback.format_exc()
            self.failed.emit(exc)
        else:
            self.succeeded.emit(result)

    @classmethod
    def start_new(cls, parent, fn, on_success=None, on_error=None,
                  on_progress=None, on_status=None) -> "Task":
        task = cls(fn, parent)
        queued = Qt.ConnectionType.QueuedConnection
        if on_success:
            task.succeeded.connect(on_success, queued)
        if on_error:
            task.failed.connect(on_error, queued)
        if on_progress:
            task.progress.connect(on_progress, queued)
        if on_status:
            task.status.connect(on_status, queued)
        cls._running.add(task)

        def _cleanup():
            cls._running.discard(task)
            task.deleteLater()

        task.finished.connect(_cleanup, queued)
        task.start()
        return task
