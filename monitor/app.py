"""Main application - pystray tray icon, adaptive polling, alerts, autostart, restart."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pystray  # type: ignore[import-untyped]

from .api import fetch_profile, fetch_usage, quota_fields, read_token
from .autostart import is_enabled as autostart_is_enabled, set_enabled as autostart_set, sync_path as autostart_sync
from .formatting import countdown_short, elapsed_pct, field_period
from .tray import create_icon, create_status_icon, taskbar_is_light, watch_theme

POLL_INTERVAL = 180
POLL_FAST     = 30
POLL_ERROR    = 30

_STATUS_CACHE = Path.home() / '.claude' / 'cache' / 'soc-monitor-status.json'

# Default alert thresholds per field key (prefix match for variants)
_THRESHOLDS: dict[str, list[float]] = {
    'five_hour': [50, 80, 95],
    'seven_day': [95],
}


def _thresholds_for(key: str) -> list[float]:
    if key in _THRESHOLDS:
        return _THRESHOLDS[key]
    # Match base period (e.g. 'seven_day_sonnet' -> 'seven_day')
    parts = key.split('_', 2)
    if len(parts) >= 2:
        base = f'{parts[0]}_{parts[1]}'
        if base in _THRESHOLDS:
            return _THRESHOLDS[base]
    return []


@dataclass
class CacheSnapshot:
    usage: dict[str, Any]
    profile: dict[str, Any] | None
    last_success_time: float | None
    last_error: str | None


class App:
    """Tray application with adaptive polling, threshold alerts, and restart support."""

    def __init__(self) -> None:
        self._usage:              dict[str, Any] = {}
        self._profile:            dict[str, Any] | None = None
        self._last_success_time:  float | None = None
        self._last_error:         str | None = None
        self._profile_token:      str | None = None

        self._lock             = threading.Lock()
        self._popup_lock       = threading.Lock()
        self._popup_open       = False
        self._popup_closed_at  = 0.0
        self.next_poll_time:   float | None = None

        # Alert state
        self._prev_utilization:   dict[str, float] = {}
        self._notified_thresholds: dict[str, float] = {}
        self._first_update_done   = False

        # Adaptive polling
        self._fast_polls  = 0
        self._running     = True
        self.restart_requested = False

        self._light_taskbar = taskbar_is_light()

        frozen = getattr(sys, 'frozen', False)

        self.icon = pystray.Icon(
            'soc_monitor',
            icon=create_icon(0, 0),
            title='Claude Monitor',
            menu=pystray.Menu(
                pystray.MenuItem('Show Status', self._on_show, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    'Start with Windows', self._on_toggle_autostart,
                    checked=lambda item: autostart_is_enabled(),
                    visible=frozen,
                ),
                pystray.MenuItem('Restart', self._on_restart),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Quit', self._on_quit),
            ),
        )

    # ── Public ──────────────────────────────────────────────────────────────

    def run(self) -> None:
        self.icon.run(setup=self._on_ready)

    def cache_snapshot(self) -> CacheSnapshot:
        with self._lock:
            return CacheSnapshot(
                usage=dict(self._usage),
                profile=self._profile,
                last_success_time=self._last_success_time,
                last_error=self._last_error,
            )

    # ── Setup ────────────────────────────────────────────────────────────────

    def _on_ready(self, icon: Any) -> None:
        icon.visible = True
        if getattr(sys, 'frozen', False):
            autostart_sync()
        if not read_token():
            icon.notify('No token - run: claude auth login', 'Claude Monitor')
        watch_theme(self._on_theme_changed)
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
        self.icon.stop()

    # ── Polling ──────────────────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        while self._running:
            self._update()
            interval = POLL_FAST if self._fast_polls > 0 else POLL_INTERVAL
            if self._last_error:
                interval = POLL_ERROR

            deadline = time.time() + interval
            self.next_poll_time = deadline
            while self._running and time.time() < deadline:
                time.sleep(1)

    def _update(self) -> None:
        if not self._lock.acquire(blocking=False):
            return
        try:
            data = fetch_usage()
        finally:
            self._lock.release()

        if 'error' in data:
            self._last_error = data['error']
            self._render_tray(error=True)
            return

        with self._lock:
            self._last_error        = None
            self._last_success_time = time.time()
            self._usage             = data

        fields  = quota_fields(data)
        pct_map = {k: v.get('utilization', 0) or 0 for k, v in fields}

        self._check_reset_alerts(pct_map)
        self._check_threshold_alerts(data, pct_map)

        # Adaptive fast-poll when primary field is rising
        primary_pct  = pct_map.get('five_hour', 0)
        primary_prev = self._prev_utilization.get('five_hour')
        if primary_prev is not None and primary_pct > primary_prev:
            self._fast_polls = 3
        elif self._fast_polls > 0:
            self._fast_polls -= 1

        self._prev_utilization  = pct_map
        self._first_update_done = True
        self._render_tray(error=False)
        self._write_status_cache(fields)

    # ── Alerts ───────────────────────────────────────────────────────────────

    def _check_reset_alerts(self, pct_map: dict[str, float]) -> None:
        """Notify when a nearly-exhausted quota resets (usage drops)."""
        for key, pct in pct_map.items():
            prev = self._prev_utilization.get(key)
            if prev is None:
                continue

            # Any other quota at >=99% blocks the "reset" interpretation
            any_blocking = any(
                other_pct >= 99
                for other_key, other_pct in pct_map.items()
                if other_key != key
            )

            period = field_period(key)
            reset_threshold = 95 if (period and period <= 5 * 3600) else 98
            if prev > reset_threshold and pct < prev and not any_blocking:
                self.icon.notify('Quota reset - usage cleared', 'Claude Monitor')
                self._notified_thresholds[key] = 0

    def _check_threshold_alerts(self, data: dict[str, Any], pct_map: dict[str, float]) -> None:
        """Notify when usage crosses a configured threshold."""
        for key, pct in pct_map.items():
            thresholds = _thresholds_for(key)
            if not thresholds:
                continue

            exceeded       = [t for t in thresholds if pct >= t]
            highest        = max(exceeded) if exceeded else 0
            last_notified  = self._notified_thresholds.get(key, 0)

            if highest > last_notified:
                # Time-aware: skip alert if usage is behind elapsed time
                entry  = data.get(key) or {}
                period = field_period(key)
                if period:
                    time_pct = elapsed_pct(entry.get('resets_at', ''), period)
                    if time_pct is not None and pct <= time_pct:
                        self._notified_thresholds[key] = highest
                        continue

                label = key.replace('_', ' ').upper()
                self.icon.notify(
                    f'{label}: {pct:.0f}% used',
                    'Claude Monitor - Usage Alert',
                )
                self._notified_thresholds[key] = highest

            elif highest < last_notified:
                # Usage dropped below last threshold (reset) - allow re-alerting
                self._notified_thresholds[key] = highest

    # ── Rendering ────────────────────────────────────────────────────────────

    def _render_tray(self, error: bool) -> None:
        if error:
            self.icon.icon  = create_status_icon('!')
            self.icon.title = f'Claude Monitor - {self._last_error}'
            return

        fields    = quota_fields(self._usage)
        pcts      = [v.get('utilization', 0) or 0 for _, v in fields]
        top       = pcts[0] if len(pcts) > 0 else 0
        bot       = pcts[1] if len(pcts) > 1 else 0
        countdown = countdown_short(fields[0][1].get('resets_at', '')) if fields else ''

        self.icon.icon  = create_icon(top, bot, countdown=countdown)
        self.icon.title = self._build_tooltip(fields)

    def _build_tooltip(self, fields: list) -> str:
        if not fields:
            return 'Claude Monitor'
        from .api import field_label
        parts = []
        for k, v in fields[:3]:
            pct    = v.get('utilization', 0) or 0
            cd     = countdown_short(v.get('resets_at', ''))
            suffix = f'  -{cd}' if cd else ''
            parts.append(f'{field_label(k)}: {pct:.0f}%{suffix}')
        return '\n'.join(parts)

    def _write_status_cache(self, fields: list) -> None:
        """Write quota snapshot to ~/.claude/cache/ for statusline consumers."""
        payload = {
            'updated': int(time.time()),
            'fields': [
                {
                    'key':       k,
                    'pct':       round(v.get('utilization', 0) or 0),
                    'resets_at': v.get('resets_at', '') or '',
                    'countdown': countdown_short(v.get('resets_at', '') or ''),
                }
                for k, v in fields
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
            self._ensure_profile()
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
        profile = fetch_profile()
        with self._lock:
            self._profile       = profile
            self._profile_token = current_token
