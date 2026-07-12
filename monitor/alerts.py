"""Quota alert logic — reset + threshold notifications, isolated from the App.

Owns the per-window alert state (previous utilization + which thresholds have
already fired) so it can be unit-tested without constructing the tray App.
Composite keys are `"{provider_id}:{field_key}"`, e.g. `"claude:five_hour"`.
"""
from __future__ import annotations

from typing import Callable

from .formatting import field_period

# Per-field upward-crossing thresholds for low-quota notifications. Falls back
# to the field's base period (e.g. 'seven_day_opus' → 'seven_day').
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


class AlertManager:
    """Fires notifications on threshold crossings and quota resets.

    `notify(message, title)` is the sink (the tray icon's notify in production).
    """

    def __init__(self, notify: Callable[[str, str], None]) -> None:
        self._notify = notify
        self._prev:     dict[str, float] = {}   # last utilization per composite key
        self._notified: dict[str, float] = {}   # highest threshold already alerted per key

    def previous(self, key: str) -> float | None:
        """Utilization from the prior poll — read before process() overwrites it."""
        return self._prev.get(key)

    def process(self, pct_map: dict[str, float]) -> None:
        """Run reset + threshold checks for this poll, then record it as the baseline."""
        self._check_reset_alerts(pct_map)
        self._check_threshold_alerts(pct_map)
        self._prev = pct_map

    def forget(self, prefix: str) -> None:
        """Drop all state for keys starting with `prefix` (e.g. 'claude:' on token change)."""
        self._prev     = {k: v for k, v in self._prev.items()     if not k.startswith(prefix)}
        self._notified = {k: v for k, v in self._notified.items() if not k.startswith(prefix)}

    def _check_reset_alerts(self, pct_map: dict[str, float]) -> None:
        """Notify when a nearly-exhausted quota resets (usage drops)."""
        for composite_key, pct in pct_map.items():
            prev = self._prev.get(composite_key)
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
                self._notify('Quota reset - usage cleared', 'QuotaWatch')
                self._notified[composite_key] = 0

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
            last_notified = self._notified.get(composite_key, 0)

            if highest > last_notified:
                pid   = composite_key.split(':', 1)[0] if ':' in composite_key else ''
                label = f'{pid.upper()}: {field_key.replace("_", " ").upper()}' if pid else field_key.upper()
                self._notify(f'{label}: {pct:.0f}% used', 'QuotaWatch - Usage Alert')
                self._notified[composite_key] = highest

            elif highest < last_notified:
                self._notified[composite_key] = highest
