"""Gera `assets/app.ico` (multi-resolução) a partir da marca desenhada em código.

Uso: python -m tools.make_icon [--accent #7C5CFF]
"""

import argparse
import struct
import sys
from pathlib import Path

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QPainter

from launcher.ui.icons import paint_mark

SIZES = (16, 24, 32, 48, 64, 128, 256)
ROOT = Path(__file__).resolve().parent.parent


def render_png(size: int, accent: str) -> bytes:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    pad = max(0.0, size * 0.04)
    paint_mark(p, QRectF(pad, pad, size - 2 * pad, size - 2 * pad), QColor(accent))
    p.end()
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(data)


def build_ico(images: dict) -> bytes:
    """ICO com entradas PNG (formato aceito pelo Windows Vista em diante)."""
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, png in images.items():
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        blobs += png
        offset += len(png)
    return header + entries + blobs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--accent", default="#7C5CFF")
    parser.add_argument("--out", type=Path, default=ROOT / "assets" / "app.ico")
    args = parser.parse_args()

    QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"])
    images = {s: render_png(s, args.accent) for s in SIZES}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(build_ico(images))
    print(f"Ícone gravado em {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
