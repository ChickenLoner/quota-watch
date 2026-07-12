"""Main application - pystray tray icon, adaptive polling, alerts, autostart, restart."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_MOD_CONTROL     = 0x0002
_MOD_SHIFT       = 0x0004
_WM_HOTKEY       = 0x0312
_HOTKEY_SHOW     = 1
_HOTKEY_RESTART  = 2
_HOTKEY_QUIT     = 3

import pystray  # type: ignore[import-untyped]

from .providers.base import UsageSnapshot
from .providers.antigravity import AntigravityProvider
from .providers.claude import ClaudeProvider, read_token
from .providers.codex import CodexProvider
from .providers.windsurf import WindsurfProvider
from .autostart import is_enabled as autostart_is_enabled, set_enabled as autostart_set, sync_path as autostart_sync
from .formatting import countdown_short, field_period
from .tray import app_icon, taskbar_is_light, watch_theme

POLL_INTERVAL      = 180
POLL_FAST          = 30
_POLL_ERROR_STEPS  = [30, 60, 120, 240, 600]  # backoff ramp on repeated errors

_STATUS_CACHE = Path.home() / '.claude' / 'cache' / 'soc-monitor-status.json'

_THRESHOLDS: dict[str, list[float]] = {
    'five_hour': [50, 80, 95],
    'seven_day': [95],
}


def _thresholds_for(key: str) -> list[float]:
    if key in _THRESHOLDS:
        return _THRESHOLDS[key]
    parts = key.split('_', 2)
    if len(parts) >= 2:
        base = f'{parts[0]}_{parts[1]}'
        if base in _THRESHOLDS:
            return _THRESHOLDS[base]
    return []


def _at_limit_skip(snap: 'UsageSnapshot') -> bool:
    """True when primary field is at 100% and reset hasn't passed yet (+5 min grace)."""
    if not snap.fields:
        return False
    f = snap.fields[0]
    if f.utilization < 100 or not f.resets_at:
        return False
    try:
        reset = datetime.fromisoformat(f.resets_at.replace('Z', '+00:00'))
        return datetime.now(timezone.utc) < reset + timedelta(minutes=5)
    except Exception:
        return False


@dataclass
class CacheSnapshot:
    snapshots: dict[str, UsageSnapshot]   # keyed by provider_id
    profile: dict[str, Any] | None
    last_success_time: float | None
    last_error: str | None


class App:
    """Tray application with adaptive polling, threshold alerts, and restart support."""

    def __init__(self) -> None:
        self._claude              = ClaudeProvider()
        self._providers           = [self._claude, CodexProvider(), WindsurfProvider(), AntigravityProvider()]
        self._snapshots:          dict[str, UsageSnapshot] = {}
        self._profile:            dict[str, Any] | None = None
        self._last_success_time:  float | None = None
        self._last_error:         str | None = None
        self._profile_token:      str | None = None

        self._lock             = threading.Lock()
        self._popup_lock       = threading.Lock()
        self._popup_open       = False
        self._popup_closed_at  = 0.0
        self.next_poll_time:   float | None = None

        # Alert state — keyed by "{provider_id}:{field_key}"
        self._prev_utilization:    dict[str, float] = {}
        self._notified_thresholds: dict[str, float] = {}
        self._first_update_done    = False

        self._fast_polls       = 0
        self._error_count      = 0
        self._running          = True
        self.restart_requested = False
        self._force_poll       = threading.Event()

        self._light_taskbar = taskbar_is_light()

        frozen = getattr(sys, 'frozen', False)

        self.icon = pystray.Icon(
            'quota_watch',
            icon=app_icon(),
            title='QuotaWatch',
            menu=pystray.Menu(
                pystray.MenuItem('&Show Status\tCtrl+Shift+Q', self._on_show, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    'Start with &Windows', self._on_toggle_autostart,
                    checked=lambda item: autostart_is_enabled(),
                    visible=frozen,
                ),
                pystray.MenuItem('&Restart\tCtrl+Shift+R', self._on_restart),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('&Quit\tCtrl+Shift+X', self._on_quit),
            ),
        )

    # ── Public ──────────────────────────────────────────────────────────────

    def run(self) -> None:
        self.icon.run(setup=self._on_ready)

    def cache_snapshot(self) -> CacheSnapshot:
        with self._lock:
            return CacheSnapshot(
                snapshots=dict(self._snapshots),
                profile=self._profile,
                last_success_time=self._last_success_time,
                last_error=self._last_error,
            )

    # ── Setup ────────────────────────────────────────────────────────────────

    def _on_ready(self, icon: Any) -> None:
        icon.visible = True
        if getattr(sys, 'frozen', False):
            autostart_sync()
        if not self._claude.is_available():
            icon.notify('Claude: no token - run: claude auth login', 'QuotaWatch')
        watch_theme(self._on_theme_changed)
        threading.Thread(target=self._hotkey_loop, daemon=True).start()
        from .popup import prewarm_installs
        threading.Thread(target=prewarm_installs, daemon=True).start()
        self._ensure_profile()
        self._poll_loop()

    # ── Menu actions ─────────────────────────────────────────────────────────

    def _on_toggle_autostart(self, icon: Any = None, item: Any = None) -> None:
        autostart_set(not autostart_is_enabled())

    def _on_restart(self, icon: Any = None, item: Any = None) -> None:
        self.restart_requested = True
        self._on_quit()

    def _on_quit(self, icon: Any = None, item: Any = None) -> None:
        self._running = False
        self._force_poll.set()
        self.icon.stop()

    # ── Polling ──────────────────────────────────────────────────────────────

    def _earliest_reset_within(self, interval: float) -> float | None:
        """Return the earliest resets_at timestamp within the next interval, or None."""
        now = time.time()
        cutoff = now + interval + 5  # include resets up to 5s past the interval end
        earliest: float | None = None
        with self._lock:
            for snap in self._snapshots.values():
                for f in snap.fields:
                    if not f.resets_at:
                        continue
                    try:
                        ts = datetime.fromisoformat(
                            f.resets_at.replace('Z', '+00:00')
                        ).timestamp()
                        if now < ts < cutoff:
                            if earliest is None or ts < earliest:
                                earliest = ts
                    except Exception:
                        pass
        return earliest

    def _poll_loop(self) -> None:
        while self._running:
            self._update()
            if self._last_error:
                step = min(self._error_count - 1, len(_POLL_ERROR_STEPS) - 1)
                interval = _POLL_ERROR_STEPS[max(0, step)]
            elif self._fast_polls > 0:
                interval = POLL_FAST
            else:
                interval = POLL_INTERVAL

            deadline = time.time() + interval
            # Wake up 5s after any quota reset that falls within this interval
            reset_ts = self._earliest_reset_within(interval)
            if reset_ts is not None:
                deadline = min(deadline, reset_ts + 5)
            self.next_poll_time = deadline
            self._force_poll.wait(timeout=max(1.0, deadline - time.time()))
            self._force_poll.clear()

    def _update(self) -> None:
        if not self._lock.acquire(blocking=False):
            return
        try:
            new_snapshots: dict[str, UsageSnapshot] = {}
            skipped: dict[str, UsageSnapshot] = {}  # at-limit providers; use cached data
            for provider in self._providers:
                if not provider.is_available():
                    continue
                existing = self._snapshots.get(provider.provider_id)
                if existing and not existing.error and _at_limit_skip(existing):
                    skipped[provider.provider_id] = existing
                else:
                    new_snapshots[provider.provider_id] = provider.fetch()
        finally:
            self._lock.release()

        # Separate successes from failures; merge skipped into ok
        ok      = {pid: s for pid, s in new_snapshots.items() if not s.error}
        ok.update(skipped)
        failed  = {pid: s for pid, s in new_snapshots.items() if s.error}

        if not ok and failed:
            errors = ', '.join(f'{pid}: {s.error}' for pid, s in failed.items())
            self._last_error  = errors
            self._error_count += 1
            self._render_tray(error=True)
            return

        with self._lock:
            self._snapshots.update(new_snapshots)
            self._last_success_time = time.time()
            self._last_error  = None
            self._error_count = 0

        # Build composite pct_map: "{provider_id}:{field_key}" -> utilization
        pct_map: dict[str, float] = {}
        for pid, snap in ok.items():
            for f in snap.fields:
                pct_map[f'{pid}:{f.key}'] = f.utilization

        self._check_reset_alerts(pct_map)
        self._check_threshold_alerts(pct_map)

        # Adaptive fast-poll: trigger when Claude's session field is rising
        claude_snap  = ok.get('claude')
        primary_key  = 'claude:five_hour'
        primary_pct  = pct_map.get(primary_key, 0)
        primary_prev = self._prev_utilization.get(primary_key)
        if primary_prev is not None and primary_pct > primary_prev:
            self._fast_polls = 3
        elif self._fast_polls > 0:
            self._fast_polls -= 1

        self._prev_utilization  = pct_map
        self._first_update_done = True
        self._render_tray(error=False)
        self._write_status_cache(ok)

    # ── Alerts ───────────────────────────────────────────────────────────────

    def _check_reset_alerts(self, pct_map: dict[str, float]) -> None:
        """Notify when a nearly-exhausted quota resets (usage drops)."""
        for composite_key, pct in pct_map.items():
            prev = self._prev_utilization.get(composite_key)
            if prev is None:
                continue

            any_blocking = any(
                other_pct >= 99
                for other_key, other_pct in pct_map.items()
                if other_key != composite_key
            )

            field_key = composite_key.split(':', 1)[1] if ':' in composite_key else composite_key
            period    = field_period(field_key)
            reset_threshold = 95 if (period and period <= 5 * 3600) else 98
            if prev > reset_threshold and pct < prev and not any_blocking:
                self.icon.notify('Quota reset - usage cleared', 'QuotaWatch')
                self._notified_thresholds[composite_key] = 0

    def _check_threshold_alerts(self, pct_map: dict[str, float]) -> None:
        """Notify once each time usage crosses a configured threshold upward.

        No pace weighting: a crossing always alerts. Being "on pace" doesn't
        change that you're running low, which is exactly when the warning matters.
        """
        for composite_key, pct in pct_map.items():
            field_key = composite_key.split(':', 1)[1] if ':' in composite_key else composite_key
            thresholds = _thresholds_for(field_key)
            if not thresholds:
                continue

            exceeded      = [t for t in thresholds if pct >= t]
            highest       = max(exceeded) if exceeded else 0
            last_notified = self._notified_thresholds.get(composite_key, 0)

            if highest > last_notified:
                pid   = composite_key.split(':', 1)[0] if ':' in composite_key else ''
                label = f'{pid.upper()}: {field_key.replace("_", " ").upper()}' if pid else field_key.upper()
                self.icon.notify(f'{label}: {pct:.0f}% used', 'QuotaWatch - Usage Alert')
                self._notified_thresholds[composite_key] = highest

            elif highest < last_notified:
                self._notified_thresholds[composite_key] = highest

    # ── Rendering ────────────────────────────────────────────────────────────

    def _render_tray(self, error: bool) -> None:
        if error:
            self.icon.title = f'QuotaWatch - {self._last_error}'
            return
        self.icon.title = self._build_tooltip()

    def _build_tooltip(self) -> str:
        lines = []
        for snap in self._snapshots.values():
            if snap.error or not snap.fields:
                continue
            f   = snap.fields[0]
            cd  = countdown_short(f.resets_at or '')
            suf = f'  -{cd}' if cd else ''
            lines.append(f'{snap.provider_name}: {f.label} {f.utilization:.0f}%{suf}')
        return '\n'.join(lines) if lines else 'QuotaWatch'

    def _write_status_cache(self, ok: dict[str, UsageSnapshot]) -> None:
        """Write quota snapshot to ~/.claude/cache/ for statusline consumers."""
        payload = {
            'updated': int(time.time()),
            'providers': {
                pid: {
                    'fields': [
                        {
                            'key':       f.key,
                            'pct':       round(f.utilization),
                            'resets_at': f.resets_at or '',
                            'countdown': countdown_short(f.resets_at or ''),
                        }
                        for f in snap.fields
                    ],
                }
                for pid, snap in ok.items()
            },
            # Keep legacy 'fields' key for existing statusline scripts (Claude primary only)
            'fields': [
                {
                    'key':       f.key,
                    'pct':       round(f.utilization),
                    'resets_at': f.resets_at or '',
                    'countdown': countdown_short(f.resets_at or ''),
                }
                for f in (ok.get('claude', UsageSnapshot('', '', [])).fields)
            ],
        }
        try:
            _STATUS_CACHE.parent.mkdir(parents=True, exist_ok=True)
            _STATUS_CACHE.write_text(json.dumps(payload), encoding='utf-8')
        except OSError:
            pass

    def _on_theme_changed(self) -> None:
        light = taskbar_is_light()
        if light != self._light_taskbar:
            self._light_taskbar = light
            self._render_tray(error=bool(self._last_error))

    # ── Global hotkeys (Ctrl+Shift+Q/R/X) ────────────────────────────────────

    def _hotkey_loop(self) -> None:
        user32   = ctypes.windll.user32
        handlers = {
            _HOTKEY_SHOW:    self._on_show,
            _HOTKEY_RESTART: self._on_restart,
            _HOTKEY_QUIT:    self._on_quit,
        }
        for hk_id, vk in ((_HOTKEY_SHOW, 'Q'), (_HOTKEY_RESTART, 'R'), (_HOTKEY_QUIT, 'X')):
            user32.RegisterHotKey(None, hk_id, _MOD_CONTROL | _MOD_SHIFT, ord(vk))

        msg = ctypes.wintypes.MSG()
        while self._running:
            r = user32.PeekMessageW(ctypes.byref(msg), None, _WM_HOTKEY, _WM_HOTKEY, 1)
            if r and msg.message == _WM_HOTKEY and msg.wParam in handlers:
                handlers[msg.wParam]()
            time.sleep(0.05)

        for hk_id in handlers:
            user32.UnregisterHotKey(None, hk_id)

    # ── Popup ─────────────────────────────────────────────────────────────────

    def _on_show(self, icon: Any = None, item: Any = None) -> None:
        with self._popup_lock:
            if self._popup_open:
                return
            if time.time() - self._popup_closed_at < 0.15:
                return
            self._popup_open = True
        threading.Thread(target=self._open_popup, daemon=True).start()

    def _open_popup(self) -> None:
        try:
            threading.Thread(target=self._ensure_profile, daemon=True).start()
            from .popup import UsagePopup
            UsagePopup(self)
        except Exception:
            traceback.print_exc()
        finally:
            self._popup_closed_at = time.time()
            self._popup_open      = False

    # ── Profile ───────────────────────────────────────────────────────────────

    def _ensure_profile(self) -> None:
        current_token = read_token()
        if self._profile is not None and self._profile_token == current_token:
            return
        token_changed = self._profile_token is not None and self._profile_token != current_token
        profile = self._claude.fetch_profile()
        with self._lock:
            self._profile       = profile
            self._profile_token = current_token
            if token_changed:
                self._snapshots.pop('claude', None)
                self._prev_utilization = {
                    k: v for k, v in self._prev_utilization.items()
                    if not k.startswith('claude:')
                }
                self._notified_thresholds = {
                    k: v for k, v in self._notified_thresholds.items()
                    if not k.startswith('claude:')
                }
        if token_changed:
            self._force_poll.set()
