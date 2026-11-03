"""Caixas de mensagem no mesmo estilo das demais janelas."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton

from . import icons, theme
from .widgets import FramelessDialog, label

_KINDS = {
    "info": ("help", "accent"),
    "success": ("check", "success"),
    "warning": ("shield", "warning"),
    "error": ("close", "danger"),
    "question": ("help", "accent"),
}


class MessageDialog(FramelessDialog):
    def __init__(self, parent, title: str, text: str, kind: str = "info",
                 buttons=(("OK", "primary", True),), width: int = 400):
        super().__init__(title, width=width, parent=parent)
        self.choice = None
        pal = theme.palette()
        icon_name, color_attr = _KINDS.get(kind, _KINDS["info"])

        row = QHBoxLayout()
        row.setSpacing(14)
        ico = QLabel()
        ico.setPixmap(icons.pixmap(icon_name, getattr(pal, color_attr), 26))
        ico.setAlignment(Qt.AlignmentFlag.AlignTop)
        row.addWidget(ico, 0, Qt.AlignmentFlag.AlignTop)
        body = label(text, "body", wrap=True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setMinimumWidth(width - 110)
        row.addWidget(body, 1)
        self.body.addLayout(row)
        self.body.addSpacing(8)

        btns = QHBoxLayout()
        btns.addStretch()
        for text_, variant, value in buttons:
            btn = QPushButton(text_)
            btn.setProperty("variant", variant)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, v=value: self._choose(v))
            btns.addWidget(btn)
            if variant in ("primary", "danger"):
                btn.setDefault(True)
        self.body.addLayout(btns)

    def _choose(self, value):
        self.choice = value
        self.accept()


def info(parent, title: str, text: str):
    MessageDialog(parent, title, text, "info").exec()


def success(parent, title: str, text: str):
    MessageDialog(parent, title, text, "success").exec()


def warning(parent, title: str, text: str):
    MessageDialog(parent, title, text, "warning").exec()


def error(parent, title: str, text: str):
    MessageDialog(parent, title, text, "error").exec()


def confirm(parent, title: str, text: str, confirm_label: str = "Confirmar",
            cancel_label: str = "Cancelar", danger: bool = False) -> bool:
    dlg = MessageDialog(
        parent, title, text, "warning" if danger else "question",
        buttons=((cancel_label, "default", False),
                 (confirm_label, "danger" if danger else "primary", True)),
    )
    dlg.exec()
    return dlg.choice is True


def path_html(path) -> str:
    """Caminho com pontos de quebra após cada separador (caminhos longos não estouram)."""
    zwsp = "​"
    return str(path).replace("\\", "\\" + zwsp).replace("/", "/" + zwsp)


def describe(exc: BaseException) -> str:
    """Texto curto e legível para exibir um erro ao usuário."""
    text = str(exc) or exc.__class__.__name__
    return text.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
