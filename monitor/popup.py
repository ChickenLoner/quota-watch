"""Popup window using pywebview with Edge WebView2."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import re
import shutil
import subprocess
import threading
import time
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, Any

_GWL_EXSTYLE        = -20
_WS_EX_APPWINDOW    = 0x00040000
_WS_EX_TOOLWINDOW   = 0x00000080

import webview  # type: ignore[import-untyped]

from . import __version__
from .formatting import elapsed_pct, field_period

if TYPE_CHECKING:
    from .app import App

_HTML_DIR       = Path(__file__).parent / 'html'
_HTML_FILE      = _HTML_DIR / 'popup.html'
_POPUP_W_FOCUS  = 360
_POPUP_W_GRID   = 440
_BASELINE_DPI   = 96

_BG_DARK = '#14161c'

_PROVIDER_DOTS = {
    'claude':      '#c2683f',
    'codex':       '#5b8def',
    'windsurf':    '#2bb3a3',
    'antigravity': '#b07ae0',
}

_CHANGELOG_URLS: dict[str, str] = {
    'claude':      'https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md',
    'codex':       'https://github.com/openai/codex/releases',
    'antigravity': 'https://github.com/google-antigravity/antigravity-cli/blob/main/CHANGELOG.md',
}
_CHANGELOG_LABELS: dict[str, str] = {
    'codex':       'CODEX CLI',
    'antigravity': 'AGY CLI',
}
CHANGELOG_URL = _CHANGELOG_URLS['claude']


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


_RE_AUTH_HINTS: dict[str, str] = {
    'claude':      'claude auth login',
    'codex':       'codex login',
    'antigravity': 'open Antigravity to refresh',
}

_ORDER = ['claude', 'codex', 'windsurf', 'antigravity']


def _bar_entry(f: Any) -> dict[str, Any]:
    pct      = f.utilization
    resets   = f.resets_at or ''
    period   = field_period(f.key)
    time_pct = elapsed_pct(resets, period) if period else None
    warn     = time_pct is not None and pct > time_pct
    sev      = 'crit' if pct >= 90 else ('warn' if warn else 'ok')
    return {
        'key':        f.key,
        'label':      f.label,
        'pct':        round(pct, 1),
        'sev':        sev,
        'resets_at':  resets or None,
    }


def _extra_usage(snap_data: Any) -> dict[str, Any] | None:
    extra_data = snap_data.extras.get('extra_usage') if snap_data else None
    if not extra_data or not extra_data.get('is_enabled'):
        return None
    limit = extra_data.get('monthly_limit', 0) or 0
    if limit <= 0:
        return None
    used = extra_data.get('used_credits', 0) or 0
    pct  = used / limit * 100
    return {
        'pct_text':   f'{pct:.0f}%',
        'fill_pct':   max(0.0, min(1.0, pct / 100)),
        'spent_text': f'{used / 100:.2f} / {limit / 100:.2f}',
    }


def _run_version(path: str) -> str:
    try:
        proc = subprocess.run(
            [path, '--version'], capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        out = (proc.stdout or proc.stderr or '').strip()
        m = re.search(r'(\d+\.\d+[\.\d]*)', out)
        return m.group(1) if m else ''
    except Exception:
        return ''


def _fetch_installs() -> list[dict[str, str]]:
    try:
        from .claude_cli import find_installations
        return [{'name': i.name, 'version': i.version} for i in find_installations()]
    except Exception:
        return []


def _fetch_codex_installs() -> list[dict[str, str]]:
    path = shutil.which('codex')
    if not path:
        return []
    v = _run_version(path)
    return [{'name': 'CLI', 'version': v}] if v else []


def _find_agy_path() -> str | None:
    path = shutil.which('agy')
    if not path:
        local = Path(os.environ.get('LOCALAPPDATA', '')) / 'agy' / 'bin' / 'agy.exe'
        if local.is_file():
            return str(local)
    return path


def _fetch_agy_installs() -> list[dict[str, str]]:
    path = _find_agy_path()
    if not path:
        return []
    v = _run_version(path)
    return [{'name': 'CLI', 'version': v}] if v else []


def _installs() -> list[dict[str, str]]:
    return _cached('claude', _fetch_installs)


def _codex_installs() -> list[dict[str, str]]:
    return _cached('codex', _fetch_codex_installs)


def _agy_installs() -> list[dict[str, str]]:
    return _cached('agy', _fetch_agy_installs)


_SEV_RANK = {'crit': 0, 'err': 1, 'warn': 2, 'ok': 3}

_install_cache: dict[str, tuple[float, list]] = {}
_INSTALL_TTL = 300  # seconds


def _cached(key: str, fn) -> list:
    now = time.time()
    entry = _install_cache.get(key)
    if entry and now - entry[0] < _INSTALL_TTL:
        return entry[1]
    result = fn()
    _install_cache[key] = (now, result)
    return result


def prewarm_installs() -> None:
    """Pre-populate install caches from a background thread at startup."""
    _installs()
    _codex_installs()
    _agy_installs()


def _provider_entry(pid: str, s: Any, claude_profile: dict[str, Any] | None) -> dict[str, Any]:
    stale = getattr(s, 'stale', False)
    bars = [_bar_entry(f) for f in s.fields]  # always build; stale snapshots carry cached fields

    auth_status = 'connected'
    re_auth_hint = None
    error_text = None
    if s.auth_error:
        auth_status = 'auth_error'
        re_auth_hint = _RE_AUTH_HINTS.get(pid)
        error_text = s.error
    elif stale:
        auth_status = 'connected'
        error_text = s.error
    elif s.error:
        auth_status = 'error'
        error_text = s.error

    email = None
    plan = None
    if pid == 'claude' and claude_profile:
        email = claude_profile.get('email') or None
        plan = claude_profile.get('plan') or None
    elif s.extras:
        email = s.extras.get('email') or None
        plan_raw = s.extras.get('plan_type') or s.extras.get('plan_name') or ''
        plan = plan_raw.replace('_', ' ').title() if plan_raw else None

    if bars:
        worst = min((b['sev'] for b in bars), key=lambda sev: _SEV_RANK[sev])
    else:
        worst = 'err' if auth_status != 'connected' else 'ok'

    entry: dict[str, Any] = {
        'id':          pid,
        'name':        s.provider_name,
        'dot':         _PROVIDER_DOTS.get(pid, '#7d8694'),
        'plan':        plan,
        'email':       email,
        'authStatus':  auth_status,
        'reAuthHint':  re_auth_hint,
        'errorText':   error_text,
        'stale':       stale,
        'statusSev':   worst,
        'bars':           bars,
        'extra':          None,
        'installs':       None,
        'changelog_url':  _CHANGELOG_URLS.get(pid),
        'changelog_label': _CHANGELOG_LABELS.get(pid),
    }
    if pid == 'claude':
        entry['extra'] = _extra_usage(s)
        entry['installs'] = _installs()
    elif pid == 'codex':
        entry['installs'] = _codex_installs()
    elif pid == 'antigravity':
        entry['installs'] = _agy_installs()
        entry['canLaunchAgy'] = _find_agy_path() is not None
    return entry


def _build_payload(app: App) -> dict[str, Any]:
    """Build the JSON payload for the popup JS init()."""
    snap      = app.cache_snapshot()
    snapshots = snap.snapshots  # dict[provider_id, UsageSnapshot]

    claude_profile = None
    if snap.profile:
        account = snap.profile.get('account', {})
        org     = snap.profile.get('organization', {})
        plan    = org.get('organization_type', '').replace('_', ' ').title()
        claude_profile = {'email': account.get('email', ''), 'plan': plan or ''}

    ordered_ids = [pid for pid in _ORDER if pid in snapshots] + \
                  [pid for pid in snapshots if pid not in _ORDER]

    providers = [_provider_entry(pid, snapshots[pid], claude_profile) for pid in ordered_ids]

    # Status (footer)
    has_any_data = any(not s.error and s.fields for s in snapshots.values())
    if not has_any_data:
        status: dict[str, Any] = {
            'text':     snap.last_error[:120] if snap.last_error else 'SYNCING...',
            'is_error': bool(snap.last_error),
        }
    else:
        status = {
            'last_success_time': snap.last_success_time,
            'next_poll_time':    app.next_poll_time,
            'refreshing':        False,
            'error':             snap.last_error[:120] if snap.last_error else None,
        }

    return {
        'version':   f'v{__version__}',
        'status':    status,
        'providers': providers,
    }


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

    def launch_agy(self) -> None:
        """Launch agy as a detached background process (no-op if not found)."""
        agy_path = _find_agy_path()
        if agy_path:
            subprocess.Popen(
                [agy_path],
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                close_fds=True,
            )


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
        if hwnd:
            user32 = ctypes.windll.user32
            fg = user32.GetForegroundWindow()
            if fg and fg != hwnd:
                tid_fg = user32.GetWindowThreadProcessId(fg, None)
                tid_hw = user32.GetWindowThreadProcessId(hwnd, None)
                if tid_fg != tid_hw:
                    user32.AttachThreadInput(tid_fg, tid_hw, True)
                    user32.BringWindowToTop(hwnd)
                    user32.SetForegroundWindow(hwnd)
                    user32.AttachThreadInput(tid_fg, tid_hw, False)
                else:
                    user32.SetForegroundWindow(hwnd)
            else:
                user32.SetForegroundWindow(hwnd)

    def _close(self) -> None:
        try:
            self._win.destroy()
        except Exception:
            pass
