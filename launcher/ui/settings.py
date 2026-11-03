"""Preferências do launcher e opções do aplicativo selecionado.

Os valores são gravados ao fechar o diálogo, por qualquer caminho (botão,
Esc ou fechamento pelo sistema) — não há botão "Salvar" para esquecer.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from .widgets import FramelessDialog, ToggleSwitch, divider, label

# (chave, rótulo, descrição) das preferências gerais.
GENERAL_PREFS = (
    ("auto_update", "Atualizar aplicativos ao abrir",
     "Instala sozinho a versão nova do aplicativo selecionado, se ele já estiver instalado."),
    ("auto_update_launcher", "Atualizar o launcher ao abrir",
     "Sem esta opção, o launcher pergunta antes de se atualizar."),
    ("keep_open", "Manter o launcher aberto",
     "Por padrão o launcher fecha depois de iniciar um aplicativo."),
)
AUTO_LOGIN_PREF = ("auto_login", "Entrar automaticamente",
                   "Usa as credenciais salvas e pula a tela de login.")


class SettingsDialog(FramelessDialog):
    def __init__(self, config, store, app, parent=None):
        super().__init__("Configurações", width=440, parent=parent)
        self._store = store
        self._app = app
        self._pref_toggles = {}
        self._option_widgets = {}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)
        scroll.setWidget(content)

        lay.addWidget(label("GERAL", "overline"))
        prefs = list(GENERAL_PREFS)
        if config.auth.enabled:
            prefs.append(AUTO_LOGIN_PREF)
        for i, (key, title, desc) in enumerate(prefs):
            if i:
                lay.addWidget(divider())
            toggle = self._toggle_row(lay, title, desc, bool(store.pref(key, False)))
            self._pref_toggles[key] = toggle

        if app.options:
            lay.addSpacing(8)
            lay.addWidget(label(f"OPÇÕES · {app.name.upper()}", "overline"))
            for i, option in enumerate(app.options):
                if i:
                    lay.addWidget(divider())
                value = store.option_value(app.id, option)
                if option.type == "bool":
                    widget = self._toggle_row(lay, option.label, option.description, bool(value))
                else:
                    widget = self._text_row(lay, option, "" if value is None else str(value))
                self._option_widgets[option.key] = (option, widget)

        lay.addStretch()
        self.body.addWidget(scroll)
        content.adjustSize()
        scroll.setMinimumHeight(min(460, content.sizeHint().height() + 4))

    @staticmethod
    def _toggle_row(layout, title: str, description: str, checked: bool) -> ToggleSwitch:
        row = QHBoxLayout()
        row.setSpacing(12)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(label(title, "body", wrap=True))
        if description:
            texts.addWidget(label(description, "caption", wrap=True))
        row.addLayout(texts, 1)
        toggle = ToggleSwitch(checked)
        row.addWidget(toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(row)
        return toggle

    @staticmethod
    def _text_row(layout, option, value: str) -> QLineEdit:
        layout.addWidget(label(option.label, "body", wrap=True))
        if option.description:
            layout.addWidget(label(option.description, "caption", wrap=True))
        field = QLineEdit(value)
        if option.type == "password":
            field.setEchoMode(QLineEdit.EchoMode.Password)
        if option.default not in (None, ""):
            field.setPlaceholderText(str(option.default))
        layout.addWidget(field)
        return field

    def _save(self):
        for key, toggle in self._pref_toggles.items():
            self._store.set_pref(key, toggle.isChecked())
        for key, (option, widget) in self._option_widgets.items():
            if option.type == "bool":
                value = widget.isChecked()
            else:
                value = widget.text()
                if not value.strip() and option.default not in (None, ""):
                    value = option.default
            self._store.set_option_value(self._app.id, option, value)

    def done(self, result):
        self._save()
        super().done(result)
