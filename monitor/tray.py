"""System tray icon renderer."""
from __future__ import annotations

import ctypes
import winreg
from pathlib import Path
from typing import Callable

from PIL import Image

ICON_SIZE = 64   # internal canvas - Windows scales down to 16x16
_ICON_PATH = Path(__file__).parent / 'icon.png'
_app_icon_cache: Image.Image | None = None

THEME_REG_KEY   = r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize'
THEME_REG_VALUE = 'SystemUsesLightTheme'


def taskbar_is_light() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, THEME_REG_KEY) as k:
            v, _ = winreg.QueryValueEx(k, THEME_REG_VALUE)
            return bool(v)
    except OSError:
        return False


def watch_theme(callback: Callable[[], None]) -> None:
    """Block-watch registry for taskbar theme changes; call callback on change."""
    import threading

    def _watch() -> None:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, THEME_REG_KEY,
                access=winreg.KEY_NOTIFY | winreg.KEY_READ,
            )
            while True:
                ctypes.windll.advapi32.RegNotifyChangeKeyValue(
                    key.handle, False, 0x00000004, None, False,
                )
                callback()
        except Exception:
            pass

    threading.Thread(target=_watch, daemon=True).start()


def app_icon() -> Image.Image:
    """Static app-icon image for the tray - usage/error state is conveyed via the hover tooltip, not the icon."""
    global _app_icon_cache
    if _app_icon_cache is None:
        src = Image.open(_ICON_PATH).convert('RGBA')
        src.thumbnail((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
        canvas = Image.new('RGBA', (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
        canvas.paste(src, ((ICON_SIZE - src.width) // 2, (ICON_SIZE - src.height) // 2), src)
        _app_icon_cache = canvas
    return _app_icon_cache
