"""SOC-themed system tray icon renderer."""
from __future__ import annotations

import ctypes
import winreg
from typing import Callable

from PIL import Image, ImageDraw, ImageFont


ICON_SIZE = 64   # internal canvas - Windows scales down to 16x16
_BAR_W  = 56
_BAR_H  = 9
_BAR_Y1 = 4
_BAR_Y2 = 34
_TEXT_Y = 16   # countdown text top edge (in gap between bars)

_DARK_BG = (10, 15, 10, 255)
_GREEN   = (0, 255, 65, 255)
_YELLOW  = (255, 230, 0, 255)
_RED     = (255, 50, 50, 255)
_CYAN    = (34, 225, 255, 255)
_DIM     = (0, 80, 20, 180)
_TRACK   = (20, 40, 20, 255)

try:
    _FONT = ImageFont.load_default(size=12)
except TypeError:
    _FONT = None

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


def _bar_color(pct: float) -> tuple[int, int, int, int]:
    if pct >= 90:
        return _RED
    if pct >= 60:
        return _YELLOW
    return _GREEN


def create_icon(pct_top: float, pct_bottom: float, countdown: str = '', error: bool = False) -> Image.Image:
    """Draw a 64x64 SOC-themed dual-bar tray icon with optional session countdown."""
    img = Image.new('RGBA', (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, ICON_SIZE - 1, ICON_SIZE - 1], fill=_DARK_BG)

    if error:
        d.text((24, 10), '!', fill=_RED)
        return img

    for bar_y, pct in ((_BAR_Y1, pct_top), (_BAR_Y2, pct_bottom)):
        fill_w = max(1, int(_BAR_W * min(pct, 100) / 100))
        color  = _bar_color(pct)
        d.rectangle([4, bar_y, 4 + _BAR_W, bar_y + _BAR_H], fill=_TRACK)
        d.rectangle([4, bar_y, 4 + fill_w,  bar_y + _BAR_H], fill=color)
        d.rectangle([4, bar_y, 4 + _BAR_W, bar_y + _BAR_H], outline=_DIM)

    # Countdown text centered in gap between bars
    if countdown and _FONT:
        bbox = d.textbbox((0, 0), countdown, font=_FONT)
        tw   = bbox[2] - bbox[0]
        tx   = max(0, (ICON_SIZE - tw) // 2)
        d.text((tx, _TEXT_Y), countdown, fill=_CYAN, font=_FONT)

    d.line([(0, ICON_SIZE - 1), (ICON_SIZE - 1, ICON_SIZE - 1)], fill=(*_GREEN[:3], 80), width=1)

    return img


def create_status_icon(text: str) -> Image.Image:
    """Draw a text-only status icon (e.g. '!', 'ERR')."""
    img = Image.new('RGBA', (ICON_SIZE, ICON_SIZE), _DARK_BG)
    d = ImageDraw.Draw(img)
    d.text((4, 12), text[:3], fill=_RED)
    return img
