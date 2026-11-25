"""Native frame for frameless windows on Windows.

Qt's frameless windows have no shadow and square corners. Giving the window
the caption/thick-frame styles back (and then hiding that frame in
WM_NCCALCSIZE) lets the Desktop Window Manager draw its own shadow, the
Windows 11 rounded corners and the minimize/restore animations — at no
painting cost for us, unlike a translucent window with a drop-shadow effect.

Everything here is best effort: on failure (or off Windows) the window simply
stays a plain frameless window.
"""

from __future__ import annotations

import ctypes
import sys

GWL_STYLE = -16
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_SYSMENU = 0x00080000
WM_NCCALCSIZE = 0x0083
SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020   # NOSIZE|NOMOVE|NOZORDER|NOACTIVATE|FRAMECHANGED

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWCP_ROUND = 2


class _Margins(ctypes.Structure):
    _fields_ = [("left", ctypes.c_int), ("right", ctypes.c_int),
                ("top", ctypes.c_int), ("bottom", ctypes.c_int)]


def _colorref(hex_color: str) -> int:
    value = hex_color.lstrip("#")
    r, g, b = int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    return r | (g << 8) | (b << 16)


def enable(widget, border_color: str = "") -> bool:
    """Gives a frameless top-level widget the native shadow and rounded corners."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes.wintypes as wt

        hwnd = wt.HWND(int(widget.winId()))
        user32, dwmapi = ctypes.windll.user32, ctypes.windll.dwmapi
        get_style = user32.GetWindowLongPtrW
        set_style = user32.SetWindowLongPtrW
        get_style.restype = set_style.restype = ctypes.c_ssize_t
        get_style.argtypes = [wt.HWND, ctypes.c_int]
        set_style.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
        style = get_style(hwnd, GWL_STYLE)
        set_style(hwnd, GWL_STYLE, style | WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_SYSMENU)

        margins = _Margins(1, 1, 1, 1)
        dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))

        def attribute(attr: int, value: int):
            data = ctypes.c_int(value)
            dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(data), ctypes.sizeof(data))

        attribute(DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
        attribute(DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)      # Windows 11; ignored before
        if border_color:
            attribute(DWMWA_BORDER_COLOR, _colorref(border_color))
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_FLAGS)
        return True
    except Exception:  # noqa: BLE001 — cosmetic only
        return False


def handle_event(event_type, message):
    """For nativeEvent(): hides the frame that enable() added. Returns (True, 0) or None.

    Note: calling QWidget.nativeEvent() from Python crashes with PyQt6 6.12, so
    callers must return (False, 0) themselves when this returns None.
    """
    if event_type != b"windows_generic_MSG":
        return None
    try:
        import ctypes.wintypes as wt

        msg = wt.MSG.from_address(int(message))
        if msg.message == WM_NCCALCSIZE and msg.wParam:
            return True, 0
    except Exception:  # noqa: BLE001
        return None
    return None
