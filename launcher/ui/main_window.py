"""Janela principal: seleção do aplicativo, versões, atualização e execução."""

from __future__ import annotations

import json
import os
import shutil
import sys
import webbrowser
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QMenu, QProgressBar, QPushButton, QVBoxLayout,
)

from .. import __version__, auth, installer, remote, self_update
from . import icons, messages, theme
from .builds import BuildCodeDialog, BuildInfoDialog, HelpMenuDialog, InstalledBuildsDialog
from .downloads import DownloadsDialog
from .settings import SettingsDialog
from .widgets import FramelessWindow, Task, VersionTile, divider, icon_button, label

_TEMP_DIR_NAME = ".launcher-tmp"


class MainWindow(FramelessWindow):
    def __init__(self, config, store, base_dir: Path, user: str = "", password: str = "",
                 self_update_failed: bool = False):
        super().__init__(config.app_name, width=440)
        self.config = config
        self.store = store
        self.base_dir = Path(base_dir)
        self.server = remote.RemoteServer(config.server, store)
        self._session = auth.session_env(config.auth, user, password)
        self._session_user, self._session_password = user, password
        self._self_update_failed = self_update_failed
        self._remote: dict[str, remote.RemoteFile] = {}   # último MDTM/SIZE visto por app
        self._pending: remote.RemoteFile | None = None
        self._busy = False
        self._self_updating = False
        pal = theme.palette()

        # -- barra de título ----------------------------------------------
        self.btn_help = icon_button("help", "Ajuda e suporte")
        self.btn_downloads = icon_button("box", "Downloads")
        self.btn_settings = icon_button("settings", "Configurações")
        btn_min = icon_button("minimize", "Minimizar", size=16)
        btn_close = icon_button("close", "Fechar", "CloseButton", 16)
        for b in (self.btn_help, self.btn_downloads, self.btn_settings, btn_min, btn_close):
            self.title_bar.add_button(b)
        btn_min.clicked.connect(self.showMinimized)
        btn_close.clicked.connect(self.close)
        self.btn_help.clicked.connect(self._open_help)
        self.btn_downloads.clicked.connect(self._open_downloads)
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_downloads.setVisible(bool(config.downloads))

        # -- seletor de aplicativo -------------------------------------------
        self.body.addWidget(label("APLICATIVO", "overline"))
        self.combo = QComboBox()
        self.combo.setIconSize(QSize(28, 28))
        self.combo.setCursor(Qt.CursorShape.PointingHandCursor)
        for app in config.apps:
            self.combo.addItem(QIcon(icons.avatar_pixmap(app.name, pal.accent, 28)), app.name)
        self.body.addWidget(self.combo)
        self.description = label("", "caption", wrap=True)
        self.body.addWidget(self.description)

        # -- versões ---------------------------------------------------------
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self.tile_local = VersionTile("Instalado")
        self.tile_remote = VersionTile("Disponível")
        tiles.addWidget(self.tile_local)
        tiles.addWidget(self.tile_remote)
        self.body.addSpacing(4)
        self.body.addLayout(tiles)

        # -- status ----------------------------------------------------------
        self.status = label("", "muted", wrap=True)
        self.status.setMinimumHeight(20)
        self.body.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.body.addWidget(self.progress)
        self.body.addSpacing(6)

        # -- ações -----------------------------------------------------------
        self.btn_open = QPushButton()
        self.btn_open.setProperty("variant", "primary")
        self.btn_open.setMinimumHeight(46)
        self.btn_open.setIcon(icons.icon("play", pal.on_accent, 16, disabled_color=pal.faint))
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open.clicked.connect(lambda: self._launch_main())
        self.body.addWidget(self.btn_open)

        self.extra_box = QVBoxLayout()
        self.extra_box.setSpacing(8)
        self.body.addLayout(self.extra_box)
        self._extra_buttons: list[QPushButton] = []

        self.btn_builds = QPushButton()
        self.btn_builds.setIcon(icons.icon("wrench", pal.muted, 16))
        self.btn_builds.clicked.connect(self._open_installed_builds)
        self.body.addWidget(self.btn_builds)

        update_row = QHBoxLayout()
        update_row.setSpacing(0)
        self.btn_update = QPushButton("Verificar atualizações")
        self.btn_update.setProperty("segment", "left")
        self.btn_update.setIcon(icons.icon("refresh", pal.muted, 16, disabled_color=pal.faint))
        self.btn_update.clicked.connect(self._on_update_clicked)
        self.btn_more = QPushButton()
        self.btn_more.setProperty("segment", "right")
        self.btn_more.setIcon(icons.icon("more", pal.muted, 16, disabled_color=pal.faint))
        self.btn_more.setToolTip("Mais opções")
        self.btn_more.clicked.connect(self._show_more_menu)
        update_row.addWidget(self.btn_update, 1)
        update_row.addWidget(self.btn_more)
        self.body.addLayout(update_row)

        self.footer = label("", "caption")
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.addSpacing(2)
        self.body.addWidget(divider())
        self.body.addWidget(self.footer)

        # Restaura o último app usado.
        last = store.pref("last_app", "")
        index = next((i for i, a in enumerate(config.apps) if a.id == last), 0)
        self.combo.setCurrentIndex(index)
        self.combo.currentIndexChanged.connect(self._on_app_changed)
        self._refresh()

        QTimer.singleShot(400, self._startup_checks)

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------

    @property
    def app(self):
        return self.config.apps[self.combo.currentIndex()]

    def _install_dir(self) -> Path:
        return installer.install_path(self.base_dir, self.app)

    def _local_record(self):
        """(mdtm, size) da instalação oficial, se a pasta ainda existir."""
        if not self._install_dir().is_dir():
            return None
        return self.store.install_record(self.app.id)

    def _on_app_changed(self, _index: int):
        self.store.set_pref("last_app", self.app.id)
        self._pending = None
        self.progress.setValue(0)
        self._refresh()

    def _refresh(self, status: str | None = None):
        app = self.app
        installed = installer.is_installed(self.base_dir, app)
        record = self._local_record()
        self.description.setText(app.description)
        self.description.setVisible(bool(app.description))
        self._update_tiles(record[0] if record else None,
                           (self._remote.get(app.id) or remote.RemoteFile("", None, None)).mdtm)

        self.btn_open.setText(f"Abrir {app.name}")
        self._rebuild_extra_buttons()
        builds = installer.list_builds(self.base_dir, app) if app.custom_builds else []
        self.btn_builds.setText(f"Builds personalizadas ({len(builds)})")
        self.btn_builds.setVisible(bool(builds))
        self.btn_help.setVisible(bool(self.config.support_url or app.custom_builds))

        if self._pending is not None:
            self.btn_update.setText("Instalar atualização" if installed else "Instalar")
            self.btn_update.setIcon(icons.icon("download", theme.palette().on_accent, 16,
                                               disabled_color=theme.palette().faint))
            theme.set_role(self.btn_update, "variant", "primary")
        else:
            self.btn_update.setText("Verificar atualizações")
            self.btn_update.setIcon(icons.icon("refresh", theme.palette().muted, 16,
                                               disabled_color=theme.palette().faint))
            theme.set_role(self.btn_update, "variant", "")

        if status is None:
            if not installed:
                status = "Não instalado. Use “Verificar atualizações” para instalar."
            elif record:
                status = f"Pronto · atualizado em {remote.format_mdtm(record[0])}"
            else:
                status = "Pronto."
        self.status.setText(status)
        self.footer.setText(self._footer_text())
        self._apply_enabled()
        self.adjustSize()

    def _footer_text(self) -> str:
        parts = [f"v{__version__}"]
        if self._session_user:
            parts.append(f"Conectado como {self._session_user}")
        if self.config.is_example:
            parts.append("usando a configuração de exemplo")
        return " · ".join(parts)

    def _update_tiles(self, local_mdtm, remote_mdtm):
        pal = theme.palette()
        if local_mdtm and remote_mdtm:
            local_color = pal.success if local_mdtm == remote_mdtm else pal.warning
            remote_color = pal.success
        else:
            local_color = pal.accent if local_mdtm else pal.faint
            remote_color = pal.accent if remote_mdtm else pal.faint
        self.tile_local.set_value(remote.format_mdtm(local_mdtm), local_color)
        self.tile_remote.set_value(remote.format_mdtm(remote_mdtm), remote_color)

    def _rebuild_extra_buttons(self):
        for btn in self._extra_buttons:
            btn.deleteLater()
        self._extra_buttons = []
        for action in self.app.extra_actions:
            btn = QPushButton(action.label)
            btn.clicked.connect(lambda _=False, exe=action.executable: self._launch(exe))
            self.extra_box.addWidget(btn)
            self._extra_buttons.append(btn)

    def _apply_enabled(self):
        idle = not self._busy
        installed = installer.is_installed(self.base_dir, self.app)
        self.btn_open.setEnabled(idle and installed)
        for btn in self._extra_buttons:
            btn.setEnabled(idle and installed)
        for w in (self.combo, self.btn_update, self.btn_more, self.btn_builds,
                  self.btn_help, self.btn_downloads, self.btn_settings):
            w.setEnabled(idle)

    def _set_busy(self, busy: bool, status: str | None = None):
        self._busy = busy
        if status:
            self.status.setText(status)
        if busy:
            self.progress.setValue(0)
        self._apply_enabled()

    def _fail(self, title: str, exc: BaseException, quiet: bool = False):
        self._set_busy(False)
        self._refresh()
        if not quiet:
            messages.error(self, title, messages.describe(exc))

    # ------------------------------------------------------------------
    # Atualização do aplicativo
    # ------------------------------------------------------------------

    def _on_update_clicked(self):
        if self._pending is not None:
            self._install(self._pending)
        else:
            self._check_updates()

    def _check_updates(self, auto: bool = False):
        app = self.app
        self._set_busy(True, "Conectando ao servidor…")

        def work(ctx):
            with self.server.connect() as ftp:
                ctx.status("Consultando a versão publicada…")
                ftp.cwd(app.remote_dir)
                return remote.stat(ftp, app.package)

        def done(rf: remote.RemoteFile):
            self._remote[app.id] = rf
            self._set_busy(False)
            record = self._local_record()
            installed = installer.is_installed(self.base_dir, app)
            if installed and record and record == (rf.mdtm, rf.size):
                self._pending = None
                self.progress.setValue(100)
                self._refresh("Tudo certo · você já tem a versão mais recente.")
                return
            if auto and not installed:
                self._refresh()
                return
            self._pending = rf
            self._refresh(f"Nova versão disponível · {remote.format_mdtm(rf.mdtm)}"
                          if installed else f"Versão disponível · {remote.format_mdtm(rf.mdtm)}")
            if auto:
                self._install(rf, auto=True)

        Task.start_new(self, work, done,
                       lambda exc: self._fail("Verificar atualizações", exc, quiet=auto),
                       on_status=self.status.setText)

    def _install(self, rf: remote.RemoteFile, auto: bool = False):
        app = self.app
        target = self._install_dir()
        temp_zip = self.base_dir / _TEMP_DIR_NAME / f"{app.id}.zip"
        self._set_busy(True, "Baixando…")

        def work(ctx):
            with self.server.connect() as ftp:
                ftp.cwd(app.remote_dir)
                remote.download(ftp, rf.name, temp_zip, rf.size, on_progress=ctx.progress)
            ctx.status("Instalando…")
            ctx.progress(0)
            try:
                installer.install_package(temp_zip, target, on_progress=ctx.progress)
            finally:
                temp_zip.unlink(missing_ok=True)
            return rf

        def done(_rf):
            self.store.set_install_record(app.id, rf.mdtm, rf.size)
            self._pending = None
            self._set_busy(False)
            self.progress.setValue(100)
            self._refresh(f"Atualizado · versão de {remote.format_mdtm(rf.mdtm)}")
            if not auto:
                messages.success(self, "Instalação concluída",
                                 f"<b>{app.name}</b> está pronto para uso.")

        Task.start_new(self, work, done, lambda exc: self._fail("Instalar", exc, quiet=auto),
                       on_progress=self.progress.setValue, on_status=self.status.setText)

    # ------------------------------------------------------------------
    # Menu "mais opções"
    # ------------------------------------------------------------------

    def _show_more_menu(self):
        pal = theme.palette()
        menu = QMenu(self)
        # Sem isso os cantos arredondados do QSS aparecem sobre um fundo quadrado.
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        installed_dir = self._install_dir().is_dir()
        act_integrity = menu.addAction(icons.icon("shield", pal.muted, 16), "Verificar integridade")
        act_folder = menu.addAction(icons.icon("folder", pal.muted, 16), "Abrir pasta de instalação")
        act_folder.setEnabled(installed_dir)
        menu.addSeparator()
        act_uninstall = menu.addAction(icons.icon("trash", pal.danger, 16), "Desinstalar")
        act_uninstall.setEnabled(installed_dir)
        chosen = menu.exec(self.btn_more.mapToGlobal(self.btn_more.rect().bottomLeft()))
        if chosen is act_integrity:
            self._show_integrity()
        elif chosen is act_folder:
            os.startfile(self._install_dir())  # noqa: S606
        elif chosen is act_uninstall:
            self._uninstall()

    def _show_integrity(self):
        app = self.app
        folder = self._install_dir()
        exe = folder / app.executable
        record = self.store.install_record(app.id)
        builds = installer.list_builds(self.base_dir, app) if app.custom_builds else []
        pal = theme.palette()

        def line(ok: bool, text: str, detail: str):
            color = pal.success if ok else pal.danger
            mark = "✓" if ok else "✗"
            return (f"<span style='color:{color}'>{mark}</span>&nbsp; {text}: "
                    f"<span style='color:{pal.muted}'>{detail}</span>")

        rows = [
            line(folder.is_dir(), "Pasta de instalação", "encontrada" if folder.is_dir() else "não encontrada"),
            line(exe.is_file(), f"Executável <i>{app.executable}</i>",
                 "encontrado" if exe.is_file() else "não encontrado"),
            line(record is not None, "Registro da versão",
                 remote.format_mdtm(record[0]) if record else "ausente"),
            f"&nbsp;&nbsp;&nbsp; Arquivos na pasta: <b>{installer.count_files(folder)}</b>",
        ]
        if app.custom_builds:
            rows.append(f"&nbsp;&nbsp;&nbsp; Builds personalizadas: <b>{len(builds)}</b>")
        messages.info(self, "Verificação de integridade", f"<b>{app.name}</b><br><br>" + "<br>".join(rows))

    def _uninstall(self):
        app = self.app
        folder = self._install_dir()
        if not messages.confirm(
            self, "Desinstalar",
            f"Desinstalar <b>{app.name}</b>?<br><br>Todos os arquivos em<br><i>{messages.path_html(folder)}</i><br>"
            "serão apagados. Builds personalizadas não são afetadas.",
            confirm_label="Desinstalar", danger=True,
        ):
            return
        try:
            shutil.rmtree(folder)
        except OSError as exc:
            messages.error(self, "Desinstalar", f"Não foi possível remover os arquivos:<br>{messages.describe(exc)}")
            return
        self.store.clear_install_record(app.id)
        self._pending = None
        self.progress.setValue(0)
        self._refresh(f"{app.name} foi desinstalado.")

    # ------------------------------------------------------------------
    # Execução
    # ------------------------------------------------------------------

    def _launch_env(self) -> dict:
        return installer.build_launch_env(self.app, self.store.option_values(self.app), self._session)

    def _launch_main(self):
        self._launch(self.app.executable)

    def _launch(self, executable: str, folder: Path | None = None):
        path = (folder or self._install_dir()) / executable
        try:
            installer.launch(path, self._launch_env())
        except Exception as exc:  # noqa: BLE001
            messages.error(self, "Abrir aplicativo", messages.describe(exc))
            return
        if self.store.pref("keep_open", False):
            self.status.setText(f"{self.app.name} iniciado.")
        else:
            self.close()

    # ------------------------------------------------------------------
    # Diálogos da barra de título
    # ------------------------------------------------------------------

    def _open_settings(self):
        SettingsDialog(self.config, self.store, self.app, self).exec()
        auth.persist_session_if_auto_login(
            self.store.pref("auto_login", False), self._session_user, self._session_password,
            lambda u, p: auth.save_login(self.store, u, p),
        )

    def _open_downloads(self):
        DownloadsDialog(self.config.downloads, self.server, self.base_dir, self).exec()

    def _open_help(self):
        app = self.app
        has_builds = bool(app.custom_builds and installer.list_builds(self.base_dir, app))
        dlg = HelpMenuDialog(app, self.config.support_url, has_builds, self)
        if not dlg.exec():
            return
        if dlg.choice == "report":
            webbrowser.open(self.config.support_url)
        elif dlg.choice == "install":
            self._ask_build_code()
        elif dlg.choice == "manage":
            self._open_installed_builds()

    # ------------------------------------------------------------------
    # Builds personalizadas
    # ------------------------------------------------------------------

    def _ask_build_code(self):
        app = self.app
        cb = app.custom_builds
        dlg = BuildCodeDialog(cb, self)
        if not dlg.exec():
            return
        code = dlg.code
        self._set_busy(True, f"Procurando a build {code}…")

        def work(ctx):
            with self.server.connect() as ftp:
                if not remote.try_cwd(ftp, f"{app.remote_dir.rstrip('/')}/{cb.remote_subdir}/{code}"):
                    return None
                files = [name.rsplit("/", 1)[-1] for name in ftp.nlst()]
                package = installer.pick_package_name(files, cb.package_names)
                if package is None:
                    return None
                text = remote.read_text(ftp, "info.json") if "info.json" in files else None
                info = json.loads(text) if text else {}
                return (info if isinstance(info, dict) else {}), remote.stat(ftp, package)

        def done(result):
            self._set_busy(False)
            self._refresh()
            if result is None:
                messages.info(self, "Build personalizada",
                              f"Nenhuma build encontrada para <b>{cb.code_label} {code}</b>.<br><br>"
                              "Confira o código e tente de novo.")
                return
            info, rf = result
            existing = installer.read_build_meta(installer.build_dir(self.base_dir, app, code)) or {}
            if BuildInfoDialog(app, code, info, existing.get("id", ""), self).exec():
                self._install_build(code, info, rf)

        Task.start_new(self, work, done, lambda exc: self._fail("Build personalizada", exc),
                       on_status=self.status.setText)

    def _install_build(self, code: str, info: dict, rf: remote.RemoteFile):
        app = self.app
        cb = app.custom_builds
        target = installer.build_dir(self.base_dir, app, code)
        official = self._install_dir() if self._install_dir().is_dir() else None
        temp_zip = self.base_dir / _TEMP_DIR_NAME / f"{app.id}-build-{code}.zip"
        self._set_busy(True, f"Baixando a build {code}…")

        def work(ctx):
            with self.server.connect() as ftp:
                ftp.cwd(f"{app.remote_dir.rstrip('/')}/{cb.remote_subdir}/{code}")
                remote.download(ftp, rf.name, temp_zip, rf.size, on_progress=ctx.progress)
            ctx.status("Instalando…")
            ctx.progress(0)
            try:
                installer.install_package(temp_zip, target, clean=True, on_progress=ctx.progress)
            finally:
                temp_zip.unlink(missing_ok=True)
            copied = installer.carry_over_files(official, target, cb.carry_over_files)
            installer.write_build_meta(target, code, info, rf.mdtm, rf.size)
            return copied

        def done(copied):
            self._set_busy(False)
            self.progress.setValue(100)
            self._refresh(f"Build {code} instalada.")
            note = ""
            if copied:
                note = "<br><br>Copiado da instalação oficial: " + ", ".join(f"<b>{c}</b>" for c in copied)
            messages.success(self, "Build instalada",
                             f"A build <b>{code}</b> foi instalada numa pasta separada.<br>"
                             f"Abra-a em <b>Builds personalizadas</b>.{note}")

        Task.start_new(self, work, done, lambda exc: self._fail("Build personalizada", exc),
                       on_progress=self.progress.setValue, on_status=self.status.setText)

    def _open_installed_builds(self):
        app = self.app
        builds = installer.list_builds(self.base_dir, app)
        if not builds:
            self._refresh()
            return

        def remove(build) -> bool:
            try:
                shutil.rmtree(build["folder"])
                return True
            except OSError as exc:
                messages.error(self, "Remover build", messages.describe(exc))
                return False

        dlg = InstalledBuildsDialog(app, builds, remove, self)
        accepted = dlg.exec()
        self._refresh()
        if accepted and dlg.selected:
            self._launch(app.executable, Path(dlg.selected["folder"]))

    # ------------------------------------------------------------------
    # Inicialização: auto-atualização do launcher e do app
    # ------------------------------------------------------------------

    def _startup_checks(self):
        if self._self_update_failed:
            messages.warning(
                self, "Atualização do launcher",
                "A nova versão foi baixada, mas o executável não pôde ser substituído.<br><br>"
                "Isso costuma acontecer com outra janela do launcher aberta, antivírus "
                "bloqueando a troca ou pasta sem permissão de escrita. Feche as outras "
                "instâncias e abra o launcher de novo.",
            )
            self._auto_update_app()
        elif self.config.self_update and self_update.is_frozen():
            self._check_self_update()
        else:
            self._auto_update_app()

    def _auto_update_app(self):
        if self._self_updating:
            return
        if self.store.pref("auto_update", False) and installer.is_installed(self.base_dir, self.app):
            self._check_updates(auto=True)

    def _check_self_update(self):
        su = self.config.self_update

        def work(ctx):
            with self.server.connect() as ftp:
                if not remote.try_cwd(ftp, su.remote_dir):
                    return None
                try:
                    return remote.stat(ftp, su.file_name)
                except Exception:  # noqa: BLE001 — sem .exe publicado: nada a fazer
                    return None

        def done(rf):
            if rf is None or not rf.size:
                self._auto_update_app()
                return
            record = self.store.install_record(self_update.RECORD_KEY)
            if not self_update.needs_update(record, rf.mdtm, rf.size, self_update.running_exe_size()):
                if record is None:
                    self.store.set_install_record(self_update.RECORD_KEY, rf.mdtm, rf.size)
                self._auto_update_app()
                return
            if not self.store.pref("auto_update_launcher", False) and not messages.confirm(
                self, "Atualização do launcher",
                f"Há uma nova versão do launcher (publicada em <b>{remote.format_mdtm(rf.mdtm)}</b>)."
                "<br><br>Atualizar agora? O launcher será reiniciado.",
                confirm_label="Atualizar", cancel_label="Agora não",
            ):
                self._auto_update_app()
                return
            self._download_self_update(rf)

        Task.start_new(self, work, done, lambda exc: self._auto_update_app())

    def _download_self_update(self, rf: remote.RemoteFile):
        su = self.config.self_update
        exe = Path(sys.executable)
        new_exe = exe.with_name(f"{exe.stem}.new.exe")
        self._self_updating = True
        self._set_busy(True, "Baixando a nova versão do launcher…")

        def work(ctx):
            with self.server.connect() as ftp:
                ftp.cwd(su.remote_dir)
                remote.download(ftp, su.file_name, new_exe, rf.size, on_progress=ctx.progress)

        def done(_):
            self.status.setText("Reiniciando para aplicar a atualização…")
            self_update.apply(new_exe, rf.mdtm, rf.size)
            QApplication.instance().quit()

        def fail(exc):
            self._self_updating = False
            self._fail("Atualização do launcher", exc)

        Task.start_new(self, work, done, fail, on_progress=self.progress.setValue)

    def closeEvent(self, event):
        if self._busy and not messages.confirm(
            self, "Operação em andamento",
            "Há um download ou instalação em andamento. Fechar mesmo assim?",
            confirm_label="Fechar", danger=True,
        ):
            event.ignore()
            return
        super().closeEvent(event)
