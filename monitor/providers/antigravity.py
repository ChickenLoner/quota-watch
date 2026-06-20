"""AntigravityProvider — Google Antigravity CLI quota via cloudcode-pa API."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
from pathlib import Path
from typing import Any

import requests

from .base import Provider, QuotaField, UsageSnapshot

_CONFIG_DIR   = Path.home() / '.gemini' / 'antigravity-cli'
_CRED_TARGET  = 'gemini:antigravity'
_PROJECTS_FILE = _CONFIG_DIR / 'cache' / 'projects.json'

_QUOTA_URL    = 'https://cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels'
_LOAD_URL     = 'https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist'
_USERINFO_URL = 'https://www.googleapis.com/oauth2/v2/userinfo'
_TIMEOUT      = 10
_VERSION      = '1.18.3'


class _CRED(ctypes.Structure):
    _fields_ = [
        ('Flags',              ctypes.wintypes.DWORD),
        ('Type',               ctypes.wintypes.DWORD),
        ('TargetName',         ctypes.wintypes.LPWSTR),
        ('Comment',            ctypes.wintypes.LPWSTR),
        ('LastWritten',        ctypes.c_ulonglong),
        ('CredentialBlobSize', ctypes.wintypes.DWORD),
        ('CredentialBlob',     ctypes.POINTER(ctypes.c_byte)),
        ('Persist',            ctypes.wintypes.DWORD),
        ('AttributeCount',     ctypes.wintypes.DWORD),
        ('Attributes',         ctypes.c_void_p),
        ('TargetAlias',        ctypes.wintypes.LPWSTR),
        ('UserName',           ctypes.wintypes.LPWSTR),
    ]


def _read_cred_json() -> dict[str, Any]:
    """Read JSON blob from Windows Credential Manager entry gemini:antigravity."""
    try:
        ptr = ctypes.c_void_p()
        ok  = ctypes.windll.advapi32.CredReadW(_CRED_TARGET, 1, 0, ctypes.byref(ptr))
        if not ok:
            return {}
        cred = ctypes.cast(ptr, ctypes.POINTER(_CRED)).contents
        blob = bytes(ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize))
        ctypes.windll.advapi32.CredFree(ptr)
        try:
            s = blob.decode('utf-16-le')
        except Exception:
            s = blob.decode('utf-8', errors='replace')
        return json.loads(s)
    except Exception:
        return {}


def _project_id_from_file() -> str:
    """Read first project ID from agy's projects.json cache."""
    try:
        data = json.loads(_PROJECTS_FILE.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            return next(iter(data.values()), '')
    except Exception:
        pass
    return ''


def _token_expired(expiry_str: str) -> bool:
    """True if ISO8601 expiry timestamp is in the past (with 60s buffer)."""
    try:
        from datetime import datetime, timezone
        exp = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
        return datetime.now(timezone.utc).timestamp() >= exp.timestamp() - 60
    except Exception:
        return True


# Quota groups — Antigravity exposes ~20 model IDs that share quota per family.
# Mirror the reference tool's QuotaGroup aggregation (claude / gemini-pro / gemini-flash).
# Order = display order; each tuple is (group_key, label, matcher).
_GROUPS: list[tuple[str, str, Any]] = [
    ('claude',       'CLAUDE',       lambda m: m.startswith('claude')),
    ('gemini_pro',   'GEMINI PRO',   lambda m: m.startswith('gemini') and 'pro' in m),
    ('gemini_flash', 'GEMINI FLASH', lambda m: m.startswith('gemini') and 'flash' in m),
    ('gemini_other', 'GEMINI',       lambda m: m.startswith('gemini')),
    ('gpt_oss',      'GPT-OSS',      lambda m: m.startswith('gpt')),
]


def _group_for(model_id: str) -> tuple[str, str] | None:
    """Return (group_key, label) for a model ID, or None to skip (internal models)."""
    mid = model_id.lower()
    for key, label, matcher in _GROUPS:
        if matcher(mid):
            return key, label
    return None


def _aggregate_groups(models: dict[str, Any]) -> list[QuotaField]:
    """Collapse per-model quota into quota groups; each group takes its most-used member."""
    # group_key -> {label, utilization, resets_at}
    agg: dict[str, dict[str, Any]] = {}
    order: dict[str, int] = {key: i for i, (key, _, _) in enumerate(_GROUPS)}

    for model_id, model_info in models.items():
        grp = _group_for(model_id)
        if grp is None:
            continue                          # skip tab_*/chat_*/unnamed internal models
        key, label  = grp
        qi          = model_info.get('quotaInfo', {})
        remaining   = float(qi.get('remainingFraction', 1.0))
        utilization = max(0.0, min(100.0, (1.0 - remaining) * 100))
        resets_at   = qi.get('resetTime') or None

        cur = agg.get(key)
        if cur is None or utilization > cur['utilization']:
            agg[key] = {'label': label, 'utilization': utilization, 'resets_at': resets_at}

    fields = [
        QuotaField(key=key, label=v['label'], utilization=v['utilization'], resets_at=v['resets_at'])
        for key, v in sorted(agg.items(), key=lambda kv: order.get(kv[0], 99))
    ]
    return fields


class AntigravityProvider(Provider):
    provider_id   = 'antigravity'
    provider_name = 'Antigravity'

    def __init__(self) -> None:
        self._account: dict[str, str] = {}   # cached {email, plan} — rarely changes

    def is_available(self) -> bool:
        return _CONFIG_DIR.exists()

    def _account_info(self, access_token: str, project_id: str) -> dict[str, str]:
        """Fetch email (Google userinfo) + plan tier (loadCodeAssist). Cached after first success."""
        if self._account:
            return self._account
        email = ''
        plan  = ''
        try:
            r = requests.get(
                _USERINFO_URL,
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=_TIMEOUT,
            )
            if r.ok:
                email = r.json().get('email', '')
        except requests.RequestException:
            pass
        try:
            r = requests.post(
                _LOAD_URL,
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type':  'application/json',
                    'User-Agent':    f'antigravity/{_VERSION} windows/amd64',
                },
                json={
                    'cloudaicompanionProject': project_id,
                    'metadata': {'ideType': 'ANTIGRAVITY', 'platform': 'WINDOWS_AMD64', 'pluginType': 'GEMINI'},
                },
                timeout=_TIMEOUT,
            )
            if r.ok:
                tier = r.json().get('currentTier', {})
                plan = (tier.get('id') or '').replace('-', ' ').title()
        except requests.RequestException:
            pass
        info = {'email': email, 'plan': plan}
        if email or plan:
            self._account = info     # cache only on success
        return info

    def fetch(self) -> UsageSnapshot:
        cred       = _read_cred_json()
        token_obj  = cred.get('token')
        if not isinstance(token_obj, dict):
            return UsageSnapshot(
                self.provider_id, self.provider_name, [],
                error='No token — run: agy auth login', auth_error=True,
            )

        access_token = token_obj.get('access_token', '')
        expiry_str   = token_obj.get('expiry', '')
        project_id   = _project_id_from_file()

        # Use the access token agy stores in Credential Manager. agy refreshes it
        # on its own background loop, so a stale token means agy isn't running —
        # tell the user to open Antigravity rather than minting tokens ourselves.
        if not access_token or _token_expired(expiry_str):
            return UsageSnapshot(
                self.provider_id, self.provider_name, [],
                error='Token expired — open Antigravity to refresh', auth_error=True,
            )

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type':  'application/json',
            'User-Agent':    f'antigravity/{_VERSION} windows/amd64',
        }
        body = {'project': project_id} if project_id else {}

        try:
            resp = requests.post(_QUOTA_URL, headers=headers, json=body, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            return UsageSnapshot(
                self.provider_id, self.provider_name, [],
                error=str(exc)[:120],
            )

        if resp.status_code == 401:
            return UsageSnapshot(
                self.provider_id, self.provider_name, [],
                error='Token expired — open Antigravity to refresh', auth_error=True,
            )
        if not resp.ok:
            return UsageSnapshot(
                self.provider_id, self.provider_name, [],
                error=f'HTTP {resp.status_code}: {resp.text[:80]}',
            )

        data: dict[str, Any] = resp.json()
        models: dict[str, Any] = data.get('models', {})

        fields = _aggregate_groups(models)
        if not fields:
            return UsageSnapshot(
                self.provider_id, self.provider_name, [],
                error=f'No quota data — raw: {str(data)[:120]}',
            )

        # Most-used first → primary tray field shows most critical group
        fields.sort(key=lambda f: f.utilization, reverse=True)

        acct   = self._account_info(access_token, project_id)
        extras: dict[str, Any] = {}
        if acct.get('email'):
            extras['email'] = acct['email']
        if acct.get('plan'):
            extras['plan_name'] = acct['plan']

        return UsageSnapshot(self.provider_id, self.provider_name, fields, extras=extras)
