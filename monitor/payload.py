"""Popup payload building — pure data shaping from snapshots + CLI install probing.

Kept separate from popup.py's window/ctypes machinery so the payload builders
(`_build_payload`, `_provider_entry`, `_bar_entry`) stay pure and testable.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import __version__
from .severity import sev_for

if TYPE_CHECKING:
    from .app import App

_PROVIDER_DOTS = {
    'claude':      '#c2683f',
    'codex':       '#5b8def',
    'windsurf':    '#2bb3a3',
    'antigravity': '#b07ae0',
}

_CHANGELOG_URLS: dict[str, str] = {
    'claude':      'https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md',
    'codex':       'https://github.com/openai/codex/releases',
    'antigravity': 'https://github.com/google-antigravity/antigravity-cli/blob/main/CHANGELOG.md',
}
_CHANGELOG_LABELS: dict[str, str] = {
    'codex':       'CODEX CLI',
    'antigravity': 'AGY CLI',
}
CHANGELOG_URL = _CHANGELOG_URLS['claude']

_RE_AUTH_HINTS: dict[str, str] = {
    'claude':      'claude auth login',
    'codex':       'codex login',
    'antigravity': 'open Antigravity to refresh',
}

_ORDER = ['claude', 'codex', 'windsurf', 'antigravity']

_SEV_RANK = {'crit': 0, 'err': 1, 'warn': 2, 'ok': 3}

_install_cache: dict[str, tuple[float, list]] = {}
_INSTALL_TTL = 300  # seconds


def _bar_entry(f: Any) -> dict[str, Any]:
    pct    = f.utilization
    resets = f.resets_at or ''
    sev    = sev_for(f.key, pct)
    return {
        'key':        f.key,
        'label':      f.label,
        'pct':        round(pct, 1),
        'sev':        sev,
        'resets_at':  resets or None,
    }


def _extra_usage(snap_data: Any) -> dict[str, Any] | None:
    extra_data = snap_data.extras.get('extra_usage') if snap_data else None
    if not extra_data or not extra_data.get('is_enabled'):
        return None
    limit = extra_data.get('monthly_limit', 0) or 0
    if limit <= 0:
        return None
    used = extra_data.get('used_credits', 0) or 0
    pct  = used / limit * 100
    return {
        'pct_text':   f'{pct:.0f}%',
        'fill_pct':   max(0.0, min(1.0, pct / 100)),
        'spent_text': f'{used / 100:.2f} / {limit / 100:.2f}',
    }


def _run_version(path: str) -> str:
    try:
        proc = subprocess.run(
            [path, '--version'], capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        out = (proc.stdout or proc.stderr or '').strip()
        m = re.search(r'(\d+\.\d+[\.\d]*)', out)
        return m.group(1) if m else ''
    except Exception:
        return ''


def _fetch_installs() -> list[dict[str, str]]:
    try:
        from .claude_cli import find_installations
        return [{'name': i.name, 'version': i.version} for i in find_installations()]
    except Exception:
        return []


def _fetch_codex_installs() -> list[dict[str, str]]:
    path = shutil.which('codex')
    if not path:
        return []
    v = _run_version(path)
    return [{'name': 'CLI', 'version': v}] if v else []


def _find_agy_path() -> str | None:
    path = shutil.which('agy')
    if not path:
        local = Path(os.environ.get('LOCALAPPDATA', '')) / 'agy' / 'bin' / 'agy.exe'
        if local.is_file():
            return str(local)
    return path


def _fetch_agy_installs() -> list[dict[str, str]]:
    path = _find_agy_path()
    if not path:
        return []
    v = _run_version(path)
    return [{'name': 'CLI', 'version': v}] if v else []


def _cached(key: str, fn) -> list:
    now = time.time()
    entry = _install_cache.get(key)
    if entry and now - entry[0] < _INSTALL_TTL:
        return entry[1]
    result = fn()
    _install_cache[key] = (now, result)
    return result


def _installs() -> list[dict[str, str]]:
    return _cached('claude', _fetch_installs)


def _codex_installs() -> list[dict[str, str]]:
    return _cached('codex', _fetch_codex_installs)


def _agy_installs() -> list[dict[str, str]]:
    return _cached('agy', _fetch_agy_installs)


def prewarm_installs() -> None:
    """Pre-populate install caches from a background thread at startup."""
    _installs()
    _codex_installs()
    _agy_installs()


def _provider_entry(pid: str, s: Any, claude_profile: dict[str, Any] | None) -> dict[str, Any]:
    stale = getattr(s, 'stale', False)
    bars = [_bar_entry(f) for f in s.fields]  # always build; stale snapshots carry cached fields

    auth_status = 'connected'
    re_auth_hint = None
    error_text = None
    if s.auth_error:
        auth_status = 'auth_error'
        re_auth_hint = _RE_AUTH_HINTS.get(pid)
        error_text = s.error
    elif stale:
        auth_status = 'connected'
        error_text = s.error
    elif s.error:
        auth_status = 'error'
        error_text = s.error

    email = None
    plan = None
    if pid == 'claude' and claude_profile:
        email = claude_profile.get('email') or None
        plan = claude_profile.get('plan') or None
    elif s.extras:
        email = s.extras.get('email') or None
        plan_raw = s.extras.get('plan_type') or s.extras.get('plan_name') or ''
        plan = plan_raw.replace('_', ' ').title() if plan_raw else None

    if bars:
        worst = min((b['sev'] for b in bars), key=lambda sev: _SEV_RANK[sev])
    else:
        worst = 'err' if auth_status != 'connected' else 'ok'

    entry: dict[str, Any] = {
        'id':          pid,
        'name':        s.provider_name,
        'dot':         _PROVIDER_DOTS.get(pid, '#7d8694'),
        'plan':        plan,
        'email':       email,
        'authStatus':  auth_status,
        'reAuthHint':  re_auth_hint,
        'errorText':   error_text,
        'stale':       stale,
        'statusSev':   worst,
        'bars':           bars,
        'extra':          None,
        'installs':       None,
        'changelog_url':  _CHANGELOG_URLS.get(pid),
        'changelog_label': _CHANGELOG_LABELS.get(pid),
    }
    if pid == 'claude':
        entry['extra'] = _extra_usage(s)
        entry['installs'] = _installs()
    elif pid == 'codex':
        entry['installs'] = _codex_installs()
    elif pid == 'antigravity':
        entry['installs'] = _agy_installs()
    return entry


def _build_payload(app: App) -> dict[str, Any]:
    """Build the JSON payload for the popup JS init()."""
    snap      = app.cache_snapshot()
    snapshots = snap.snapshots  # dict[provider_id, UsageSnapshot]

    claude_profile = None
    if snap.profile:
        account = snap.profile.get('account', {})
        org     = snap.profile.get('organization', {})
        plan    = org.get('organization_type', '').replace('_', ' ').title()
        claude_profile = {'email': account.get('email', ''), 'plan': plan or ''}

    ordered_ids = [pid for pid in _ORDER if pid in snapshots] + \
                  [pid for pid in snapshots if pid not in _ORDER]

    providers = [_provider_entry(pid, snapshots[pid], claude_profile) for pid in ordered_ids]

    # Status (footer)
    has_any_data = any(not s.error and s.fields for s in snapshots.values())
    if not has_any_data:
        status: dict[str, Any] = {
            'text':     snap.last_error[:120] if snap.last_error else 'SYNCING...',
            'is_error': bool(snap.last_error),
        }
    else:
        status = {
            'last_success_time': snap.last_success_time,
            'next_poll_time':    app.next_poll_time,
            'refreshing':        False,
            'error':             snap.last_error[:120] if snap.last_error else None,
        }

    return {
        'version':   f'v{__version__}',
        'status':    status,
        'providers': providers,
    }
