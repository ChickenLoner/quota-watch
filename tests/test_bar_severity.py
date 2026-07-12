"""Tests for popup bar severity (_bar_entry).

Regression: severity used to be pace-based (usage vs elapsed-time), so 1% used
right after a window reset showed a WARNING. Severity now tracks actual usage:
crit >=90, warn >=50, else ok.

Run standalone:  uv run python tests/test_bar_severity.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitor.payload import _bar_entry
from monitor.providers.base import QuotaField


def _sev(pct: float) -> str:
    # resets_at deliberately near-future (window just reset) — the old pace logic
    # would flag this as 'warn'; the new usage-based logic must not.
    f = QuotaField('five_hour', 'SESSION - 5H', pct, '2099-01-01T00:00:00+00:00')
    return _bar_entry(f)['sev']


def test_one_percent_is_ok_not_warn():
    assert _sev(1) == 'ok', 'trivial usage must not show a warning'


def test_below_fifty_is_ok():
    assert _sev(0) == 'ok'
    assert _sev(49.9) == 'ok'


def test_fifty_to_ninety_is_warn():
    assert _sev(50) == 'warn'
    assert _sev(75) == 'warn'
    assert _sev(89.9) == 'warn'


def test_ninety_plus_is_crit():
    assert _sev(90) == 'crit'
    assert _sev(100) == 'crit'


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
