"""Main application - pystray tray icon, adaptive polling, alerts, autostart, restart."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pystray  # type: ignore[import-untyped]

from .providers.base import UsageSnapshot
from .providers.claude import ClaudeProvider, read_token
from .providers.codex import CodexProvider
from .providers.windsurf import WindsurfProvider
from .autostart import is_enabled as autostart_is_enabled, set_enabled as autostart_set, sync_path as autostart_sync
from .formatting import countdown_short, elapsed_pct, field_period
from .tray import create_icon, create_status_icon, taskbar_is_light, watch_theme

POLL_INTERVAL = 180
POLL_FAST     = 30
POLL_ERROR    = 30

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
        self._providers           = [self._claude, CodexProvider(), WindsurfProvider()]
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
        self._running          = True
        self.restart_requested = False

        self._light_taskbar = taskbar_is_light()

        frozen = getattr(sys, 'frozen', False)

        self.icon = pystray.Icon(
            'quota_watch',
            icon=create_icon(0, 0),
            title='QuotaWatch',
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
            new_snapshots: dict[str, UsageSnapshot] = {}
            for provider in self._providers:
                if provider.is_available():
                    new_snapshots[provider.provider_id] = provider.fetch()
        finally:
            self._lock.release()

        # Separate successes from failures
        ok      = {pid: s for pid, s in new_snapshots.items() if not s.error}
        failed  = {pid: s for pid, s in new_snapshots.items() if s.error}

        if not ok and failed:
            errors = ', '.join(f'{pid}: {s.error}' for pid, s in failed.items())
            self._last_error = errors
            self._render_tray(error=True)
            return

        with self._lock:
            self._snapshots.update(new_snapshots)
            self._last_success_time = time.time()
            # Clear overall error if at least one provider succeeded
            self._last_error = None

        # Build composite pct_map: "{provider_id}:{field_key}" -> utilization
        pct_map: dict[str, float] = {}
        for pid, snap in ok.items():
            for f in snap.fields:
                pct_map[f'{pid}:{f.key}'] = f.utilization

        self._check_reset_alerts(pct_map)
        self._check_threshold_alerts(ok, pct_map)

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

    def _check_threshold_alerts(
        self,
        ok: dict[str, UsageSnapshot],
        pct_map: dict[str, float],
    ) -> None:
        """Notify when usage crosses a configured threshold."""
        field_lookup: dict[str, Any] = {}
        for pid, snap in ok.items():
            for f in snap.fields:
                field_lookup[f'{pid}:{f.key}'] = f

        for composite_key, pct in pct_map.items():
            field_key = composite_key.split(':', 1)[1] if ':' in composite_key else composite_key
            thresholds = _thresholds_for(field_key)
            if not thresholds:
                continue

            exceeded      = [t for t in thresholds if pct >= t]
            highest       = max(exceeded) if exceeded else 0
            last_notified = self._notified_thresholds.get(composite_key, 0)

            if highest > last_notified:
                f      = field_lookup.get(composite_key)
                period = field_period(field_key)
                if period and f:
                    time_pct = elapsed_pct(f.resets_at or '', period)
                    if time_pct is not None and pct <= time_pct:
                        self._notified_thresholds[composite_key] = highest
                        continue

                pid   = composite_key.split(':', 1)[0] if ':' in composite_key else ''
                label = f'{pid.upper()}: {field_key.replace("_", " ").upper()}' if pid else field_key.upper()
                self.icon.notify(f'{label}: {pct:.0f}% used', 'QuotaWatch - Usage Alert')
                self._notified_thresholds[composite_key] = highest

            elif highest < last_notified:
                self._notified_thresholds[composite_key] = highest

    # ── Rendering ────────────────────────────────────────────────────────────

    def _render_tray(self, error: bool) -> None:
        if error:
            self.icon.icon  = create_status_icon('!')
            self.icon.title = f'QuotaWatch - {self._last_error}'
            return

        # Collect all fields sorted by utilization desc
        all_fields = [
            (snap.provider_name, f)
            for snap in self._snapshots.values()
            if not snap.error
            for f in snap.fields
        ]
        all_fields.sort(key=lambda x: x[1].utilization, reverse=True)

        top       = all_fields[0][1].utilization if len(all_fields) > 0 else 0
        bot       = all_fields[1][1].utilization if len(all_fields) > 1 else 0
        countdown = countdown_short(all_fields[0][1].resets_at or '') if all_fields else ''

        self.icon.icon  = create_icon(top, bot, countdown=countdown)
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
        profile = self._claude.fetch_profile()
        with self._lock:
            self._profile       = profile
            self._profile_token = current_token
