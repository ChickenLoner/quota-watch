"""Claude provider — reads OAuth token from ~/.claude/, fetches Anthropic usage API."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .base import Provider, QuotaField, UsageSnapshot
from ._http import get_json

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

_RATE_LIMIT_COOLDOWN = 300  # 5 min default when no Retry-After header
_rate_limited_until: float = 0.0
_cached_user_agent: str = ''


def _user_agent() -> str:
    global _cached_user_agent
    if _cached_user_agent:
        return _cached_user_agent
    try:
        from ..claude_cli import CLI_PATH, cli_version
        v = cli_version(CLI_PATH) if CLI_PATH.is_file() else ''
        _cached_user_agent = f'claude-code/{v or "2.1.0"}'
    except Exception:
        _cached_user_agent = 'claude-code/2.1.0'
    return _cached_user_agent


def _rate_limit_remaining() -> float:
    """Seconds remaining in cooldown, or 0 if not rate-limited."""
    return max(0.0, _rate_limited_until - time.time())


def _record_rate_limit(retry_after_secs: float | None) -> None:
    global _rate_limited_until
    delay = retry_after_secs if (retry_after_secs and retry_after_secs > 0) else _RATE_LIMIT_COOLDOWN
    _rate_limited_until = time.time() + delay


def _clear_rate_limit() -> None:
    global _rate_limited_until
    _rate_limited_until = 0.0


def _field_label(key: str) -> str:
    return _FIELD_LABELS.get(key, key.upper().replace('_', ' '))


_token_cache: tuple[float, str | None] | None = None  # (mtime, token)


def read_token() -> str | None:
    """OAuth access token from ~/.claude/.credentials.json.

    Cached by file mtime so the two reads per poll (is_available + _auth_headers)
    parse the file only once. Behavior is identical to a fresh read.
    """
    global _token_cache
    try:
        mtime = _CREDENTIALS_FILE.stat().st_mtime
    except OSError:
        _token_cache = None
        return None
    if _token_cache is not None and _token_cache[0] == mtime:
        return _token_cache[1]
    try:
        data = json.loads(_CREDENTIALS_FILE.read_text(encoding='utf-8'))
        token = data.get('claudeAiOauth', {}).get('accessToken') or None
    except Exception:
        token = None
    _token_cache = (mtime, token)
    return token


def _auth_headers() -> dict[str, str] | None:
    token = read_token()
    if not token:
        return None
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'anthropic-beta': 'oauth-2025-04-20',
        'User-Agent': _user_agent(),
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

    def __init__(self) -> None:
        self._last_fields: list[QuotaField] = []

    def is_available(self) -> bool:
        return read_token() is not None

    def _rate_limited_snapshot(self, remaining: float) -> UsageSnapshot:
        """RATE LIMITED error — reuses last good fields as stale data if we have them."""
        mins = max(1, int(remaining / 60) + 1)
        if self._last_fields:
            return self._err(f'RATE LIMITED - showing old data, retry in ~{mins}m',
                             stale=True, fields=self._last_fields)
        return self._err(f'RATE LIMITED - retry in ~{mins}m')

    def fetch(self) -> UsageSnapshot:
        hdrs = _auth_headers()
        if not hdrs:
            return self._err('NO TOKEN - run: claude auth login', auth_error=True)

        remaining = _rate_limit_remaining()
        if remaining > 0:
            return self._rate_limited_snapshot(remaining)

        data, err = get_json(_API_USAGE, hdrs, timeout=10)
        if err is not None:
            if err.status == 401:
                return self._err('TOKEN EXPIRED - refreshing...', auth_error=True)
            if err.status == 429:
                _record_rate_limit(err.retry_after)
                return self._rate_limited_snapshot(_rate_limit_remaining())
            if err.transport == 'connection':
                return self._err('CONNECTION FAILED')
            if err.transport == 'unknown':
                return self._err('UNKNOWN ERROR')
            if 500 <= err.status < 600:
                return self._err(f'SERVER ERROR {err.status}')
            return self._err(f'HTTP {err.status}')

        _clear_rate_limit()
        fields, extras = _parse_response(data)
        self._last_fields = fields
        return self._ok(fields, extras)

    def fetch_profile(self) -> dict[str, Any] | None:
        hdrs = _auth_headers()
        if not hdrs:
            return None
        data, err = get_json(_API_PROFILE, hdrs, timeout=10)
        return data if err is None else None
