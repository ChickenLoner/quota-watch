"""Popup window using pywebview with Edge WebView2."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import threading
import time
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

_GWL_EXSTYLE        = -20
_WS_EX_APPWINDOW    = 0x00040000
_WS_EX_TOOLWINDOW   = 0x00000080

import webview  # type: ignore[import-untyped]

from .payload import CHANGELOG_URL, _build_payload

if TYPE_CHECKING:
    from .app import App

_HTML_DIR       = Path(__file__).parent / 'html'
_HTML_FILE      = _HTML_DIR / 'popup.html'
_POPUP_W_FOCUS  = 360
_POPUP_W_GRID   = 440
_BASELINE_DPI   = 96

_BG_DARK = '#14161c'


class _MonitorInfo(ctypes.Structure):
    _fields_ = [
        ('cbSize',    ctypes.wintypes.DWORD),
        ('rcMonitor', ctypes.wintypes.RECT),
        ('rcWork',    ctypes.wintypes.RECT),
        ('dwFlags',   ctypes.wintypes.DWORD),
    ]


def _dpi_scale() -> float:
    try:
        hdc = ctypes.windll.user32.GetDC(None)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(None, hdc)
        return dpi / _BASELINE_DPI
    except Exception:
        return 1.0


def _tray_position(popup_w: int, popup_h: int) -> tuple[int, int]:
    """Return (x, y) in logical pixels to place popup near the system tray."""
    try:
        tray = ctypes.windll.user32.FindWindowW('Shell_TrayWnd', None)
        mon  = ctypes.windll.user32.MonitorFromWindow(tray, 2)
        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(_MonitorInfo)
        ctypes.windll.user32.GetMonitorInfoW(mon, ctypes.byref(info))

        work  = info.rcWork
        moni  = info.rcMonitor
        scale = _dpi_scale()

        if work.bottom < moni.bottom:   # taskbar bottom
            x = int((work.right  - popup_w * scale) / scale)
            y = int((work.bottom - popup_h * scale) / scale)
        elif work.top > moni.top:       # taskbar top
            x = int((work.right - popup_w * scale) / scale)
            y = int(work.top / scale)
        elif work.left > moni.left:     # taskbar left
            x = int(work.left / scale)
            y = int((work.bottom - popup_h * scale) / scale)
        else:                           # taskbar right
            x = int((work.right - popup_w * scale) / scale)
            y = int((work.bottom - popup_h * scale) / scale)

        return x, y
    except Exception:
        return 40, 40


class _PopupApi:
    """Python methods exposed to popup JS via pywebview."""

    def __init__(self, popup: UsagePopup) -> None:
        self._popup = popup

    def close(self) -> None:
        self._popup._close()

    def open_url(self, url: str = '') -> None:
        webbrowser.open(url or CHANGELOG_URL)

    def refresh(self) -> None:
        """Trigger an immediate data fetch and push updated payload to JS."""
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _do_refresh(self) -> None:
        self._popup._app._update()
        payload = _build_payload(self._popup._app)
        try:
            self._popup._win.evaluate_js(f'refreshDone({json.dumps(payload)})')
        except Exception:
            pass

    def report_size(self, width: int, height: int) -> None:
        """JS calls this after each render with the exact panel dimensions.
        Always resizes to match — no grow-only tricks needed because JS
        passes the exact intended size for the current layout mode.
        """
        w, h = int(width), int(height)
        if w > 0 and h > 0 and (w != self._popup._last_w or h != self._popup._last_h):
            self._popup._last_w = w
            self._popup._last_h = h
            x, y = _tray_position(w, h)
            self._popup._win.move(x, y)
            self._popup._win.resize(w, h)

    def report_height(self, height: int) -> None:
        """Backward-compat shim — delegates to report_size with last known width."""
        self.report_size(self._popup._last_w, height)


class UsagePopup:
    """Opens the popup window and blocks the calling thread until closed."""

    def __init__(self, app: App) -> None:
        self._app          = app
        self._closed       = threading.Event()
        self._last_w       = _POPUP_W_FOCUS
        self._last_h       = 20
        self._unique_title = f'__quota_watch_{id(self)}__'

        api = _PopupApi(self)

        self._win = webview.create_window(
            self._unique_title, url=str(_HTML_FILE),
            width=self._last_w, height=self._last_h,
            resizable=False, frameless=True, shadow=False,
            easy_drag=False, on_top=True, hidden=True,
            background_color=_BG_DARK,
            js_api=api,
        )
        self._win.events.loaded += self._on_loaded
        self._win.events.closed += self._closed.set

        self._closed.wait()

    def _on_loaded(self) -> None:
        # Hide from taskbar: set TOOLWINDOW, clear APPWINDOW
        hwnd = ctypes.windll.user32.FindWindowW(None, self._unique_title)
        if hwnd:
            ex = ctypes.windll.user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, _GWL_EXSTYLE,
                (ex | _WS_EX_TOOLWINDOW) & ~_WS_EX_APPWINDOW,
            )

        # Position near tray before showing (JS will call report_size after init)
        x, y = _tray_position(self._last_w, self._last_h)
        self._win.move(x, y)

        # Inject data into page
        payload = _build_payload(self._app)
        self._win.evaluate_js(f'init({json.dumps(payload)})')

        # Show after positioning (avoids flash at wrong position)
        self._win.show()

        # Force keyboard focus — on_top=True keeps the window visually topmost
        # but doesn't steal keyboard focus from the previously active window.
        # Attach the foreground window's input queue to the WebView2 UI thread
        # (the thread that owns hwnd) so SetForegroundWindow is permitted even
        # after the RegisterHotKey foreground-lock has expired (~200 ms).
        # Must use hwnd's owning thread — NOT GetCurrentThreadId(), which is
        # the pywebview callback thread and unrelated to the window message queue.
        # SetForegroundWindow's return value is unreliable under the lock, so
        # verify with GetForegroundWindow and retry a few times instead of
        # trusting a single call.
        if hwnd:
            user32 = ctypes.windll.user32
            fg = user32.GetForegroundWindow()
            tid_fg = user32.GetWindowThreadProcessId(fg, None) if fg else 0
            tid_hw = user32.GetWindowThreadProcessId(hwnd, None)
            attached = False
            if fg and fg != hwnd and tid_fg != tid_hw:
                user32.AttachThreadInput(tid_fg, tid_hw, True)
                attached = True
            user32.BringWindowToTop(hwnd)
            for _ in range(5):
                user32.SetForegroundWindow(hwnd)
                if user32.GetForegroundWindow() == hwnd:
                    break
                time.sleep(0.05)
            if attached:
                user32.AttachThreadInput(tid_fg, tid_hw, False)
            user32.SetFocus(hwnd)

        # Belt-and-suspenders: ask the WebView2 renderer itself to take DOM
        # focus now that the OS-level window is (hopefully) active. Without
        # this, keydown listeners on `document` can stay dead even though
        # the window looks frontmost, since OS activation doesn't always
        # hand keyboard input down into the Chromium child control.
        try:
            self._win.evaluate_js('focusWindow()')
        except Exception:
            pass

    def _close(self) -> None:
        try:
            self._win.destroy()
        except Exception:
            pass
