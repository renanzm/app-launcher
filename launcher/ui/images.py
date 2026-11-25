"""Images for the interface (banners, screenshots, icons), loaded off the UI thread.

A reference is an http(s) URL — downloaded once and cached on disk by
`GitHubClient.fetch_file` — or a file path, relative to the configuration file.
App icons come from the executables themselves: the installed .exe, or the
.exe published in the release (read in parts, see `launcher/peicon.py`).
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QFileInfo, QObject, QSize, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QFileIconProvider

from .. import peicon
from .widgets import Task


def is_url(ref: str) -> bool:
    return ref.lower().startswith(("http://", "https://"))


def image_from_icon(data: bytes, kind: str) -> QImage:
    return QImage.fromData(data, "PNG" if kind == "png" else "ICO")


class ImageStore(QObject):
    """Loads images by key; `loaded(key)` fires when one becomes available."""

    loaded = pyqtSignal(str)

    def __init__(self, client, base_dir: Path | None, parent=None):
        super().__init__(parent)
        self._client = client
        self._base_dir = Path(base_dir) if base_dir else None
        self._images: dict[str, QPixmap] = {}
        self._pending: set[str] = set()
        self._failed: set[str] = set()
        self._exe_icons: dict[str, QPixmap | None] = {}

    def _load(self, key: str, work) -> QPixmap | None:
        """Cached pixmap for `key`, or None while `work()` (-> QImage) runs on a worker thread."""
        if key in self._images:
            return self._images[key]
        if key in self._pending or key in self._failed:
            return None
        self._pending.add(key)

        def done(image: QImage):
            self._pending.discard(key)
            if image is None or image.isNull():
                self._failed.add(key)
                return
            self._images[key] = QPixmap.fromImage(image)
            self.loaded.emit(key)

        def fail(_exc):
            self._pending.discard(key)
            self._failed.add(key)

        Task.start_new(self, lambda _ctx: work(), done, fail)
        return None

    def get(self, ref: str) -> QPixmap | None:
        """An image by URL or path, if ready; otherwise starts loading it."""
        if not ref:
            return None

        def work():
            path = self._client.fetch_file(ref) if is_url(ref) else self._resolve(ref)
            return QImage(str(path))

        return self._load(ref, work)

    def image(self, ref: str) -> QImage | None:
        pixmap = self.get(ref)
        return pixmap.toImage() if pixmap is not None else None

    def release_icon(self, asset) -> QPixmap | None:
        """Icon of a release's .exe asset, if ready; otherwise starts fetching it."""
        if asset is None:
            return None
        key = f"asset-icon:{asset.id or asset.download_url}"

        def work():
            path = self._client.fetch_asset_icon(asset)
            if path is None:
                return None
            return image_from_icon(path.read_bytes(), path.suffix.lstrip(".").lower())

        return self._load(key, work)

    def _resolve(self, ref: str) -> Path:
        path = Path(ref)
        if not path.is_absolute() and self._base_dir is not None:
            path = self._base_dir / path
        return path

    def exe_icon(self, exe: Path, size: int = 64) -> QPixmap | None:
        """Icon of an installed executable, at the largest size it carries.

        Read from the file's resources (256 px when available); the Windows shell
        is the fallback. Cached by path and modification time.
        """
        exe = Path(exe)
        try:
            stamp = exe.stat().st_mtime_ns
        except OSError:
            return None
        key = f"{exe}|{stamp}"
        if key in self._exe_icons:
            return self._exe_icons[key]
        result = None
        try:
            data, kind = peicon.extract_from_file(exe)
            image = image_from_icon(data, kind)
            if not image.isNull():
                result = QPixmap.fromImage(image)
        except (OSError, peicon.IconError):
            pass
        if result is None:
            icon = QFileIconProvider().icon(QFileInfo(str(exe)))
            pixmap = icon.pixmap(QSize(size, size)) if not icon.isNull() else QPixmap()
            result = pixmap if not pixmap.isNull() else None
        self._exe_icons[key] = result
        return result

    def forget_exe_icon(self, exe: Path):
        prefix = f"{exe}|"
        for key in [k for k in self._exe_icons if k.startswith(prefix)]:
            del self._exe_icons[key]
