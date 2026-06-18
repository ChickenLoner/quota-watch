"""Windsurf provider — reads local SQLite state.vscdb, no auth required."""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from .base import Provider, QuotaField, UsageSnapshot

_DB_KEY = 'windsurf.settings.cachedPlanInfo'


def _db_path() -> Path:
    if sys.platform == 'win32':
        base = Path.home() / 'AppData' / 'Roaming'
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(Path.home(), '.config')
    return base / 'Windsurf' / 'User' / 'globalStorage' / 'state.vscdb'


def _unix_to_iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _read_plan_info(db: Path) -> dict | None:
    try:
        con = sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=3)
        cur = con.execute('SELECT value FROM ItemTable WHERE key = ? LIMIT 1', (_DB_KEY,))
        row = cur.fetchone()
        con.close()
        if not row:
            return None
        return json.loads(row[0])
    except Exception:
        return None


class WindsurfProvider(Provider):
    provider_id   = 'windsurf'
    provider_name = 'Windsurf'

    def is_available(self) -> bool:
        return _db_path().is_file()

    def fetch(self) -> UsageSnapshot:
        db = _db_path()
        if not db.is_file():
            return UsageSnapshot(self.provider_id, self.provider_name, [],
                                 error='Windsurf not found - install and launch Windsurf first')

        plan = _read_plan_info(db)
        if plan is None:
            return UsageSnapshot(self.provider_id, self.provider_name, [],
                                 error='No plan data - sign in to Windsurf first')

        return self._parse(plan)

    def _parse(self, plan: dict) -> UsageSnapshot:
        fields: list[QuotaField] = []

        quota = plan.get('quotaUsage') or {}
        daily_rem  = quota.get('dailyRemainingPercent')
        weekly_rem = quota.get('weeklyRemainingPercent')
        daily_ts   = quota.get('dailyResetAtUnix')
        weekly_ts  = quota.get('weeklyResetAtUnix')

        if daily_rem is not None:
            fields.append(QuotaField(
                key='one_day',
                label='DAILY - 1D',
                utilization=max(0.0, min(100.0, 100.0 - float(daily_rem))),
                resets_at=_unix_to_iso(int(daily_ts)) if daily_ts else None,
            ))

        if weekly_rem is not None:
            fields.append(QuotaField(
                key='seven_day',
                label='WEEKLY - 7D',
                utilization=max(0.0, min(100.0, 100.0 - float(weekly_rem))),
                resets_at=_unix_to_iso(int(weekly_ts)) if weekly_ts else None,
            ))

        # Fallback: older message-count schema
        if not fields:
            usage = plan.get('usage') or {}
            total = usage.get('messages') or usage.get('flowActions')
            used  = usage.get('usedMessages') or usage.get('usedFlowActions')
            if total and used is not None and total > 0:
                fields.append(QuotaField(
                    key='windsurf_session',
                    label='MESSAGES',
                    utilization=max(0.0, min(100.0, used / total * 100)),
                    resets_at=None,
                ))

        extras: dict = {}
        if plan.get('planName'):
            extras['plan_name'] = plan['planName']

        return UsageSnapshot(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            fields=fields,
            extras=extras,
        )
