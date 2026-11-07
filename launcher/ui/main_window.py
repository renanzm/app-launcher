"""Main window: app selection, versions, updating and launching."""

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
from ..i18n import tr
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
        self._remote: dict[str, remote.RemoteFile] = {}   # last MDTM/SIZE seen per app
        self._pending: remote.RemoteFile | None = None
        self._busy = False
        self._self_updating = False
        pal = theme.palette()

        # -- title bar ----------------------------------------------------
        self.btn_help = icon_button("help", tr("Help and support"))
        self.btn_downloads = icon_button("box", tr("Downloads"))
        self.btn_settings = icon_button("settings", tr("Settings"))
        btn_min = icon_button("minimize", tr("Minimize"), size=16)
        btn_close = icon_button("close", tr("Close"), "CloseButton", 16)
        for b in (self.btn_help, self.btn_downloads, self.btn_settings, btn_min, btn_close):
            self.title_bar.add_button(b)
        btn_min.clicked.connect(self.showMinimized)
        btn_close.clicked.connect(self.close)
        self.btn_help.clicked.connect(self._open_help)
        self.btn_downloads.clicked.connect(self._open_downloads)
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_downloads.setVisible(bool(config.downloads))

        # -- application selector --------------------------------------------
        self.body.addWidget(label(tr("APPLICATION"), "overline"))
        self.combo = QComboBox()
        self.combo.setIconSize(QSize(28, 28))
        self.combo.setCursor(Qt.CursorShape.PointingHandCursor)
        for app in config.apps:
            self.combo.addItem(QIcon(icons.avatar_pixmap(app.name, pal.accent, 28)), app.name)
        self.body.addWidget(self.combo)
        self.description = label("", "caption", wrap=True)
        self.body.addWidget(self.description)

        # -- versions --------------------------------------------------------
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self.tile_local = VersionTile(tr("Installed"))
        self.tile_remote = VersionTile(tr("Available"))
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

        # -- actions ---------------------------------------------------------
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
        self.btn_update = QPushButton(tr("Check for updates"))
        self.btn_update.setProperty("segment", "left")
        self.btn_update.setIcon(icons.icon("refresh", pal.muted, 16, disabled_color=pal.faint))
        self.btn_update.clicked.connect(self._on_update_clicked)
        self.btn_more = QPushButton()
        self.btn_more.setProperty("segment", "right")
        self.btn_more.setIcon(icons.icon("more", pal.muted, 16, disabled_color=pal.faint))
        self.btn_more.setToolTip(tr("More options"))
        self.btn_more.clicked.connect(self._show_more_menu)
        update_row.addWidget(self.btn_update, 1)
        update_row.addWidget(self.btn_more)
        self.body.addLayout(update_row)

        self.footer = label("", "caption")
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.addSpacing(2)
        self.body.addWidget(divider())
        self.body.addWidget(self.footer)

        # Restore the last app used.
        last = store.pref("last_app", "")
        index = next((i for i, a in enumerate(config.apps) if a.id == last), 0)
        self.combo.setCurrentIndex(index)
        self.combo.currentIndexChanged.connect(self._on_app_changed)
        self._refresh()

        QTimer.singleShot(400, self._startup_checks)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def app(self):
        return self.config.apps[self.combo.currentIndex()]

    def _install_dir(self) -> Path:
        return installer.install_path(self.base_dir, self.app)

    def _local_record(self):
        """(mdtm, size) of the official installation, if the folder still exists."""
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

        self.btn_open.setText(tr("Open {name}", name=app.name))
        self._rebuild_extra_buttons()
        builds = installer.list_builds(self.base_dir, app) if app.custom_builds else []
        self.btn_builds.setText(tr("Custom builds ({count})", count=len(builds)))
        self.btn_builds.setVisible(bool(builds))
        self.btn_help.setVisible(bool(self.config.support_url or app.custom_builds))

        if self._pending is not None:
            self.btn_update.setText(tr("Install update") if installed else tr("Install"))
            self.btn_update.setIcon(icons.icon("download", theme.palette().on_accent, 16,
                                               disabled_color=theme.palette().faint))
            theme.set_role(self.btn_update, "variant", "primary")
        else:
            self.btn_update.setText(tr("Check for updates"))
            self.btn_update.setIcon(icons.icon("refresh", theme.palette().muted, 16,
                                               disabled_color=theme.palette().faint))
            theme.set_role(self.btn_update, "variant", "")

        if status is None:
            if not installed:
                status = tr("Not installed. Use “Check for updates” to install.")
            elif record:
                status = tr("Ready · updated on {date}", date=remote.format_mdtm(record[0]))
            else:
                status = tr("Ready.")
        self.status.setText(status)
        self.footer.setText(self._footer_text())
        self._apply_enabled()
        self.adjustSize()

    def _footer_text(self) -> str:
        parts = [f"v{__version__}"]
        if self._session_user:
            parts.append(tr("Signed in as {user}", user=self._session_user))
        if self.config.is_example:
            parts.append(tr("using the example configuration"))
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
    # Application update
    # ------------------------------------------------------------------

    def _on_update_clicked(self):
        if self._pending is not None:
            self._install(self._pending)
        else:
            self._check_updates()

    def _check_updates(self, auto: bool = False):
        app = self.app
        self._set_busy(True, tr("Connecting to the server…"))

        def work(ctx):
            with self.server.connect() as ftp:
                ctx.status(tr("Checking the published version…"))
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
                self._refresh(tr("All good · you already have the latest version."))
                return
            if auto and not installed:
                self._refresh()
                return
            self._pending = rf
            date = remote.format_mdtm(rf.mdtm)
            self._refresh(tr("New version available · {date}", date=date) if installed
                          else tr("Version available · {date}", date=date))
            if auto:
                self._install(rf, auto=True)

        Task.start_new(self, work, done,
                       lambda exc: self._fail(tr("Check for updates"), exc, quiet=auto),
                       on_status=self.status.setText)

    def _install(self, rf: remote.RemoteFile, auto: bool = False):
        app = self.app
        target = self._install_dir()
        temp_zip = self.base_dir / _TEMP_DIR_NAME / f"{app.id}.zip"
        self._set_busy(True, tr("Downloading…"))

        def work(ctx):
            with self.server.connect() as ftp:
                ftp.cwd(app.remote_dir)
                remote.download(ftp, rf.name, temp_zip, rf.size, on_progress=ctx.progress)
            ctx.status(tr("Installing…"))
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
            self._refresh(tr("Updated · version from {date}", date=remote.format_mdtm(rf.mdtm)))
            if not auto:
                messages.success(self, tr("Installation complete"),
                                 tr("<b>{name}</b> is ready to use.", name=app.name))

        Task.start_new(self, work, done, lambda exc: self._fail(tr("Install"), exc, quiet=auto),
                       on_progress=self.progress.setValue, on_status=self.status.setText)

    # ------------------------------------------------------------------
    # "More options" menu
    # ------------------------------------------------------------------

    def _show_more_menu(self):
        pal = theme.palette()
        menu = QMenu(self)
        # Without this, the QSS rounded corners show over a square background.
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        installed_dir = self._install_dir().is_dir()
        act_integrity = menu.addAction(icons.icon("shield", pal.muted, 16), tr("Verify integrity"))
        act_folder = menu.addAction(icons.icon("folder", pal.muted, 16), tr("Open install folder"))
        act_folder.setEnabled(installed_dir)
        menu.addSeparator()
        act_uninstall = menu.addAction(icons.icon("trash", pal.danger, 16), tr("Uninstall"))
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
            line(folder.is_dir(), tr("Install folder"),
                 tr("found") if folder.is_dir() else tr("not found")),
            line(exe.is_file(), tr("Executable <i>{name}</i>", name=app.executable),
                 tr("found") if exe.is_file() else tr("not found")),
            line(record is not None, tr("Version record"),
                 remote.format_mdtm(record[0]) if record else tr("missing")),
            "&nbsp;&nbsp;&nbsp; " + tr("Files in folder: <b>{count}</b>", count=installer.count_files(folder)),
        ]
        if app.custom_builds:
            rows.append("&nbsp;&nbsp;&nbsp; " + tr("Custom builds: <b>{count}</b>", count=len(builds)))
        messages.info(self, tr("Integrity check"), f"<b>{app.name}</b><br><br>" + "<br>".join(rows))

    def _uninstall(self):
        app = self.app
        folder = self._install_dir()
        if not messages.confirm(
            self, tr("Uninstall"),
            tr("Uninstall <b>{name}</b>?<br><br>All files in<br><i>{path}</i><br>will be deleted. "
               "Custom builds are not affected.", name=app.name, path=messages.path_html(folder)),
            confirm_label=tr("Uninstall"), danger=True,
        ):
            return
        try:
            shutil.rmtree(folder)
        except OSError as exc:
            messages.error(self, tr("Uninstall"),
                           tr("Could not remove the files:<br>{error}", error=messages.describe(exc)))
            return
        self.store.clear_install_record(app.id)
        self._pending = None
        self.progress.setValue(0)
        self._refresh(tr("{name} was uninstalled.", name=app.name))

    # ------------------------------------------------------------------
    # Launching
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
            messages.error(self, tr("Open application"), messages.describe(exc))
            return
        if self.store.pref("keep_open", False):
            self.status.setText(tr("{name} started.", name=self.app.name))
        else:
            self.close()

    # ------------------------------------------------------------------
    # Title bar dialogs
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
    # Custom builds
    # ------------------------------------------------------------------

    def _ask_build_code(self):
        app = self.app
        cb = app.custom_builds
        dlg = BuildCodeDialog(cb, self)
        if not dlg.exec():
            return
        code = dlg.code
        self._set_busy(True, tr("Looking for build {code}…", code=code))

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
                messages.info(self, tr("Custom build"),
                              tr("No build found for <b>{label} {code}</b>.<br><br>"
                                 "Check the code and try again.", label=cb.code_label, code=code))
                return
            info, rf = result
            existing = installer.read_build_meta(installer.build_dir(self.base_dir, app, code)) or {}
            if BuildInfoDialog(app, code, info, existing.get("id", ""), self).exec():
                self._install_build(code, info, rf)

        Task.start_new(self, work, done, lambda exc: self._fail(tr("Custom build"), exc),
                       on_status=self.status.setText)

    def _install_build(self, code: str, info: dict, rf: remote.RemoteFile):
        app = self.app
        cb = app.custom_builds
        target = installer.build_dir(self.base_dir, app, code)
        official = self._install_dir() if self._install_dir().is_dir() else None
        temp_zip = self.base_dir / _TEMP_DIR_NAME / f"{app.id}-build-{code}.zip"
        self._set_busy(True, tr("Downloading build {code}…", code=code))

        def work(ctx):
            with self.server.connect() as ftp:
                ftp.cwd(f"{app.remote_dir.rstrip('/')}/{cb.remote_subdir}/{code}")
                remote.download(ftp, rf.name, temp_zip, rf.size, on_progress=ctx.progress)
            ctx.status(tr("Installing…"))
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
            self._refresh(tr("Build {code} installed.", code=code))
            note = ""
            if copied:
                note = "<br><br>" + tr("Copied from the official installation: {files}",
                                       files=", ".join(f"<b>{c}</b>" for c in copied))
            messages.success(self, tr("Build installed"),
                             tr("Build <b>{code}</b> was installed in a separate folder.<br>"
                                "Open it from <b>Custom builds</b>.", code=code) + note)

        Task.start_new(self, work, done, lambda exc: self._fail(tr("Custom build"), exc),
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
                messages.error(self, tr("Remove build"), messages.describe(exc))
                return False

        dlg = InstalledBuildsDialog(app, builds, remove, self)
        accepted = dlg.exec()
        self._refresh()
        if accepted and dlg.selected:
            self._launch(app.executable, Path(dlg.selected["folder"]))

    # ------------------------------------------------------------------
    # Startup: self-update of the launcher and the app
    # ------------------------------------------------------------------

    def _startup_checks(self):
        if self._self_update_failed:
            messages.warning(
                self, tr("Launcher update"),
                tr("The new version was downloaded, but the executable could not be replaced.<br><br>"
                   "This usually happens when another launcher window is open, an antivirus "
                   "blocks the swap, or the folder is not writable. Close the other "
                   "instances and open the launcher again."),
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
                except Exception:  # noqa: BLE001 — no .exe published: nothing to do
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
                self, tr("Launcher update"),
                tr("A new launcher version is available (published on <b>{date}</b>)."
                   "<br><br>Update now? The launcher will restart.", date=remote.format_mdtm(rf.mdtm)),
                confirm_label=tr("Update"), cancel_label=tr("Not now"),
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
        self._set_busy(True, tr("Downloading the new launcher version…"))

        def work(ctx):
            with self.server.connect() as ftp:
                ftp.cwd(su.remote_dir)
                remote.download(ftp, su.file_name, new_exe, rf.size, on_progress=ctx.progress)

        def done(_):
            self.status.setText(tr("Restarting to apply the update…"))
            self_update.apply(new_exe, rf.mdtm, rf.size)
            QApplication.instance().quit()

        def fail(exc):
            self._self_updating = False
            self._fail(tr("Launcher update"), exc)

        Task.start_new(self, work, done, fail, on_progress=self.progress.setValue)

    def closeEvent(self, event):
        if self._busy and not messages.confirm(
            self, tr("Operation in progress"),
            tr("A download or installation is in progress. Close anyway?"),
            confirm_label=tr("Close"), danger=True,
        ):
            event.ignore()
            return
        super().closeEvent(event)
