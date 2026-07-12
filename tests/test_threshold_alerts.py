"""Tests for low-quota threshold notifications (app._check_threshold_alerts).

Regression tests for the bug where pace-suppression silently ate near-limit
alerts: when usage stayed at or below the elapsed-time pace, threshold crossings
were suppressed AND marked as already-notified, so the user got no warning when
running low. Desired behavior: every upward threshold crossing notifies once,
regardless of pace.

Run standalone:  uv run python tests/test_threshold_alerts.py
Or with pytest:  uv run python -m pytest tests/test_threshold_alerts.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitor.app import App


def _new_app():
    app = App.__new__(App)  # skip __init__ (avoids building the pystray icon)
    app._notified_thresholds = {}
    app._prev_utilization = {}
    fired: list[str] = []
    app.icon = types.SimpleNamespace(notify=lambda msg, title=None: fired.append(msg))
    return app, fired


def _poll(app, pct: float, time_pct: float) -> None:
    """One poll of Claude five_hour at `pct` used, window `time_pct` elapsed."""
    pct_map = {'claude:five_hour': pct}
    app._check_reset_alerts(pct_map)
    app._check_threshold_alerts(pct_map)
    app._prev_utilization = pct_map  # mimic end of _update()


def test_under_pace_still_warns_near_limit():
    """The core bug: usage <= elapsed-time pace must NOT swallow the alert."""
    app, fired = _new_app()
    _poll(app, 70, 85)   # crosses 50% while under pace
    _poll(app, 96, 97)   # crosses 95% while under pace
    assert fired, 'expected at least one notification when hitting 96%, got none'
    assert any('96%' in m or '95' in m for m in fired), f'expected a near-limit alert, got {fired}'


def test_all_thresholds_fire_on_burst():
    app, fired = _new_app()
    _poll(app, 55, 10)
    _poll(app, 85, 15)
    _poll(app, 97, 20)
    assert len(fired) == 3, f'expected 3 alerts (50/80/95), got {len(fired)}: {fired}'


def test_no_duplicate_alert_for_same_threshold():
    app, fired = _new_app()
    _poll(app, 55, 30)
    _poll(app, 58, 35)   # still only past the 50 threshold
    assert len(fired) == 1, f'expected 1 alert, got {len(fired)}: {fired}'


def test_reset_rearms_thresholds():
    app, fired = _new_app()
    _poll(app, 96, 40)   # near limit -> alert(s)
    n_before = len(fired)
    assert n_before >= 1
    _poll(app, 3, 1)     # window reset: usage cleared, fresh window
    _poll(app, 55, 20)   # crosses 50% again -> must alert again
    assert len(fired) > n_before, 'threshold did not re-arm after reset'


def test_below_first_threshold_is_silent():
    app, fired = _new_app()
    _poll(app, 40, 90)
    assert fired == [], f'expected no alert below 50%, got {fired}'


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'PASS  {t.__name__}')
        except AssertionError as e:
            failed += 1
            print(f'FAIL  {t.__name__}: {e}')
    print(f'\n{len(tests) - failed}/{len(tests)} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(_run())
