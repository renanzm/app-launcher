"""Main window, in the style of a game launcher.

    ┌──────────┬──────────────────────────────────────────────┐
    │  brand   │ HOME  RELEASE NOTES  GITHUB↗ …        ⚙ — ✕  │
    │──────────│                                              │
    │ library  │        artwork · title · release cards       │
    │  (apps)  │                                              │
    │          ├──────────────────────────────────────────────┤
    │ actions  │ versions │ status + progress │ ⚙ │  ▶ PLAY   │
    └──────────┴──────────────────────────────────────────────┘

Network work (checking releases, downloading, installing) always runs in a
`Task`, so the window never freezes.
"""

from __future__ import annotations

import math
import os
import shutil
import sys
import time
import webbrowser
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QHBoxLayout, QMenu, QPushButton, QToolButton, QVBoxLayout, QWidget,
)

from .. import __version__, auth, github, installer, remote, self_update, sources
from ..i18n import localized, tr
from ..state import default_cache_dir
from . import icons, messages, native, theme
from .actionbar import ActionBar
from .downloads import DownloadsDialog
from .images import ImageStore
from .library import Sidebar
from .settings import SettingsDialog
from .stage import HomePage, NotesPage, Pages, Stage, format_date
from .widgets import DragArea, Task

_TEMP_DIR_NAME = ".launcher-tmp"
WINDOW_SIZE = QSize(1200, 720)
RECHECK_INTERVAL_MS = 30 * 60 * 1000


@dataclass
class AppState:
    info: sources.AppInfo | None = None
    checking: bool = False
    error: str = ""
    process: object = None                 # subprocess.Popen of the running app
    task: Task | None = None               # running install
    phase: str = ""                        # "", "download", "install"
    progress: float | None = None
    last: tuple | None = None              # (bytes done, total) of the download
    samples: deque = field(default_factory=lambda: deque(maxlen=40))


class TopBar(QWidget):
    """Navigation tabs and external links on the left, window buttons on the right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(26, 0, 0, 0)
        lay.setSpacing(0)
        self.tabs = QButtonGroup(self)
        self.tabs.setExclusive(True)
        self.btn_home = self._nav(tr("Home"), checkable=True)
        self.btn_notes = self._nav(tr("Release notes"), checkable=True)
        self.tabs.addButton(self.btn_home, 0)
        self.tabs.addButton(self.btn_notes, 1)
        lay.addWidget(self.btn_home)
        lay.addWidget(self.btn_notes)
        self.links = QHBoxLayout()
        self.links.setSpacing(0)
        lay.addLayout(self.links)
        lay.addWidget(DragArea(), 1)
        self.right = QHBoxLayout()
        self.right.setContentsMargins(0, 0, 0, 0)
        self.right.setSpacing(2)
        lay.addLayout(self.right)
        lay.addSpacing(10)
        self.window_buttons = QHBoxLayout()
        self.window_buttons.setSpacing(0)
        lay.addLayout(self.window_buttons)
        lay.setAlignment(self.window_buttons, Qt.AlignmentFlag.AlignTop)

    @staticmethod
    def _nav(text: str, checkable: bool = False, external: bool = False) -> QPushButton:
        btn = QPushButton(text.upper())
        btn.setProperty("role", "nav")
        btn.setCheckable(checkable)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if external:
            btn.setIcon(icons.icon("external", theme.palette().faint, 12))
            btn.setIconSize(QSize(12, 12))
            btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        return btn

    def set_links(self, links, on_click):
        while self.links.count():
            item = self.links.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for text, url in links:
            btn = self._nav(text, external=True)
            btn.setToolTip(url)
            btn.clicked.connect(lambda _=False, u=url: on_click(u))
            self.links.addWidget(btn)

    def add_icon(self, button):
        self.right.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)

    def add_window_button(self, name: str, tooltip: str, object_name: str) -> QToolButton:
        pal = theme.palette()
        btn = QToolButton()
        btn.setObjectName(object_name)
        btn.setIcon(icons.icon(name, pal.muted, 16))
        btn.setIconSize(QSize(16, 16))
        btn.setFixedSize(48, 40)
        btn.setToolTip(tooltip)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.window_buttons.addWidget(btn)
        return btn


class MainWindow(QWidget):
    def __init__(self, config, store, base_dir: Path, user: str = "", password: str = "",
                 self_update_failed: bool = False):
        super().__init__()
        self.setObjectName("LauncherWindow")
        self.setWindowTitle(config.app_name)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.config = config
        self.store = store
        self.base_dir = Path(base_dir)
        self.root = installer.resolve_root(self.base_dir, config.install_root)
        self.client = github.GitHubClient(config.github.token, default_cache_dir(config.app_id),
                                          timeout=config.github.timeout)
        self.server = remote.RemoteServer(config.server, store) if config.server else None
        self.images = ImageStore(self.client, config.source.parent if config.source else self.base_dir, self)
        self._session = auth.session_env(config.auth, user, password)
        self._session_user, self._session_password = user, password
        self._self_update_failed = self_update_failed
        self._self_update_pending = bool(config.self_update)
        self._self_updating = False
        self._queue: list[str] = []
        self._native = False
        self._fade = None
        self.states = {app.id: AppState() for app in config.apps}
        self._index = 0

        self._build()
        self.images.loaded.connect(self._on_image_loaded)

        last = store.pref("last_app", "")
        index = next((i for i, a in enumerate(config.apps) if a.id == last), 0)
        self._select(index, animate=False)

        self._poll = QTimer(self)
        self._poll.timeout.connect(self._poll_processes)
        self._poll.start(1500)
        self._recheck = QTimer(self)
        self._recheck.timeout.connect(lambda: self._check_all(quiet=True))
        self._recheck.start(RECHECK_INTERVAL_MS)
        QShortcut(QKeySequence("F5"), self, activated=lambda: self._check(self.app, quiet=False))
        QTimer.singleShot(150, self._startup_checks)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        pal = theme.palette()
        screen = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        size = QSize(WINDOW_SIZE)
        if screen is not None:
            size = QSize(min(size.width(), screen.width() - 40), min(size.height(), screen.height() - 40))
        self.setFixedSize(size)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(self.config.app_name, f"v{__version__}", self.config.apps, self._accent)
        self.sidebar.app_selected.connect(lambda i: self._select(i, animate=True))
        if self.config.downloads and self.server is not None:
            btn = QPushButton(tr("Downloads").upper())
            btn.setProperty("role", "sidebar-action")
            btn.setIcon(icons.icon("box", pal.muted, 16))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(self._open_downloads)
            self.sidebar.add_action(btn)
            self.btn_downloads = btn
        else:
            self.btn_downloads = None
        self.sidebar.footer.setText(self._footer_text())
        self.sidebar.footer.setVisible(bool(self._footer_text()))
        root.addWidget(self.sidebar)

        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        root.addLayout(main, 1)

        self.stage = Stage(self.images)
        stage_lay = QVBoxLayout(self.stage)
        stage_lay.setContentsMargins(0, 0, 0, 0)
        stage_lay.setSpacing(0)
        self.topbar = TopBar()
        stage_lay.addWidget(self.topbar)
        self.pages = Pages()
        self.home = HomePage()
        self.notes = NotesPage(self.images)
        self.pages.addWidget(self.home)
        self.pages.addWidget(self.notes)
        stage_lay.addWidget(self.pages, 1)
        main.addWidget(self.stage, 1)

        self.home.open_notes.connect(self._show_notes)
        self.home.open_url.connect(webbrowser.open)
        self.notes.open_url.connect(webbrowser.open)
        self.topbar.tabs.idClicked.connect(self._set_page)
        self.topbar.btn_home.setChecked(True)

        self.btn_settings = self._icon_button("settings", tr("Settings"))
        self.btn_settings.clicked.connect(self._open_settings)
        self.topbar.add_icon(self.btn_settings)
        self.btn_report = self._icon_button("bug", tr("Report a bug"))
        self.btn_report.clicked.connect(lambda: webbrowser.open(self.config.support_url))
        self.btn_report.setVisible(bool(self.config.support_url))
        self.topbar.add_icon(self.btn_report)
        btn_min = self.topbar.add_window_button("minimize", tr("Minimize"), "WindowButton")
        btn_min.clicked.connect(self.showMinimized)
        btn_close = self.topbar.add_window_button("close", tr("Close"), "WindowClose")
        btn_close.clicked.connect(self.close)

        self.bar = ActionBar()
        self.bar.play.clicked.connect(self._on_primary)
        self.bar.options.clicked.connect(self._show_options_menu)
        self.bar.cancel.clicked.connect(self._cancel_install)
        main.addWidget(self.bar)

    @staticmethod
    def _icon_button(name: str, tooltip: str) -> QToolButton:
        pal = theme.palette()
        btn = QToolButton()
        btn.setObjectName("IconButton")
        btn.setIcon(icons.icon(name, pal.muted, 18, disabled_color=pal.faint))
        btn.setIconSize(QSize(18, 18))
        btn.setFixedSize(34, 34)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def _footer_text(self) -> str:
        parts = []
        if self._session_user:
            parts.append(tr("Signed in as {user}", user=self._session_user))
        if self.config.is_example:
            parts.append(tr("using the example configuration"))
        return " · ".join(parts)

    # ------------------------------------------------------------------
    # Native frame
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if not self._native:
            self._native = True
            native.enable(self, theme.palette().border_strong)
        if self._fade is None:
            self.setWindowOpacity(0.0)
            self._fade = QPropertyAnimation(self, b"windowOpacity", self)
            self._fade.setDuration(240)
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
            self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._fade.start()

    def nativeEvent(self, event_type, message):
        handled = native.handle_event(event_type, message) if self._native else None
        return handled if handled is not None else (False, 0)

    # ------------------------------------------------------------------
    # Helpers about apps
    # ------------------------------------------------------------------

    @property
    def app(self):
        return self.config.apps[self._index]

    def _accent(self, app) -> str:
        return app.accent_color or self.config.accent_color

    def _install_dir(self, app) -> Path:
        return installer.install_path(self.root, app)

    def _record(self, app) -> dict | None:
        """Installed record, if the install folder still exists."""
        if not self._install_dir(app).is_dir():
            return None
        return self.store.installed(app.id)

    def _executable(self, app) -> str:
        return installer.executable_for(app, self._record(app))

    def _is_installed(self, app) -> bool:
        return installer.is_installed(self.root, app, self._executable(app))

    def _latest(self, app) -> sources.Version | None:
        info = self.states[app.id].info
        return info.latest if info else None

    def _update_available(self, app) -> bool:
        latest = self._latest(app)
        if latest is None or not self._is_installed(app):
            return False
        record = self._record(app)
        return record is None or record.get("key") != latest.key

    def _running(self, app) -> bool:
        proc = self.states[app.id].process
        return proc is not None and proc.poll() is None

    def _busy_app(self):
        return next((a for a in self.config.apps if self.states[a.id].task is not None), None)

    # ------------------------------------------------------------------
    # Selection and rendering
    # ------------------------------------------------------------------

    def _select(self, index: int, animate: bool = True):
        if not 0 <= index < len(self.config.apps):
            return
        changed = index != self._index
        self._index = index
        app = self.app
        self.store.set_pref("last_app", app.id)
        self.sidebar.select(index)
        state = self.states[app.id]
        if state.info is None and not state.checking and not state.error:
            self._check(app, quiet=True)
        self._render(animate=animate and changed)
        if changed and self.pages.currentIndex() == 1 and not self._history(app):
            self._set_page(0)

    def _history(self, app):
        info = self.states[app.id].info
        return list(info.history) if info and app.source == "github" else []

    def _render(self, animate: bool = False):
        app = self.app
        accent = self._accent(app)
        state = self.states[app.id]
        info = state.info
        record = self._record(app)
        installed_key = (record or {}).get("key", "")
        self.stage.set_app(app.id, app.name, accent, localized(app.banner), localized(app.screenshot),
                           animate=animate)
        description = localized(app.description) or (info.repository.description if info and info.repository else "")
        self.home.show_app(app, info, accent, installed_key, description, localized(app.tagline), animate)
        latest = info.latest if info else None
        self.notes.show_history(self._history(app), installed_key, latest.key if latest else "")
        self.topbar.btn_notes.setEnabled(bool(self._history(app)))
        self.topbar.set_links(self._links(app), webbrowser.open)
        self.bar.set_accent(accent)
        for a in self.config.apps:
            self._render_tile(a)
        self._render_bar()

    def _links(self, app):
        links = []
        repo = self.states[app.id].info.repository if self.states[app.id].info else None
        if app.github:
            base = repo.html_url if repo and repo.html_url else f"https://github.com/{app.github}"
            links.append(("GitHub", base))
            if repo is None or repo.has_issues:
                links.append((tr("Issues"), f"{base}/issues"))
            if repo is not None and repo.homepage:
                links.append((tr("Website"), repo.homepage))
        for link in app.links:
            links.append((localized(link.label), link.url))
        return links[:5]

    def _render_tile(self, app):
        pal = theme.palette()
        tile = self.sidebar.tiles[self.config.apps.index(app)]
        state = self.states[app.id]
        accent = QColor(self._accent(app)).lighter(125).name()
        installed = self._is_installed(app)
        # Icon: configured image > the executable's own icon > initials.
        pixmap = self.images.get(app.icon) if app.icon else None
        if pixmap is None and installed:
            pixmap = self.images.exe_icon(self._install_dir(app) / self._executable(app))
        tile.set_icon(pixmap)

        if state.task is not None:
            if state.phase == "download" and state.progress is not None:
                text = tr("Downloading · {percent}%", percent=int(state.progress * 100))
            else:
                text = tr("Installing…")
            tile.set_status(text, accent, progress=state.progress or 0.0)
        elif self._running(app):
            tile.set_status(tr("Running"), pal.success)
        elif self._update_available(app):
            tile.set_status(tr("Update · {version}", version=self._latest(app).label), accent, badge=True)
        elif installed:
            label_ = sources.describe_record(self._record(app)) or tr("Installed")
            tile.set_status(label_, pal.muted)
        elif state.checking and state.info is None:
            tile.set_status(tr("Checking…"), pal.faint)
        elif state.error and state.info is None:
            tile.set_status(tr("Unavailable"), pal.warning)
        else:
            tile.set_status(tr("Not installed"), pal.faint)

    def _render_bar(self):
        pal = theme.palette()
        app = self.app
        state = self.states[app.id]
        latest = self._latest(app)
        record = self._record(app)
        installed = self._is_installed(app)
        update = self._update_available(app)
        busy_app = self._busy_app()
        accent_light = QColor(self._accent(app)).lighter(125).name()

        # -- info grid ---------------------------------------------------
        if installed:
            self.bar.set_info("installed", sources.describe_record(record) or tr("Unknown version"))
        else:
            self.bar.set_info("installed", tr("Not installed"), pal.faint)
        if latest is not None:
            text = latest.label if app.source == "ftp" else f"{latest.label} · {format_date(latest.published)}"
            self.bar.set_info("latest", text, accent_light if update else "")
        else:
            self.bar.set_info("latest", tr("Checking…") if state.checking else "—", pal.faint)
        size = latest.size if latest is not None and latest.size else None
        self.bar.set_info("size", remote.format_size(size) if size else "—")

        # -- primary button ----------------------------------------------
        play = self.bar.play
        if state.task is not None:
            play.set_state(tr("Downloading") if state.phase == "download" else tr("Installing"), "download", "busy")
            play.setEnabled(False)
        elif self._running(app):
            play.set_state(tr("Running"), "check", "running")
            play.setEnabled(False)
        elif update:
            play.set_state(tr("Update"), "download")
            play.setEnabled(busy_app is None and not self._self_updating)
        elif installed:
            play.set_state(tr("Launch"), "play")
            play.setEnabled(not self._self_updating)
        else:
            play.set_state(tr("Install"), "download")
            play.setEnabled(latest is not None and latest.installable and busy_app is None
                            and not self._self_updating)
        self.bar.options.setEnabled(state.task is None and not self._self_updating)

        # -- status --------------------------------------------------------
        if state.task is not None or self._self_updating:
            return                                   # the task keeps the status up to date
        self.bar.set_busy(False)
        status, color = "", ""
        if self._running(app):
            status = tr("{name} is running.", name=app.name)
        elif update:
            status = tr("Update available: {new} (you have {old}).", new=latest.label,
                        old=sources.describe_record(record) or tr("an unknown version"))
            color = accent_light
        elif installed:
            status = tr("Ready to launch.") if app.source == "github" or latest else tr("Ready.")
        elif latest is not None and latest.installable:
            status = tr("{version} is ready to install.", version=latest.label)
        elif state.checking:
            status = tr("Checking for the latest version…")
        elif state.info is not None and state.info.problem:
            status, color = state.info.problem, pal.warning
        elif state.error:
            status, color = state.error, pal.warning
        if busy_app is not None and busy_app is not app and not installed:
            status = tr("Waiting for {name} to finish installing.", name=busy_app.name)
        if state.info is not None and state.info.offline:
            status += "  " + tr("(offline: showing saved information)")
        self.bar.status.setText(status)
        self.bar.status.setStyleSheet(f"color: {color};" if color else "")
        folder = self._install_dir(app)
        hint = (tr("Installed in {path}", path=folder) if installed
                else tr("Will be installed in {path}", path=folder))
        self.bar.hint.setText(hint)

    def _on_image_loaded(self, ref: str):
        for app in self.config.apps:
            if ref == app.icon:
                self._render_tile(app)

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    def _set_page(self, index: int):
        self.pages.setCurrentIndex(index)
        self.stage.set_dimmed(index == 1)
        button = self.topbar.tabs.button(index)
        if button is not None and not button.isChecked():
            button.setChecked(True)

    def _show_notes(self, index: int = 0):
        if not self._history(self.app):
            return
        self._set_page(1)
        self.notes.select(index)

    # ------------------------------------------------------------------
    # Checking versions
    # ------------------------------------------------------------------

    def _source(self, app):
        return sources.make_source(app, self.client, self.server)

    def _check_all(self, quiet: bool = True):
        for app in self.config.apps:
            self._check(app, quiet=quiet)

    def _check(self, app, quiet: bool = True):
        state = self.states[app.id]
        if state.checking or state.task is not None:
            return
        state.checking = True
        state.error = ""
        if app is self.app:
            self._render_bar()
        self._render_tile(app)
        source = self._source(app)

        def done(info: sources.AppInfo):
            state.checking = False
            first = state.info is None
            state.info = info
            if app is self.app:
                self._render(animate=False) if not first else self._render_after_first_check()
            else:
                self._render_tile(app)
            if not quiet and app is self.app and not self._update_available(app) and self._is_installed(app):
                self.bar.status.setText(tr("All good · you already have the latest version."))
            self._maybe_queue_update(app)

        def fail(exc):
            state.checking = False
            state.error = messages.describe(exc).replace("<br>", " ")
            if app is self.app:
                self._render_bar()
            self._render_tile(app)
            if not quiet:
                messages.error(self, tr("Check for updates"), messages.describe(exc))

        Task.start_new(self, lambda ctx: source.check(), done, fail)

    def _render_after_first_check(self):
        # The first answer fills the page: fade the new content in.
        self._render(animate=False)
        self.home._animate_in()

    def _maybe_queue_update(self, app):
        if (self.store.pref("auto_update", False) and self._update_available(app)
                and not self._running(app) and app.id not in self._queue):
            self._queue.append(app.id)
        self._process_queue()

    def _process_queue(self):
        if self._self_update_pending or self._self_updating or self._busy_app() is not None:
            return
        while self._queue:
            app = self.config.app(self._queue.pop(0))
            if app is not None and self._update_available(app) and not self._running(app):
                self._install(app, auto=True)
                return

    # ------------------------------------------------------------------
    # Installing
    # ------------------------------------------------------------------

    def _on_primary(self):
        app = self.app
        if self._update_available(app) or not self._is_installed(app):
            self._install(app)
        else:
            self._launch(app, self._executable(app))

    def _install(self, app, auto: bool = False):
        state = self.states[app.id]
        version = self._latest(app)
        if version is None or not version.installable or state.task is not None:
            return
        if self._running(app):
            messages.warning(self, tr("Install"), tr("Close {name} before updating it.", name=app.name))
            return
        target = self._install_dir(app)
        temp_dir = self.root / _TEMP_DIR_NAME / app.id
        source = self._source(app)

        def work(ctx):
            ctx.status("download")
            downloaded = source.download(version, temp_dir,
                                         on_progress=lambda done, total: ctx.report((done, total)),
                                         cancelled=ctx.cancelled)
            ctx.status("install")
            ctx.report(None, force=True)
            try:
                return installer.install_download(downloaded, target, app,
                                                  on_progress=lambda pct: ctx.report(pct / 100.0))
            finally:
                downloaded.unlink(missing_ok=True)
                shutil.rmtree(temp_dir, ignore_errors=True)
                try:
                    temp_dir.parent.rmdir()          # only when no other download uses it
                except OSError:
                    pass

        def on_status(phase: str):
            state.phase = phase
            state.progress = 0.0 if phase == "install" else None
            if app is self.app:
                self._render_bar()
                self._show_progress(app)

        def on_report(payload):
            if state.phase == "download" and isinstance(payload, tuple):
                done, total = payload
                state.samples.append((time.monotonic(), done))
                state.progress = done / total if total else None
                state.last = payload
            elif isinstance(payload, float):
                state.progress = payload
            if app is self.app:
                self._show_progress(app)
            self._render_tile(app)

        def finished(executable: str):
            published = version.published.isoformat() if version.published else ""
            self.store.set_installed(app.id, version.key, version.label, published, version.size, executable)
            self.images.forget_exe_icon(target / executable)
            self._end_task(app)
            self.bar.status.setText(tr("{name} {version} installed.", name=app.name, version=version.label)
                                    if app is self.app else self.bar.status.text())
            self._process_queue()

        def failed(exc):
            self._end_task(app)
            if isinstance(exc, github.DownloadCancelled):
                if app is self.app:
                    self.bar.status.setText(tr("Download cancelled."))
            elif not auto:
                messages.error(self, tr("Install"), messages.describe(exc))
            else:
                state.error = messages.describe(exc).replace("<br>", " ")
                self._render_bar()
            self._process_queue()

        state.phase, state.progress = "download", None
        state.samples.clear()
        state.task = Task.start_new(self, work, finished, failed, on_status=on_status, on_report=on_report)
        self._render_tile(app)
        if app is self.app:
            self._render_bar()
            self._show_progress(app)

    def _show_progress(self, app):
        state = self.states[app.id]
        if state.task is None:
            return
        self.bar.set_busy(True, cancellable=state.phase == "download")
        self.bar.progress.set_value(state.progress)
        self.bar.status.setStyleSheet("")
        self.bar.detail.setText(f"{int(state.progress * 100)}%" if state.progress is not None else "")
        if state.phase == "download":
            latest = self._latest(app)
            self.bar.status.setText(tr("Downloading {name} {version}…", name=app.name,
                                       version=latest.label if latest else ""))
            self.bar.hint.setText(self._speed_text(state) or tr("Connecting…"))
        else:
            self.bar.status.setText(tr("Installing {name}…", name=app.name))
            self.bar.hint.setText(str(self._install_dir(app)))

    @staticmethod
    def _speed_text(state: AppState) -> str:
        if not state.last:
            return ""
        done, total = state.last
        parts = [f"{remote.format_size(done)} / {remote.format_size(total)}" if total
                 else remote.format_size(done)]
        samples = [s for s in state.samples if s[0] >= time.monotonic() - 4]
        if len(samples) >= 2 and samples[-1][0] > samples[0][0]:
            speed = (samples[-1][1] - samples[0][1]) / (samples[-1][0] - samples[0][0])
            if speed > 0:
                parts.append(f"{remote.format_size(int(speed))}/s")
                if total:
                    seconds = max(1, int(math.ceil((total - done) / speed)))
                    parts.append(tr("{time} left", time=f"{seconds // 60}:{seconds % 60:02d}"))
        return "  ·  ".join(parts)

    def _end_task(self, app):
        state = self.states[app.id]
        state.task = None
        state.phase, state.progress = "", None
        state.samples.clear()
        state.last = None
        self.bar.set_busy(False)
        self._render() if app is self.app else self._render_tile(app)

    def _cancel_install(self):
        state = self.states[self.app.id]
        if state.task is not None:
            state.task.cancel()
            self.bar.status.setText(tr("Cancelling…"))

    # ------------------------------------------------------------------
    # Launching
    # ------------------------------------------------------------------

    def _launch(self, app, executable: str):
        path = self._install_dir(app) / executable
        env = installer.build_launch_env(app, self.store.option_values(app), self._session)
        try:
            proc = installer.launch(path, env)
        except Exception as exc:  # noqa: BLE001
            messages.error(self, tr("Open application"), messages.describe(exc))
            return
        if executable == self._executable(app):
            self.states[app.id].process = proc
        if self.store.pref("keep_open", False):
            self._render()
        else:
            self.close()

    def _poll_processes(self):
        for app in self.config.apps:
            state = self.states[app.id]
            if state.process is not None and state.process.poll() is not None:
                state.process = None
                if app is self.app:
                    self._render_bar()
                self._render_tile(app)
                self._maybe_queue_update(app)

    # ------------------------------------------------------------------
    # Options menu
    # ------------------------------------------------------------------

    def _show_options_menu(self):
        pal = theme.palette()
        app = self.app
        menu = QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        installed = self._is_installed(app)
        folder_exists = self._install_dir(app).is_dir()
        actions = {}
        extras = {}
        if self._update_available(app) and not self._running(app):
            actions["play"] = menu.addAction(icons.icon("play", pal.muted, 16), tr("Launch without updating"))
        for extra in app.extra_actions:
            act = menu.addAction(icons.icon("play", pal.muted, 16), extra.label)
            act.setEnabled(installed)
            extras[act] = extra
        if actions or extras:
            menu.addSeparator()
        actions["check"] = menu.addAction(icons.icon("refresh", pal.muted, 16), tr("Check for updates"))
        if self._history(app):
            actions["notes"] = menu.addAction(icons.icon("notes", pal.muted, 16), tr("Release notes"))
        actions["folder"] = menu.addAction(icons.icon("folder", pal.muted, 16), tr("Open install folder"))
        actions["folder"].setEnabled(folder_exists)
        actions["integrity"] = menu.addAction(icons.icon("shield", pal.muted, 16), tr("Verify integrity"))
        if app.options:
            actions["options"] = menu.addAction(icons.icon("settings", pal.muted, 16),
                                                tr("Options of {name}", name=app.name))
        menu.addSeparator()
        actions["uninstall"] = menu.addAction(icons.icon("trash", pal.danger, 16), tr("Uninstall"))
        actions["uninstall"].setEnabled(folder_exists and not self._running(app))

        button = self.bar.options
        pos = button.mapToGlobal(button.rect().topLeft())
        chosen = menu.exec(QPoint(pos.x(), pos.y() - menu.sizeHint().height() - 6))
        if chosen is None:
            return
        if chosen is actions.get("play"):
            self._launch(app, self._executable(app))
        elif chosen in extras:
            self._launch(app, extras[chosen].executable)
        elif chosen is actions.get("check"):
            self._check(app, quiet=False)
        elif chosen is actions.get("notes"):
            self._show_notes(0)
        elif chosen is actions.get("folder"):
            os.startfile(self._install_dir(app))  # noqa: S606
        elif chosen is actions.get("integrity"):
            self._show_integrity(app)
        elif chosen is actions.get("options"):
            self._open_settings()
        elif chosen is actions.get("uninstall"):
            self._uninstall(app)

    def _show_integrity(self, app):
        folder = self._install_dir(app)
        executable = self._executable(app)
        exe = folder / executable if executable else folder
        record = self._record(app)
        pal = theme.palette()

        def line(ok: bool, text: str, detail: str):
            color = pal.success if ok else pal.danger
            mark = "✓" if ok else "✗"
            return (f"<span style='color:{color}'>{mark}</span>&nbsp; {text}: "
                    f"<span style='color:{pal.muted}'>{detail}</span>")

        rows = [
            line(folder.is_dir(), tr("Install folder"), tr("found") if folder.is_dir() else tr("not found")),
            line(bool(executable) and exe.is_file(), tr("Executable <i>{name}</i>", name=executable or "?"),
                 tr("found") if executable and exe.is_file() else tr("not found")),
            line(record is not None, tr("Version record"),
                 sources.describe_record(record) if record else tr("missing")),
            "&nbsp;&nbsp;&nbsp; " + tr("Files in folder: <b>{count}</b>", count=installer.count_files(folder))
            + f" · {remote.format_size(installer.folder_size(folder))}",
        ]
        messages.info(self, tr("Integrity check"), f"<b>{app.name}</b><br><br>" + "<br>".join(rows))

    def _uninstall(self, app):
        folder = self._install_dir(app)
        if not messages.confirm(
            self, tr("Uninstall"),
            tr("Uninstall <b>{name}</b>?<br><br>All files in<br><i>{path}</i><br>will be deleted.",
               name=app.name, path=messages.path_html(folder)),
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
        self._render()
        self.bar.status.setText(tr("{name} was uninstalled.", name=app.name))

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------

    def _open_settings(self):
        SettingsDialog(self.config, self.store, self.app, self).exec()
        auth.persist_session_if_auto_login(
            self.store.pref("auto_login", False), self._session_user, self._session_password,
            lambda u, p: auth.save_login(self.store, u, p),
        )

    def _open_downloads(self):
        DownloadsDialog(self.config.downloads, self.server, self.base_dir, self).exec()

    # ------------------------------------------------------------------
    # Startup: launcher self-update, then app checks
    # ------------------------------------------------------------------

    def _startup_checks(self):
        self._check_all(quiet=True)
        if self._self_update_failed:
            self._self_update_pending = False
            messages.warning(
                self, tr("Launcher update"),
                tr("The new version was downloaded, but the executable could not be replaced.<br><br>"
                   "This usually happens when another launcher window is open, an antivirus "
                   "blocks the swap, or the folder is not writable. Close the other "
                   "instances and open the launcher again."),
            )
        elif self.config.self_update and self_update.is_frozen():
            self._check_self_update()
            return
        self._self_update_pending = False
        self._process_queue()

    def _self_update_done(self):
        self._self_update_pending = False
        self._process_queue()

    def _check_self_update(self):
        su = self.config.self_update

        def work(ctx):
            if su.source == "github":
                releases, _ = self.client.releases(su.github)
                for release in releases:
                    asset = github.pick_asset(release.assets, su.file_name)
                    if asset is not None:
                        return ("github", release, asset)
                return None
            with self.server.connect() as ftp:
                if not remote.try_cwd(ftp, su.remote_dir):
                    return None
                try:
                    return ("ftp", remote.stat(ftp, su.file_name), None)
                except Exception:  # noqa: BLE001 — no .exe published: nothing to do
                    return None

        def done(found):
            if not found:
                self._self_update_done()
                return
            kind, item, asset = found
            if kind == "github":
                if not github.is_newer(item.tag, __version__):
                    self._self_update_done()
                    return
                when, key, size = item.tag, item.tag, asset.size or 0
            else:
                rf = item
                if not rf.size:
                    self._self_update_done()
                    return
                record = self.store.install_record(self_update.RECORD_KEY)
                if not self_update.needs_update(record, rf.mdtm, rf.size, self_update.running_exe_size()):
                    if record is None:
                        self.store.set_install_record(self_update.RECORD_KEY, rf.mdtm, rf.size)
                    self._self_update_done()
                    return
                when, key, size = remote.format_mdtm(rf.mdtm), rf.mdtm, rf.size
            if not self.store.pref("auto_update_launcher", False) and not messages.confirm(
                self, tr("Launcher update"),
                tr("A new launcher version is available (<b>{version}</b>).<br><br>"
                   "Update now? The launcher will restart.", version=when),
                confirm_label=tr("Update"), cancel_label=tr("Not now"),
            ):
                self._self_update_done()
                return
            self._download_self_update(kind, item, asset, key, size)

        Task.start_new(self, work, done, lambda exc: self._self_update_done())

    def _download_self_update(self, kind, item, asset, key: str, size: int):
        su = self.config.self_update
        exe = Path(sys.executable)
        new_exe = exe.with_name(f"{exe.stem}.new.exe")
        self._self_updating = True
        self._render_bar()
        self.bar.set_busy(True)
        self.bar.status.setText(tr("Downloading the new launcher version…"))
        self.bar.progress.set_value(None)

        def work(ctx):
            report = lambda done, total: ctx.report(done / total if total else None)  # noqa: E731
            if kind == "github":
                self.client.download(asset, new_exe, on_progress=report)
            else:
                with self.server.connect() as ftp:
                    ftp.cwd(su.remote_dir)
                    remote.download(ftp, su.file_name, new_exe, item.size, on_bytes=report)

        def done(_):
            self.bar.status.setText(tr("Restarting to apply the update…"))
            self_update.apply(new_exe, key, size)
            QApplication.instance().quit()

        def fail(exc):
            self._self_updating = False
            self.bar.set_busy(False)
            self._render_bar()
            messages.error(self, tr("Launcher update"), messages.describe(exc))
            self._self_update_done()

        Task.start_new(self, work, done, fail, on_report=self.bar.progress.set_value)

    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if (self._busy_app() is not None or self._self_updating) and not messages.confirm(
            self, tr("Operation in progress"),
            tr("A download or installation is in progress. Close anyway?"),
            confirm_label=tr("Close"), danger=True,
        ):
            event.ignore()
            return
        for state in self.states.values():
            if state.task is not None:
                state.task.cancel()
        super().closeEvent(event)
