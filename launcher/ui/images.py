"""Images for the interface (banners, screenshots, icons), loaded off the UI thread.

A reference is an http(s) URL — downloaded once and cached on disk by
`GitHubClient.fetch_file` — or a file path, relative to the configuration file.
Icons of installed executables come from the Windows shell.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QFileInfo, QObject, QSize, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QFileIconProvider

from .widgets import Task


def is_url(ref: str) -> bool:
    return ref.lower().startswith(("http://", "https://"))


class ImageStore(QObject):
    """Loads images by reference; `loaded(ref)` fires when one becomes available."""

    loaded = pyqtSignal(str)

    def __init__(self, client, base_dir: Path | None, parent=None):
        super().__init__(parent)
        self._client = client
        self._base_dir = Path(base_dir) if base_dir else None
        self._images: dict[str, QPixmap] = {}
        self._pending: set[str] = set()
        self._failed: set[str] = set()
        self._exe_icons: dict[str, QPixmap] = {}

    def get(self, ref: str) -> QPixmap | None:
        """The image if it is ready; otherwise starts loading it and returns None."""
        if not ref:
            return None
        if ref in self._images:
            return self._images[ref]
        if ref in self._pending or ref in self._failed:
            return None
        self._pending.add(ref)

        def work(_ctx):
            path = self._client.fetch_file(ref) if is_url(ref) else self._resolve(ref)
            image = QImage(str(path))
            if image.isNull():
                raise ValueError(f"not an image: {ref}")
            return image

        def done(image: QImage):
            self._pending.discard(ref)
            self._images[ref] = QPixmap.fromImage(image)
            self.loaded.emit(ref)

        def fail(_exc):
            self._pending.discard(ref)
            self._failed.add(ref)

        Task.start_new(self, work, done, fail)
        return None

    def image(self, ref: str) -> QImage | None:
        pixmap = self.get(ref)
        return pixmap.toImage() if pixmap is not None else None

    def _resolve(self, ref: str) -> Path:
        path = Path(ref)
        if not path.is_absolute() and self._base_dir is not None:
            path = self._base_dir / path
        return path

    def exe_icon(self, exe: Path, size: int = 64) -> QPixmap | None:
        """Icon of an executable (cached by path); None if the shell has none."""
        key = f"{exe}|{size}"
        if key in self._exe_icons:
            return self._exe_icons[key]
        if not Path(exe).is_file():
            return None
        icon = QFileIconProvider().icon(QFileInfo(str(exe)))
        pixmap = icon.pixmap(QSize(size, size)) if not icon.isNull() else QPixmap()
        result = pixmap if not pixmap.isNull() else None
        self._exe_icons[key] = result
        return result

    def forget_exe_icon(self, exe: Path):
        prefix = f"{exe}|"
        for key in [k for k in self._exe_icons if k.startswith(prefix)]:
            del self._exe_icons[key]
