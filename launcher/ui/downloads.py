"""Standalone downloads: configurable tabs with files from the server."""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QHBoxLayout, QHeaderView, QProgressBar, QPushButton, QTabBar, QTreeWidget,
    QTreeWidgetItem,
)

from .. import remote
from ..i18n import tr
from . import icons, messages, theme
from .widgets import FramelessDialog, Task, label


class DownloadsDialog(FramelessDialog):
    def __init__(self, tabs, server: remote.RemoteServer, base_dir: Path, parent=None):
        super().__init__(tr("Downloads"), width=560, parent=parent)
        self._tabs = list(tabs)
        self._server = server
        self._base_dir = Path(base_dir)
        self._cache: dict[int, list] = {}
        self._busy = False

        self.tab_bar = QTabBar()
        self.tab_bar.setDrawBase(False)
        self.tab_bar.setExpanding(False)
        for tab in self._tabs:
            self.tab_bar.addTab(tab.label)
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        self.body.addWidget(self.tab_bar)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("FILE"), tr("SIZE"), tr("MODIFIED")])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.tree.setMinimumHeight(280)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)
        self.tree.itemChanged.connect(lambda *_: self._update_buttons())
        self.body.addWidget(self.tree)

        sel = QHBoxLayout()
        self.btn_all = QPushButton(tr("Select all"))
        self.btn_all.clicked.connect(lambda: self._check_all(True))
        self.btn_none = QPushButton(tr("Clear selection"))
        self.btn_none.clicked.connect(lambda: self._check_all(False))
        self.btn_folder = QPushButton(tr("Open folder"))
        self.btn_folder.setIcon(icons.icon("folder", theme.palette().muted, 16))
        self.btn_folder.clicked.connect(self._open_folder)
        sel.addWidget(self.btn_all)
        sel.addWidget(self.btn_none)
        sel.addStretch()
        sel.addWidget(self.btn_folder)
        self.body.addLayout(sel)

        self.status = label("", "muted")
        self.body.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.body.addWidget(self.progress)
        self.dest = label("", "caption", wrap=True)
        self.body.addWidget(self.dest)

        row = QHBoxLayout()
        row.addStretch()
        self.btn_download = QPushButton(tr("Download selected"))
        self.btn_download.setProperty("variant", "primary")
        self.btn_download.setIcon(icons.icon("download", theme.palette().on_accent, 16,
                                             disabled_color=theme.palette().faint))
        self.btn_download.clicked.connect(self._download)
        row.addWidget(self.btn_download)
        self.body.addLayout(row)

        self._on_tab_changed(0)

    # -- tabs -------------------------------------------------------------
    def _tab(self):
        return self._tabs[self.tab_bar.currentIndex()]

    def _destination(self) -> Path:
        return self._base_dir / self._tab().destination

    def _on_tab_changed(self, index: int):
        self.progress.setValue(0)
        self.dest.setText(tr("Destination: {path}", path=messages.path_html(self._destination())))
        if index in self._cache:
            self._populate(self._cache[index])
        else:
            self._load(index)

    def _load(self, index: int):
        tab = self._tabs[index]
        self.tree.clear()
        self._set_busy(True)
        self.status.setText(tr("Connecting to the server…"))

        def work(ctx):
            with self._server.connect() as ftp:
                ctx.status(tr("Listing files…"))
                ftp.cwd(tab.remote_dir)
                # .sha256 files only verify downloads; they are not listed.
                entries = [e for e in remote.list_files(ftp)
                           if not e.name.lower().endswith(".sha256")]
                names = {e.name.lower() for e in entries}
                for extra in tab.extra_files:
                    if extra.name.lower() in names:
                        continue
                    info = remote.file_info(ftp, extra.remote_dir, extra.name)
                    entries.append(remote.RemoteFile(info.name, info.mdtm, info.size,
                                                     extra.remote_dir, extra.badge))
            return sorted(entries, key=lambda e: e.name.lower())

        def done(entries):
            self._cache[index] = entries
            self._set_busy(False)
            if self.tab_bar.currentIndex() == index:
                self._populate(entries)

        def fail(exc):
            self._set_busy(False)
            self.status.setText(tr("Could not load the list."))
            messages.error(self, tr("Downloads"),
                           tr("Could not list the files:<br>{error}", error=messages.describe(exc)))

        Task.start_new(self, work, done, fail, on_status=self.status.setText)

    def _populate(self, entries):
        self.tree.blockSignals(True)
        self.tree.clear()
        badge_color = QBrush(QColor(theme.palette().accent))
        for entry in entries:
            name = f"{entry.name}   ·  {entry.badge}" if entry.badge else entry.name
            item = QTreeWidgetItem([name, remote.format_size(entry.size), remote.format_mdtm(entry.mdtm)])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setData(0, Qt.ItemDataRole.UserRole, entry)
            for col in (1, 2):
                item.setTextAlignment(col, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setForeground(col, QBrush(QColor(theme.palette().muted)))
            if entry.badge:
                item.setForeground(0, badge_color)
            self.tree.addTopLevelItem(item)
        self.tree.blockSignals(False)
        self.status.setText(tr("{count} file(s) available.", count=len(entries)) if entries
                            else tr("No files available in this tab."))
        self._update_buttons()

    # -- selection --------------------------------------------------------
    def _items(self):
        return [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]

    def _selected(self):
        return [i.data(0, Qt.ItemDataRole.UserRole) for i in self._items()
                if i.checkState(0) == Qt.CheckState.Checked]

    def _check_all(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for item in self._items():
            item.setCheckState(0, state)

    def _update_buttons(self):
        if self._busy:
            return
        count = len(self._selected())
        self.btn_download.setEnabled(count > 0)
        self.btn_download.setText(tr("Download {count} file(s)", count=count) if count else tr("Download selected"))

    def _set_busy(self, busy: bool):
        self._busy = busy
        for w in (self.tab_bar, self.tree, self.btn_all, self.btn_none, self.btn_download, self.close_button):
            w.setEnabled(not busy)
        if not busy:
            self._update_buttons()

    def _open_folder(self):
        folder = self._destination()
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)  # noqa: S606 — opens Explorer on the destination folder

    # -- download ---------------------------------------------------------
    def _download(self):
        entries = self._selected()
        if not entries:
            return
        destination = self._destination()
        existing = [e.name for e in entries if (destination / e.name).exists()]
        if existing:
            names = "<br>".join(f"• {n}" for n in existing[:6])
            more = "<br>" + tr("… and {count} more", count=len(existing) - 6) if len(existing) > 6 else ""
            if not messages.confirm(self, tr("Replace files?"),
                                    tr("These files already exist and will be replaced:<br><br>{names}{more}",
                                       names=names, more=more),
                                    confirm_label=tr("Replace")):
                return

        self._set_busy(True)

        def work(ctx):
            ok, errors = 0, []
            with self._server.connect() as ftp:
                for n, entry in enumerate(entries, start=1):
                    ctx.status(tr("Downloading {n}/{total}: {name}", n=n, total=len(entries), name=entry.name))
                    ctx.progress(0)
                    try:
                        ftp.cwd(entry.directory)
                        remote.download(ftp, entry.name, destination / entry.name,
                                        entry.size, on_progress=ctx.progress)
                        ok += 1
                    except Exception as exc:  # noqa: BLE001 — one file does not abort the rest
                        errors.append((entry.name, str(exc)))
            return ok, errors

        def done(result):
            ok, errors = result
            self._set_busy(False)
            self.progress.setValue(100 if ok and not errors else 0)
            if errors:
                lines = "<br>".join(f"• {n}: {m}" for n, m in errors[:5])
                self.status.setText(tr("{ok} downloaded, {failed} failed.", ok=ok, failed=len(errors)))
                messages.warning(self, tr("Partial download"),
                                 tr("<b>{ok}</b> file(s) downloaded.<br><br>Failures:<br>{lines}",
                                    ok=ok, lines=lines))
            else:
                self.status.setText(tr("{ok} file(s) saved to {path}.", ok=ok, path=destination))
                self._check_all(False)

        def fail(exc):
            self._set_busy(False)
            messages.error(self, tr("Downloads"),
                           tr("The download failed:<br>{error}", error=messages.describe(exc)))

        Task.start_new(self, work, done, fail, on_progress=self.progress.setValue,
                       on_status=self.status.setText)

    def reject(self):
        if not self._busy:
            super().reject()

    def closeEvent(self, event):
        if self._busy:
            event.ignore()
        else:
            super().closeEvent(event)
