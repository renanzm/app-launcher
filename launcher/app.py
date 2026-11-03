"""Ponto de entrada: configuração → splash → login (opcional) → janela principal."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="launcher", add_help=True)
    parser.add_argument("--config", type=Path, help="caminho do launcher_config.json")
    parser.add_argument("--no-splash", action="store_true", help="não exibe a tela de abertura")
    return parser.parse_known_args(argv)[0]


def main(argv=None) -> int:
    # Valida HTTPS com o repositório de certificados do Windows (proxies corporativos).
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass

    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    from . import auth, self_update
    from .config import ConfigError, find_config
    from .paths import BASE_DIR, BUNDLE_DIR, resource_path
    from .state import StateStore, default_state_path
    from .ui import theme
    from .ui.widgets import Task

    argv = list(sys.argv if argv is None else argv)
    args = _parse_args(argv[1:])

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)

    try:
        config = find_config(BASE_DIR, BUNDLE_DIR, args.config)
    except ConfigError as exc:
        from .ui import messages
        theme.apply(app, "#7C5CFF")
        messages.error(None, "Configuração inválida", messages.describe(exc))
        return 2

    app.setApplicationName(config.app_name)
    icon_file = resource_path("assets/app.ico")
    if icon_file.is_file():
        app.setWindowIcon(QIcon(str(icon_file)))
    theme.apply(app, config.accent_color)

    store = StateStore(default_state_path(config.app_id))
    argv, self_update_failed = self_update.consume_applied_args(argv, store)

    splash = None
    if not args.no_splash:
        from .ui.splash import Splash
        splash = Splash(config.app_name)
        splash.present()

    user, password, warning, skip_login = "", "", "", not config.auth.enabled
    if config.auth.enabled and store.pref("auto_login", False):
        saved_user, saved_password, _ = auth.load_saved_login(store)
        skip_login, warning = auth.resolve_startup_login(
            True, saved_user, saved_password, auth.make_authenticator(config.auth)
        )
        if skip_login:
            user, password = saved_user, saved_password

    if splash is not None:
        splash.wait_minimum()
        splash.dismiss()

    if not skip_login:
        from .ui.login import LoginDialog
        login = LoginDialog(config, store, warning or "")
        if not login.exec():
            return 0
        user, password = login.authenticated_user, login.authenticated_password

    from .ui.main_window import MainWindow
    window = MainWindow(config, store, BASE_DIR, user, password, self_update_failed)
    window.show()
    code = app.exec()
    if Task._running:
        # O usuário fechou no meio de um download: não há como interromper o
        # ftplib com segurança, então encerra o processo sem esperar a thread.
        os._exit(code)
    return code


if __name__ == "__main__":
    sys.exit(main())
