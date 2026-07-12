"""Single source of truth for quota severity.

Per-field (warn, crit) bands drive BOTH the popup bar color (payload._bar_entry)
and the notification crossings (alerts.AlertManager). Because both read the same
bands, a red bar always means the crit alert has fired — the two can never
disagree the way they did when each hardcoded its own thresholds.

Tune a field by adding it to `_BANDS`; anything unlisted uses `_DEFAULT` (with a
base-period fallback, e.g. 'seven_day_opus' → 'seven_day').
"""
from __future__ import annotations

_BANDS: dict[str, tuple[float, float]] = {
    'five_hour': (50, 90),
    'seven_day': (50, 90),
}
_DEFAULT: tuple[float, float] = (50, 90)


def bands_for(key: str) -> tuple[float, float]:
    """(warn, crit) for a field key, falling back to its base period then the default."""
    if key in _BANDS:
        return _BANDS[key]
    parts = key.split('_', 2)
    if len(parts) >= 2:
        base = f'{parts[0]}_{parts[1]}'
        if base in _BANDS:
            return _BANDS[base]
    return _DEFAULT


def sev_for(key: str, pct: float) -> str:
    """'ok' | 'warn' | 'crit' for a field's raw utilization."""
    warn, crit = bands_for(key)
    if pct >= crit:
        return 'crit'
    if pct >= warn:
        return 'warn'
    return 'ok'


def crossings(key: str) -> list[float]:
    """Ascending notification thresholds — the same warn/crit bands, deduped."""
    warn, crit = bands_for(key)
    return sorted({warn, crit})
