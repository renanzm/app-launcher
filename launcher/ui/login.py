"""Login screen (shown only when `auth.type` is not "none")."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton

from .. import auth
from ..i18n import tr
from . import icons, theme
from .widgets import FramelessDialog, Task, label


class LoginDialog(FramelessDialog):
    def __init__(self, config, store, warning: str = ""):
        super().__init__(config.app_name, width=380)
        self._config = config
        self._store = store
        self._authenticate = auth.make_authenticator(config.auth)
        self._warning = warning
        self.authenticated_user = ""
        self.authenticated_password = ""
        pal = theme.palette()

        mark = QLabel()
        mark.setPixmap(icons.mark_pixmap(pal.accent, 44))
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.addWidget(mark)
        heading = label(config.auth.title or tr("Sign in"), "heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.addWidget(heading)
        sub = label(tr("Sign in to continue to {name}.", name=config.app_name), "muted")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.addWidget(sub)
        self.body.addSpacing(8)

        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText(config.auth.user_label or tr("Username"))
        self.input_user.addAction(icons.icon("user", pal.faint, 16), QLineEdit.ActionPosition.LeadingPosition)
        self.input_pass = QLineEdit()
        self.input_pass.setPlaceholderText(tr("Password"))
        self.input_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_pass.addAction(icons.icon("lock", pal.faint, 16), QLineEdit.ActionPosition.LeadingPosition)
        self.body.addWidget(self.input_user)
        self.body.addWidget(self.input_pass)

        self.check_remember = QCheckBox(tr("Remember me on this computer"))
        self.body.addWidget(self.check_remember)
        self.error_label = label("", "caption")
        self.error_label.setStyleSheet(f"color: {pal.danger};")
        self.error_label.hide()
        self.body.addWidget(self.error_label)
        self.body.addSpacing(4)

        row = QHBoxLayout()
        self.btn_login = QPushButton(tr("Sign in"))
        self.btn_login.setProperty("variant", "primary")
        self.btn_login.setDefault(True)
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self.btn_login)
        self.body.addLayout(row)

        self.btn_login.clicked.connect(self._try_login)
        self.input_pass.returnPressed.connect(self._try_login)

        user, password, remember = auth.load_saved_login(store)
        if remember:
            self.input_user.setText(user)
            self.input_pass.setText(password)
            self.check_remember.setChecked(True)
        (self.input_pass if user else self.input_user).setFocus()

    def showEvent(self, event):
        super().showEvent(event)
        if self._warning:
            text, self._warning = self._warning, ""
            QTimer.singleShot(300, lambda: self._show_error(text))

    def _show_error(self, text: str):
        self.error_label.setText(text)
        self.error_label.setVisible(bool(text))

    def _try_login(self):
        user = self.input_user.text().strip()
        password = self.input_pass.text()
        if not user or not password:
            self._show_error(tr("Enter your username and password."))
            return
        self._show_error("")
        self._set_busy(True)
        Task.start_new(
            self, lambda ctx: self._authenticate(user, password),
            on_success=lambda ok: self._finish(ok, user, password),
            on_error=lambda exc: self._fail(tr("Authentication failed: {error}", error=exc)),
        )

    def _set_busy(self, busy: bool):
        for w in (self.btn_login, self.input_user, self.input_pass, self.check_remember):
            w.setEnabled(not busy)
        self.btn_login.setText(tr("Verifying…") if busy else tr("Sign in"))

    def _fail(self, text: str):
        self._set_busy(False)
        self._show_error(text)

    def _finish(self, ok: bool, user: str, password: str):
        if not ok:
            self._fail(tr("Invalid username or password."))
            self.input_pass.selectAll()
            self.input_pass.setFocus()
            return
        if self.check_remember.isChecked() or self._store.pref("auto_login", False):
            auth.save_login(self._store, user, password)
        else:
            auth.clear_login(self._store)
        self.authenticated_user = user
        self.authenticated_password = password
        self.accept()

