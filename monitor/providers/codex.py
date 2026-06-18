"""Codex (OpenAI subscription) provider — reads ~/.codex/auth.json, hits chatgpt.com usage API."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .base import Provider, QuotaField, UsageSnapshot

_CODEX_HOME = (
    Path(os.environ['CODEX_HOME'])
    if os.environ.get('CODEX_HOME')
    else Path.home() / '.codex'
)
_AUTH_FILE = _CODEX_HOME / 'auth.json'

_USAGE_URL = 'https://chatgpt.com/backend-api/wham/usage'

# Map limit_window_seconds → (field_key, display_label)
# Keys match field_period() naming so elapsed/alert logic works automatically.
_WINDOW_MAP: dict[int, tuple[str, str]] = {
    3600:    ('one_hour',    'SESSION - 1H'),
    10800:   ('three_hour',  'SESSION - 3H'),
    18000:   ('five_hour',   'SESSION - 5H'),
    86400:   ('one_day',     'DAILY - 1D'),
    604800:  ('seven_day',   'WEEKLY - 7D'),
    2592000: ('thirty_day',  'MONTHLY - 30D'),
}


def _seconds_to_field(seconds: int, fallback: str) -> tuple[str, str]:
    if seconds in _WINDOW_MAP:
        return _WINDOW_MAP[seconds]
    if seconds < 86400:
        h = max(1, seconds // 3600)
        return (fallback, f'SESSION - {h}H')
    d = max(1, seconds // 86400)
    return (fallback, f'PERIOD - {d}D')


def _unix_to_iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _read_credentials() -> dict[str, Any] | None:
    try:
        return json.loads(_AUTH_FILE.read_text(encoding='utf-8'))
    except Exception:
        return None


def _extract_token(creds: dict[str, Any]) -> str | None:
    # Direct API key takes precedence (covers non-OAuth users)
    api_key = (creds.get('OPENAI_API_KEY') or '').strip()
    if api_key:
        return api_key
    tokens = creds.get('tokens') or {}
    return (tokens.get('access_token') or tokens.get('accessToken') or '').strip() or None


def _extract_account_id(creds: dict[str, Any]) -> str | None:
    tokens = creds.get('tokens') or {}
    return (tokens.get('account_id') or tokens.get('accountId') or '').strip() or None


class CodexProvider(Provider):
    provider_id   = 'codex'
    provider_name = 'Codex'

    def is_available(self) -> bool:
        creds = _read_credentials()
        if not creds:
            return False
        return bool(_extract_token(creds))

    def fetch(self) -> UsageSnapshot:
        creds = _read_credentials()
        if not creds:
            return UsageSnapshot(self.provider_id, self.provider_name, [],
                                 error='NO AUTH - run: codex (to log in)', auth_error=True)

        token = _extract_token(creds)
        if not token:
            return UsageSnapshot(self.provider_id, self.provider_name, [],
                                 error='NO TOKEN in ~/.codex/auth.json', auth_error=True)

        account_id = _extract_account_id(creds)
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
            'User-Agent': 'ai-monitor',
        }
        if account_id:
            headers['ChatGPT-Account-Id'] = account_id

        try:
            r = requests.get(_USAGE_URL, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            if code in (401, 403):
                return UsageSnapshot(self.provider_id, self.provider_name, [],
                                     error='TOKEN EXPIRED - run: codex (to re-login)', auth_error=True)
            if 500 <= code < 600:
                return UsageSnapshot(self.provider_id, self.provider_name, [],
                                     error=f'SERVER ERROR {code}')
            return UsageSnapshot(self.provider_id, self.provider_name, [],
                                 error=f'HTTP {code}')
        except requests.ConnectionError:
            return UsageSnapshot(self.provider_id, self.provider_name, [],
                                 error='CONNECTION FAILED')
        except Exception:
            return UsageSnapshot(self.provider_id, self.provider_name, [],
                                 error='UNKNOWN ERROR')

        return self._parse(data)

    def _parse(self, data: dict[str, Any]) -> UsageSnapshot:
        fields: list[QuotaField] = []
        rate_limit = data.get('rate_limit') or {}

        primary = rate_limit.get('primary_window')
        if primary and primary.get('used_percent') is not None:
            seconds = primary.get('limit_window_seconds', 0)
            key, label = _seconds_to_field(seconds, 'primary')
            reset_ts = primary.get('reset_at')
            fields.append(QuotaField(
                key=key,
                label=label,
                utilization=float(primary['used_percent']),
                resets_at=_unix_to_iso(reset_ts) if reset_ts else None,
            ))

        secondary = rate_limit.get('secondary_window')
        if secondary and secondary.get('used_percent') is not None:
            seconds = secondary.get('limit_window_seconds', 0)
            key, label = _seconds_to_field(seconds, 'secondary')
            reset_ts = secondary.get('reset_at')
            fields.append(QuotaField(
                key=key,
                label=label,
                utilization=float(secondary['used_percent']),
                resets_at=_unix_to_iso(reset_ts) if reset_ts else None,
            ))

        # Additional model-specific limits (optional, append after primary/secondary)
        for extra in data.get('additional_rate_limits') or []:
            rl = extra.get('rate_limit') or {}
            pw = rl.get('primary_window')
            if not pw or pw.get('used_percent') is None:
                continue
            name = extra.get('limit_name') or extra.get('metered_feature') or 'extra'
            key = name.lower().replace(' ', '_').replace('-', '_')
            seconds = pw.get('limit_window_seconds', 0)
            _, label = _seconds_to_field(seconds, key)
            reset_ts = pw.get('reset_at')
            fields.append(QuotaField(
                key=key,
                label=f'{name.upper()} - {label.split(" - ")[-1]}' if ' - ' in label else name.upper(),
                utilization=float(pw['used_percent']),
                resets_at=_unix_to_iso(reset_ts) if reset_ts else None,
            ))

        extras: dict[str, Any] = {}
        if data.get('email'):
            extras['email'] = data['email']
        if data.get('plan_type'):
            extras['plan_type'] = data['plan_type']
        credits = data.get('credits')
        if credits:
            extras['credits'] = credits

        return UsageSnapshot(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            fields=fields,
            extras=extras,
        )
