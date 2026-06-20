"""SOC popup window using pywebview with Edge WebView2."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import threading
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, Any

_GWL_EXSTYLE        = -20
_WS_EX_APPWINDOW    = 0x00040000
_WS_EX_TOOLWINDOW   = 0x00000080

import webview  # type: ignore[import-untyped]

from . import __version__
from .formatting import elapsed_pct, field_period, midnight_positions, time_until

if TYPE_CHECKING:
    from .app import App

_HTML_DIR  = Path(__file__).parent / 'html'
_HTML_FILE = _HTML_DIR / 'popup.html'
_POPUP_W   = 340
_BASELINE_DPI = 96

_TRANSLATIONS = {
    'title':              'QUOTA WATCH',
    'account':            'OPERATOR',
    'email':              'EMAIL',
    'plan':               'CLEARANCE',
    'auth_status':        'STATUS',
    'usage':              'QUOTA CHANNELS',
    'extra_usage':        'EXTRA USAGE',
    'claude_code':        'CLAUDE CODE',
    'changelog':          'CHANGELOG',
    'status_updated_s':   'UPDATED {s}S AGO',
    'status_updated':     'UPDATED {duration} AGO',
    'status_next_update': 'NEXT IN {duration}',
    'status_refreshing':  'SYNCING...',
    'duration_hm':        '{h}H {m}M',
    'duration_m':         '{m}M',
    'duration_s':         '{s}S',
}

CHANGELOG_URL = 'https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md'


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


def _bar_entry(provider_name: str, f: Any) -> dict[str, Any]:
    pct      = f.utilization
    resets   = f.resets_at or ''
    period   = field_period(f.key)
    time_pct = elapsed_pct(resets, period) if period else None
    warn     = pct >= 100 or (time_pct is not None and pct > time_pct)
    marker   = max(0.0, min(1.0, time_pct / 100)) if time_pct is not None else None
    return {
        'provider':    provider_name,
        'label':       f.label,
        'pct_text':    f'{pct:.0f}%',
        'fill_pct':    max(0.0, min(1.0, pct / 100)),
        'warn':        warn,
        'reset_text':  time_until(resets) if resets else '',
        'resets_at':   resets,
        'midnights':   midnight_positions(resets, period) if period else [],
        'marker_rel':  marker,
    }


def _build_payload(app: App) -> dict[str, Any]:
    """Build the JSON config+data payload for the popup JS init()."""
    snap      = app.cache_snapshot()
    snapshots = snap.snapshots  # dict[provider_id, UsageSnapshot]

    # Per-provider profiles (email + plan + auth_status) keyed by provider_name
    _RE_AUTH_HINTS: dict[str, str] = {
        'claude':      'claude auth login',
        'codex':       'codex login',
        'antigravity': 'open Antigravity to refresh',
    }
    provider_profiles: dict[str, Any] = {}
    if snap.profile:
        account = snap.profile.get('account', {})
        org     = snap.profile.get('organization', {})
        plan    = org.get('organization_type', '').replace('_', ' ').title()
        provider_profiles['Claude'] = {
            'email': account.get('email', ''),
            'plan':  plan or '',
        }
    for pid, s in snapshots.items():
        key   = s.provider_name
        entry = provider_profiles.setdefault(key, {})
        if s.auth_error:
            entry['auth_status'] = 'auth_error'
            hint = _RE_AUTH_HINTS.get(pid)
            if hint:
                entry['re_auth_hint'] = hint
        elif s.error:
            entry['auth_status'] = 'error'
        else:
            entry['auth_status'] = 'connected'
            if pid != 'claude':
                email    = s.extras.get('email', '')
                plan_raw = s.extras.get('plan_type') or s.extras.get('plan_name') or ''
                if email:
                    entry['email'] = email
                if plan_raw:
                    entry['plan'] = plan_raw.replace('_', ' ').title()

    # Keep legacy single `profile` key (Claude) for backward compat
    profile = provider_profiles.get('Claude')

    # Usage bars — one section per provider, ordered: claude, codex, windsurf, others
    _ORDER = ['claude', 'codex', 'windsurf', 'antigravity']
    ordered_ids = [pid for pid in _ORDER if pid in snapshots] + \
                  [pid for pid in snapshots if pid not in _ORDER]

    usage_bars: list[dict[str, Any]] = []
    for pid in ordered_ids:
        snap_data = snapshots[pid]
        if snap_data.error or not snap_data.fields:
            continue
        for f in snap_data.fields:
            usage_bars.append(_bar_entry(snap_data.provider_name, f))

    # Extra usage (Anthropic/Claude-specific)
    extra = None
    claude_snap = snapshots.get('claude')
    extra_data  = claude_snap.extras.get('extra_usage') if claude_snap else None
    if extra_data and extra_data.get('is_enabled'):
        limit = extra_data.get('monthly_limit', 0) or 0
        if limit > 0:
            used = extra_data.get('used_credits', 0) or 0
            pct  = used / limit * 100
            extra = {
                'pct_text':   f'{pct:.0f}%',
                'fill_pct':   max(0.0, min(1.0, pct / 100)),
                'spent_text': f'{used / 100:.2f} / {limit / 100:.2f}',
            }

    # Installations
    try:
        from .claude_cli import find_installations
        installs = [{'name': i.name, 'version': i.version} for i in find_installations()]
    except Exception:
        installs = []

    # Status
    has_any_data = any(not s.error and s.fields for s in snapshots.values())
    if not has_any_data:
        if snap.last_error:
            status: dict[str, Any] = {'text': snap.last_error[:120], 'is_error': True}
        else:
            status = {'text': 'SYNCING...', 'is_error': False}
    else:
        status = {
            'last_success_time': snap.last_success_time,
            'next_poll_time':    app.next_poll_time,
            'refreshing':        False,
            'error':             snap.last_error[:120] if snap.last_error else None,
        }

    # Provider tab names — all polled providers (errored ones show auth status)
    provider_names = [
        snapshots[pid].provider_name
        for pid in ordered_ids
        if pid in snapshots
    ]

    return {
        't':           _TRANSLATIONS,
        'app_version': f'v{__version__}',
        'data': {
            'providers':         provider_names,
            'provider_profiles': provider_profiles,
            'profile':           profile,
            'usage':             usage_bars,
            'extra':         extra,
            'installations': installs,
            'status':        status,
        },
    }


class _PopupApi:
    """Python methods exposed to popup JS via pywebview."""

    def __init__(self, popup: UsagePopup) -> None:
        self._popup = popup

    def close(self) -> None:
        self._popup._close()

    def open_url(self) -> None:
        webbrowser.open(CHANGELOG_URL)

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

    def report_height(self, height: int) -> None:
        """JS ResizeObserver calls this when content height changes."""
        h = int(height)
        if h > 0 and h != self._popup._last_height:
            self._popup._last_height = h
            x, y = _tray_position(_POPUP_W, h)
            self._popup._win.move(x, y)
            self._popup._win.resize(_POPUP_W, h)


class UsagePopup:
    """Opens the SOC popup and blocks the calling thread until closed."""

    def __init__(self, app: App) -> None:
        self._app          = app
        self._closed       = threading.Event()
        self._last_height  = 400
        self._unique_title = f'__quota_watch_{id(self)}__'

        api = _PopupApi(self)

        self._win = webview.create_window(
            self._unique_title, url=str(_HTML_FILE),
            width=_POPUP_W, height=self._last_height,
            resizable=False, frameless=True, shadow=False,
            easy_drag=False, on_top=True, hidden=True,
            background_color='#070b14',
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

        # Position near tray before showing
        x, y = _tray_position(_POPUP_W, self._last_height)
        self._win.move(x, y)
        self._win.resize(_POPUP_W, self._last_height)

        # Inject data into page
        payload = _build_payload(self._app)
        self._win.evaluate_js(f'init({json.dumps(payload)})')

        # Show after positioning (avoids flash at wrong position)
        self._win.show()

    def _close(self) -> None:
        try:
            self._win.destroy()
        except Exception:
            pass
