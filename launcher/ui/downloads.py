"""Downloads avulsos: abas configuráveis com arquivos do servidor."""

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
from . import icons, messages, theme
from .widgets import FramelessDialog, Task, label


class DownloadsDialog(FramelessDialog):
    def __init__(self, tabs, server: remote.RemoteServer, base_dir: Path, parent=None):
        super().__init__("Downloads", width=560, parent=parent)
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
        self.tree.setHeaderLabels(["ARQUIVO", "TAMANHO", "MODIFICADO"])
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
        self.btn_all = QPushButton("Marcar todos")
        self.btn_all.clicked.connect(lambda: self._check_all(True))
        self.btn_none = QPushButton("Limpar seleção")
        self.btn_none.clicked.connect(lambda: self._check_all(False))
        self.btn_folder = QPushButton("Abrir pasta")
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
        self.btn_download = QPushButton("Baixar selecionados")
        self.btn_download.setProperty("variant", "primary")
        self.btn_download.setIcon(icons.icon("download", theme.palette().on_accent, 16,
                                             disabled_color=theme.palette().faint))
        self.btn_download.clicked.connect(self._download)
        row.addWidget(self.btn_download)
        self.body.addLayout(row)

        self._on_tab_changed(0)

    # -- abas -------------------------------------------------------------
    def _tab(self):
        return self._tabs[self.tab_bar.currentIndex()]

    def _destination(self) -> Path:
        return self._base_dir / self._tab().destination

    def _on_tab_changed(self, index: int):
        self.progress.setValue(0)
        self.dest.setText(f"Destino: {messages.path_html(self._destination())}")
        if index in self._cache:
            self._populate(self._cache[index])
        else:
            self._load(index)

    def _load(self, index: int):
        tab = self._tabs[index]
        self.tree.clear()
        self._set_busy(True)
        self.status.setText("Conectando ao servidor…")

        def work(ctx):
            with self._server.connect() as ftp:
                ctx.status("Listando arquivos…")
                ftp.cwd(tab.remote_dir)
                # Os .sha256 só servem para verificar os downloads; não são listados.
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
            self.status.setText("Não foi possível carregar a lista.")
            messages.error(self, "Downloads", f"Não foi possível listar os arquivos:<br>{messages.describe(exc)}")

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
        self.status.setText(f"{len(entries)} arquivo(s) disponível(is)." if entries
                            else "Nenhum arquivo disponível nesta aba.")
        self._update_buttons()

    # -- seleção ----------------------------------------------------------
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
        self.btn_download.setText(f"Baixar {count} arquivo(s)" if count else "Baixar selecionados")

    def _set_busy(self, busy: bool):
        self._busy = busy
        for w in (self.tab_bar, self.tree, self.btn_all, self.btn_none, self.btn_download, self.close_button):
            w.setEnabled(not busy)
        if not busy:
            self._update_buttons()

    def _open_folder(self):
        folder = self._destination()
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)  # noqa: S606 — abre o Explorer na pasta de destino

    # -- download ---------------------------------------------------------
    def _download(self):
        entries = self._selected()
        if not entries:
            return
        destination = self._destination()
        existing = [e.name for e in entries if (destination / e.name).exists()]
        if existing:
            names = "<br>".join(f"• {n}" for n in existing[:6])
            more = f"<br>… e mais {len(existing) - 6}" if len(existing) > 6 else ""
            if not messages.confirm(self, "Substituir arquivos?",
                                    f"Estes arquivos já existem e serão substituídos:<br><br>{names}{more}",
                                    confirm_label="Substituir"):
                return

        self._set_busy(True)

        def work(ctx):
            ok, errors = 0, []
            with self._server.connect() as ftp:
                for n, entry in enumerate(entries, start=1):
                    ctx.status(f"Baixando {n}/{len(entries)}: {entry.name}")
                    ctx.progress(0)
                    try:
                        ftp.cwd(entry.directory)
                        remote.download(ftp, entry.name, destination / entry.name,
                                        entry.size, on_progress=ctx.progress)
                        ok += 1
                    except Exception as exc:  # noqa: BLE001 — um arquivo não aborta os demais
                        errors.append((entry.name, str(exc)))
            return ok, errors

        def done(result):
            ok, errors = result
            self._set_busy(False)
            self.progress.setValue(100 if ok and not errors else 0)
            if errors:
                lines = "<br>".join(f"• {n}: {m}" for n, m in errors[:5])
                self.status.setText(f"{ok} baixado(s), {len(errors)} com erro.")
                messages.warning(self, "Download parcial",
                                 f"<b>{ok}</b> arquivo(s) baixado(s).<br><br>Falhas:<br>{lines}")
            else:
                self.status.setText(f"{ok} arquivo(s) salvo(s) em {destination}.")
                self._check_all(False)

        def fail(exc):
            self._set_busy(False)
            messages.error(self, "Downloads", f"Falha durante o download:<br>{messages.describe(exc)}")

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
