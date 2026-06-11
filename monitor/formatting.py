"""Formatting helpers - ported from usage-monitor-for-claude."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

_NUMBER_WORDS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
}
_UNIT_SUFFIXES = {'hour': 'h', 'day': 'd'}


def field_period(field: str) -> int | None:
    """Return period in seconds for a field key, or None."""
    parts = field.split('_', 2)
    if len(parts) < 2:
        return None
    number = _NUMBER_WORDS.get(parts[0])
    unit = parts[1]
    if number is None or unit not in _UNIT_SUFFIXES:
        return None
    if unit == 'hour':
        return number * 3600
    if unit == 'day':
        return number * 24 * 3600
    return None


def elapsed_pct(resets_at: str, period_seconds: int) -> float | None:
    """Return elapsed % of a period (0-100), or None."""
    if not resets_at or period_seconds <= 0:
        return None
    try:
        reset = datetime.fromisoformat(resets_at)
        now = datetime.now(timezone.utc)
        remaining = (reset - now).total_seconds()
        elapsed = period_seconds - remaining
        return max(0.0, min(100.0, elapsed / period_seconds * 100))
    except Exception:
        return None


def midnight_positions(resets_at: str, period_seconds: int) -> list[float]:
    """Return relative positions (0-1) of local midnight boundaries in a period."""
    if not resets_at or period_seconds <= 0:
        return []
    try:
        reset_utc = datetime.fromisoformat(resets_at)
        start_utc = reset_utc - timedelta(seconds=period_seconds)
        start_local = start_utc.astimezone()
        end_local = reset_utc.astimezone()
        midnight = (start_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        positions = []
        while midnight < end_local:
            rel = (midnight - start_local).total_seconds() / period_seconds
            if rel > 0.003:
                positions.append(rel)
            midnight += timedelta(days=1)
        return positions
    except Exception:
        return []


def countdown_short(resets_at: str) -> str:
    """Return compact countdown for tray icon: '3d14h', '4h22', '45m', or ''."""
    if not resets_at:
        return ''
    try:
        reset = datetime.fromisoformat(resets_at)
        remaining = (reset - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            return ''
        total_min = int(remaining / 60)
        d, rem_min = divmod(total_min, 24 * 60)
        h, m = divmod(rem_min, 60)
        if d > 0:
            return f'{d}d{h:02d}h'
        if h > 0:
            return f'{h}h{m:02d}'
        return f'{m}m'
    except Exception:
        return ''


def time_until(iso_str: str) -> str:
    """Return human-readable time until a reset timestamp."""
    try:
        reset = datetime.fromisoformat(iso_str)
        now = datetime.now(timezone.utc)
        diff = reset - now
        total_min = max(0, int(diff.total_seconds() / 60))
        if total_min == 0:
            return ''

        reset_local = reset.astimezone()
        if reset_local.second >= 30:
            reset_local = reset_local.replace(second=0) + timedelta(minutes=1)
        else:
            reset_local = reset_local.replace(second=0)

        time_str  = reset_local.strftime('%H:%M')
        days_left, rem_min = divmod(total_min, 24 * 60)
        h, m = divmod(rem_min, 60)

        if days_left == 0:
            duration = f'{h}H {m}M' if h else f'{m}M'
            return f'RESETS IN {duration} ({time_str})'

        day_name = reset_local.strftime('%a').upper()
        return f'RESETS IN {days_left}D {h}H {m:02d}M ({day_name} {time_str})'
    except Exception:
        return ''
