"""API client - reads Claude OAuth token and fetches usage/profile data."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

CLAUDE_CONFIG_DIR = (
    Path(os.environ['CLAUDE_CONFIG_DIR'])
    if os.environ.get('CLAUDE_CONFIG_DIR')
    else Path.home() / '.claude'
)
CREDENTIALS_FILE = CLAUDE_CONFIG_DIR / '.credentials.json'

API_USAGE   = 'https://api.anthropic.com/api/oauth/usage'
API_PROFILE = 'https://api.anthropic.com/api/oauth/profile'

# Known Anthropic internal codenames → display labels
FIELD_LABELS: dict[str, str] = {
    'five_hour':            'SESSION - 5H',
    'seven_day':            'WEEKLY - 7D',
    'seven_day_omelette':   'DESIGN [beta] - 7D',   # Claude Design beta
    'seven_day_opus':       'OPUS - 7D',
    'seven_day_sonnet':     'SONNET - 7D',
    'seven_day_cowork':     'COWORK - 7D',
    'seven_day_oauth_apps': 'OAUTH APPS - 7D',
    'tangelo':              'TANGELO',
    'iguana_necktie':       'IGUANA NECKTIE',
    'omelette_promotional': 'DESIGN PROMO',
}


def field_label(key: str) -> str:
    """Return display label for an API field key."""
    return FIELD_LABELS.get(key, key.upper().replace('_', ' '))


def read_token() -> str | None:
    """Read the current OAuth access token from Claude credentials file."""
    try:
        data = json.loads(CREDENTIALS_FILE.read_text(encoding='utf-8'))
        return data.get('claudeAiOauth', {}).get('accessToken') or None
    except Exception:
        return None


def _headers() -> dict[str, str] | None:
    token = read_token()
    if not token:
        return None
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'anthropic-beta': 'oauth-2025-04-20',
    }


def fetch_usage() -> dict[str, Any]:
    """Fetch usage data. Returns dict with 'error' key on failure."""
    hdrs = _headers()
    if not hdrs:
        return {'error': 'NO TOKEN - run: claude auth login', 'auth_error': True}

    try:
        r = requests.get(API_USAGE, headers=hdrs, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        if code == 401:
            return {'error': 'TOKEN EXPIRED - refreshing...', 'auth_error': True}
        if code == 429:
            retry = None
            try:
                retry = int(e.response.headers.get('Retry-After', 0))
            except Exception:
                pass
            return {'error': 'RATE LIMITED', 'rate_limited': True, 'retry_after': retry}
        if 500 <= code < 600:
            return {'error': f'SERVER ERROR {code}'}
        return {'error': f'HTTP {code}'}
    except requests.ConnectionError:
        return {'error': 'CONNECTION FAILED'}
    except Exception:
        return {'error': 'UNKNOWN ERROR'}


def fetch_profile() -> dict[str, Any] | None:
    """Fetch account profile. Returns None on failure."""
    hdrs = _headers()
    if not hdrs:
        return None
    try:
        r = requests.get(API_PROFILE, headers=hdrs, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def quota_fields(data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Extract active (non-null) quota fields from usage response."""
    result = []
    for key, value in data.items():
        if key == 'extra_usage':
            continue
        if isinstance(value, dict) and value.get('utilization') is not None:
            result.append((key, value))
    return result
