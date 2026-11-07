"""Launcher preferences and the selected application's options.

Values are saved when the dialog closes, whichever way it closes (button,
Esc or the system) — there is no "Save" button to forget.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLineEdit, QScrollArea, QVBoxLayout, QWidget,
)

from .. import i18n
from ..i18n import tr, tr_noop
from .widgets import FramelessDialog, ToggleSwitch, divider, label

# (key, label, description) of the general preferences; translated when displayed.
GENERAL_PREFS = (
    ("auto_update", tr_noop("Update applications on startup"),
     tr_noop("Installs the new version of the selected application by itself, if it is already installed.")),
    ("auto_update_launcher", tr_noop("Update the launcher on startup"),
     tr_noop("Without this option, the launcher asks before updating itself.")),
    ("keep_open", tr_noop("Keep the launcher open"),
     tr_noop("By default the launcher closes after starting an application.")),
)
AUTO_LOGIN_PREF = ("auto_login", tr_noop("Sign in automatically"),
                   tr_noop("Uses the saved credentials and skips the login screen."))


class SettingsDialog(FramelessDialog):
    def __init__(self, config, store, app, parent=None):
        super().__init__(tr("Settings"), width=440, parent=parent)
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

        lay.addWidget(label(tr("GENERAL"), "overline"))
        prefs = list(GENERAL_PREFS)
        if config.auth.enabled:
            prefs.append(AUTO_LOGIN_PREF)
        for i, (key, title, desc) in enumerate(prefs):
            if i:
                lay.addWidget(divider())
            toggle = self._toggle_row(lay, tr(title), tr(desc), bool(store.pref(key, False)))
            self._pref_toggles[key] = toggle
        lay.addWidget(divider())
        self._language_row(lay, store)

        if app.options:
            lay.addSpacing(8)
            lay.addWidget(label(tr("OPTIONS · {name}", name=app.name.upper()), "overline"))
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

    def _language_row(self, layout, store):
        row = QHBoxLayout()
        row.setSpacing(12)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(label(tr("Language"), "body"))
        texts.addWidget(label(tr("Takes effect the next time the launcher starts."), "caption", wrap=True))
        row.addLayout(texts, 1)
        self._language_combo = QComboBox()
        self._language_combo.addItem(tr("Automatic"), i18n.AUTO)
        for code, name in i18n.LANGUAGES.items():
            self._language_combo.addItem(name, code)
        current = i18n.normalize(store.pref("language", "")) or i18n.AUTO
        self._language_combo.setCurrentIndex(max(0, self._language_combo.findData(current)))
        row.addWidget(self._language_combo)
        layout.addLayout(row)

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
        self._store.set_pref("language", self._language_combo.currentData())
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
