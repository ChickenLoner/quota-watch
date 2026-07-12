"""Tests for the unified severity module (bands drive color + notifications)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitor.severity import bands_for, crossings, sev_for


def test_default_band():
    assert bands_for('anything_unknown') == (50, 90)


def test_base_period_fallback():
    # seven_day_opus falls back to the seven_day band
    assert bands_for('seven_day_opus') == bands_for('seven_day')


def test_sev_thresholds():
    assert sev_for('five_hour', 0) == 'ok'
    assert sev_for('five_hour', 49.9) == 'ok'
    assert sev_for('five_hour', 50) == 'warn'
    assert sev_for('five_hour', 89.9) == 'warn'
    assert sev_for('five_hour', 90) == 'crit'
    assert sev_for('five_hour', 100) == 'crit'


def test_crossings_are_the_bands():
    # sev color boundaries and notification crossings come from the same numbers
    warn, crit = bands_for('five_hour')
    assert crossings('five_hour') == [warn, crit]


def test_crossings_deduped_when_warn_equals_crit(monkeypatch):
    from monitor import severity
    monkeypatch.setitem(severity._BANDS, 'crit_only', (90, 90))
    assert crossings('crit_only') == [90]


def test_color_and_notify_agree_at_crit():
    # a value that colors 'crit' must also be at/above the top notification crossing
    warn, crit = bands_for('seven_day')
    assert sev_for('seven_day', crit) == 'crit'
    assert crit == crossings('seven_day')[-1]
