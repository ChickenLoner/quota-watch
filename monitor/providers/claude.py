"""Claude provider — reads OAuth token from ~/.claude/, fetches Anthropic usage API."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

from .base import Provider, QuotaField, UsageSnapshot

CLAUDE_CONFIG_DIR = (
    Path(os.environ['CLAUDE_CONFIG_DIR'])
    if os.environ.get('CLAUDE_CONFIG_DIR')
    else Path.home() / '.claude'
)
_CREDENTIALS_FILE = CLAUDE_CONFIG_DIR / '.credentials.json'

_API_USAGE   = 'https://api.anthropic.com/api/oauth/usage'
_API_PROFILE = 'https://api.anthropic.com/api/oauth/profile'

_FIELD_LABELS: dict[str, str] = {
    'five_hour':            'SESSION - 5H',
    'seven_day':            'WEEKLY - 7D',
    'seven_day_omelette':   'DESIGN [beta] - 7D',
    'seven_day_opus':       'OPUS - 7D',
    'seven_day_sonnet':     'SONNET - 7D',
    'seven_day_cowork':     'COWORK - 7D',
    'seven_day_oauth_apps': 'OAUTH APPS - 7D',
    'tangelo':              'TANGELO',
    'iguana_necktie':       'IGUANA NECKTIE',
    'omelette_promotional': 'DESIGN PROMO',
}


def _field_label(key: str) -> str:
    return _FIELD_LABELS.get(key, key.upper().replace('_', ' '))


def read_token() -> str | None:
    try:
        data = json.loads(_CREDENTIALS_FILE.read_text(encoding='utf-8'))
        return data.get('claudeAiOauth', {}).get('accessToken') or None
    except Exception:
        return None


def _auth_headers() -> dict[str, str] | None:
    token = read_token()
    if not token:
        return None
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'anthropic-beta': 'oauth-2025-04-20',
    }


def _parse_response(data: dict[str, Any]) -> tuple[list[QuotaField], dict[str, Any]]:
    """Extract quota fields and provider-specific extras from raw Anthropic response."""
    fields: list[QuotaField] = []
    for key, value in data.items():
        if key == 'extra_usage':
            continue
        if isinstance(value, dict) and value.get('utilization') is not None:
            fields.append(QuotaField(
                key=key,
                label=_field_label(key),
                utilization=value.get('utilization', 0) or 0,
                resets_at=value.get('resets_at') or None,
            ))
    extras: dict[str, Any] = {}
    if 'extra_usage' in data:
        extras['extra_usage'] = data['extra_usage']
    return fields, extras


class ClaudeProvider(Provider):
    provider_id   = 'claude'
    provider_name = 'Claude'

    def is_available(self) -> bool:
        return read_token() is not None

    def fetch(self) -> UsageSnapshot:
        hdrs = _auth_headers()
        if not hdrs:
            return UsageSnapshot(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                fields=[],
                error='NO TOKEN - run: claude auth login',
                auth_error=True,
            )

        try:
            r = requests.get(_API_USAGE, headers=hdrs, timeout=10)
            r.raise_for_status()
            data = r.json()
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            if code == 401:
                return UsageSnapshot(self.provider_id, self.provider_name, [],
                                     error='TOKEN EXPIRED - refreshing...', auth_error=True)
            if code == 429:
                return UsageSnapshot(self.provider_id, self.provider_name, [],
                                     error='RATE LIMITED')
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

        fields, extras = _parse_response(data)
        return UsageSnapshot(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            fields=fields,
            extras=extras,
        )

    def fetch_profile(self) -> dict[str, Any] | None:
        hdrs = _auth_headers()
        if not hdrs:
            return None
        try:
            r = requests.get(_API_PROFILE, headers=hdrs, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None
