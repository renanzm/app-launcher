"""Central de ajuda e builds personalizadas (entregas por ticket em pastas isoladas)."""

from __future__ import annotations

import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout,
)

from . import icons, messages, theme
from .widgets import FramelessDialog, label


class _OptionCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, icon_name: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setProperty("role", "option-card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)
        ico = QLabel()
        ico.setPixmap(icons.pixmap(icon_name, theme.palette().accent, 22))
        lay.addWidget(ico, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(label(title, "subheading"))
        texts.addWidget(label(subtitle, "caption", wrap=True))
        lay.addLayout(texts, 1)
        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()


class HelpMenuDialog(FramelessDialog):
    """Escolha entre reportar um problema e instalar/abrir builds personalizadas."""

    def __init__(self, app, support_url: str, has_builds: bool, parent=None):
        super().__init__("Ajuda e suporte", width=420, parent=parent)
        self.choice = None
        self.body.addWidget(label("Como podemos ajudar?", "heading"))
        self.body.addSpacing(4)

        if support_url:
            self._add("help", "Reportar um problema",
                      "Abre a página de suporte no navegador.", "report")
        cb = app.custom_builds
        if cb is not None:
            self._add("download", "Instalar build personalizada",
                      f"Baixa a versão preparada para um {cb.code_label.lower()} específico, "
                      "sem mexer na instalação oficial.", "install")
            if has_builds:
                self._add("wrench", "Builds instaladas",
                          "Abre ou remove as builds personalizadas deste aplicativo.", "manage")

    def _add(self, icon_name, title, subtitle, choice):
        card = _OptionCard(icon_name, title, subtitle)
        card.clicked.connect(lambda: self._choose(choice))
        self.body.addWidget(card)

    def _choose(self, choice: str):
        self.choice = choice
        self.accept()


class BuildCodeDialog(FramelessDialog):
    """Pede o código (ticket) da build personalizada."""

    def __init__(self, custom_builds, parent=None):
        super().__init__("Build personalizada", width=380, parent=parent)
        self.code = ""
        self._pattern = custom_builds.code_pattern
        self.body.addWidget(label(f"Código do {custom_builds.code_label.lower()}", "heading"))
        self.body.addWidget(label(custom_builds.code_hint, "muted", wrap=True))

        self.input = QLineEdit()
        self.input.setProperty("role", "code")
        self.input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input.setMaxLength(40)
        self.input.setValidator(QRegularExpressionValidator(QRegularExpression(r"[A-Za-z0-9_.-]*")))
        self.input.textChanged.connect(self._validate)
        self.input.returnPressed.connect(self._try_accept)
        self.body.addWidget(self.input)

        row = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton("Buscar")
        self.btn_ok.setProperty("variant", "primary")
        self.btn_ok.setEnabled(False)
        self.btn_ok.clicked.connect(self._try_accept)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(self.btn_ok)
        self.body.addSpacing(4)
        self.body.addLayout(row)
        self.input.setFocus()

    def _valid(self, text: str) -> bool:
        return re.fullmatch(self._pattern, text) is not None

    def _validate(self, text: str):
        self.btn_ok.setEnabled(self._valid(text.strip()))

    def _try_accept(self):
        text = self.input.text().strip()
        if self._valid(text):
            self.code = text
            self.accept()


class BuildInfoDialog(FramelessDialog):
    """Mostra os metadados da build encontrada e confirma a instalação."""

    def __init__(self, app, code: str, info: dict, installed_id: str = "", parent=None):
        super().__init__("Build personalizada", width=430, parent=parent)
        cb = app.custom_builds
        self.body.addWidget(label(f"{cb.code_label} {code}", "heading"))
        self.body.addWidget(label(app.name, "muted"))
        self.body.addSpacing(4)

        for caption, key in (("Data", "date"), ("Versão base", "base_version"), ("Identificador", "id")):
            value = str(info.get(key) or "").strip()
            if not value:
                continue
            row = QHBoxLayout()
            cap = label(caption, "muted")
            cap.setFixedWidth(110)
            row.addWidget(cap)
            row.addWidget(label(value, "value", wrap=True), 1)
            self.body.addLayout(row)

        description = str(info.get("description") or "").strip() or "Sem descrição."
        desc = label(description, "callout", wrap=True)
        self.body.addWidget(desc)

        if installed_id:
            note = (f"Já existe uma build instalada para este código (<i>{installed_id}</i>). "
                    "Instalar de novo substitui essa pasta.")
            role = "callout-warning"
        else:
            note = ("A build é instalada numa <b>pasta separada</b>, sem afetar a instalação "
                    "oficial nem outras builds.")
            role = "callout"
        hint = label(note, role, wrap=True)
        hint.setTextFormat(Qt.TextFormat.RichText)
        self.body.addWidget(hint)

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        install = QPushButton("Instalar")
        install.setProperty("variant", "primary")
        install.setDefault(True)
        install.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(install)
        self.body.addSpacing(4)
        self.body.addLayout(row)


class InstalledBuildsDialog(FramelessDialog):
    """Lista as builds instaladas; permite abrir ou remover."""

    def __init__(self, app, builds, on_remove, parent=None):
        super().__init__("Builds instaladas", width=440, parent=parent)
        self.selected = None
        self._app = app
        self._builds = list(builds)
        self._on_remove = on_remove

        self.body.addWidget(label(app.name, "heading"))
        self.body.addWidget(label("Escolha a build que deseja abrir.", "muted"))
        self.list = QListWidget()
        self.list.setMinimumHeight(220)
        self.list.itemDoubleClicked.connect(lambda _item: self._open())
        self.body.addWidget(self.list)

        row = QHBoxLayout()
        self.btn_remove = QPushButton("Remover")
        self.btn_remove.setProperty("variant", "danger")
        self.btn_remove.setIcon(icons.icon("trash", theme.palette().danger, 16))
        self.btn_remove.clicked.connect(self._remove)
        self.btn_open = QPushButton("Abrir")
        self.btn_open.setProperty("variant", "primary")
        self.btn_open.setIcon(icons.icon("play", theme.palette().on_accent, 14))
        self.btn_open.clicked.connect(self._open)
        row.addWidget(self.btn_remove)
        row.addStretch()
        row.addWidget(self.btn_open)
        self.body.addLayout(row)
        self._populate()

    def _populate(self):
        self.list.clear()
        code_label = self._app.custom_builds.code_label if self._app.custom_builds else "Build"
        for build in self._builds:
            title = f"{code_label} {build.get('code', '—')}"
            if build.get("date"):
                title += f"  ·  {build['date']}"
            subtitle = build.get("description") or "Sem descrição."
            item = QListWidgetItem(f"{title}\n{subtitle}")
            item.setData(Qt.ItemDataRole.UserRole, build)
            self.list.addItem(item)
        has = self.list.count() > 0
        if has:
            self.list.setCurrentRow(0)
        self.btn_open.setEnabled(has)
        self.btn_remove.setEnabled(has)

    def _current(self):
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _open(self):
        build = self._current()
        if build:
            self.selected = build
            self.accept()

    def _remove(self):
        build = self._current()
        if not build:
            return
        if not messages.confirm(
            self, "Remover build",
            f"Remover a build <b>{build.get('code', '')}</b>?<br><br>"
            "Os arquivos dessa pasta serão apagados. As demais builds não são afetadas.",
            confirm_label="Remover", danger=True,
        ):
            return
        if not self._on_remove(build):
            return
        self._builds = [b for b in self._builds if b.get("folder") != build.get("folder")]
        self._populate()
        if not self._builds:
            self.reject()
