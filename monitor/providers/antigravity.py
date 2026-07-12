"""AntigravityProvider — Google Antigravity CLI quota via local language server.

Reads quota from agy's local HTTPS server (GetUserStatus) — same data source
agy uses for its own display. If agy is not running, returns a prompt to start it.
"""
from __future__ import annotations

import json
import re
import ssl
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

from .base import Provider, QuotaField, UsageSnapshot

_CONFIG_DIR = Path.home() / '.gemini' / 'antigravity-cli'
_LOCAL_PATH = '/exa.language_server_pb.LanguageServerService/GetUserStatus'
_LOCAL_BODY = json.dumps({'metadata': {'ideName': 'antigravity', 'extensionName': 'antigravity', 'locale': 'en'}}).encode()

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode    = ssl.CERT_NONE

# Quota groups shown in UI (label-matched since local server uses opaque enum IDs)
_GROUPS = [('gemini', 'GEMINI'), ('claude_gpt', 'CLAUDE & GPT')]
_GROUP_ORDER = {key: i for i, (key, _) in enumerate(_GROUPS)}


def _agy_local_ports() -> list[int]:
    """Ports agy is currently listening on (empty when agy not running)."""
    try:
        ps = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             '(Get-Process agy -ErrorAction SilentlyContinue).Id'],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        pids = {p.strip() for p in ps.stdout.strip().split() if p.strip()}
        if not pids:
            return []
        ns = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, timeout=5,
                            creationflags=subprocess.CREATE_NO_WINDOW)
        ports: list[int] = []
        for line in ns.stdout.splitlines():
            m = re.search(r'127\.0\.0\.1:(\d+)\s+\S+\s+LISTENING\s+(\d+)', line)
            if m and m.group(2) in pids:
                ports.append(int(m.group(1)))
        return ports
    except Exception:
        return []


def _local_get_user_status(port: int) -> dict[str, Any] | None:
    """POST GetUserStatus to agy's local HTTPS server. No CSRF token for CLI."""
    try:
        req = urllib.request.Request(
            f'https://127.0.0.1:{port}{_LOCAL_PATH}',
            data=_LOCAL_BODY,
            headers={'Content-Type': 'application/json', 'Connect-Protocol-Version': '1'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=3, context=_SSL_CTX) as r:
            if r.status == 200:
                return json.loads(r.read())
    except Exception:
        pass
    return None


def _fields_from_user_status(data: dict[str, Any]) -> tuple[list[QuotaField], dict[str, str]]:
    """Parse GetUserStatus into QuotaFields + extras. Matches agy's own display.

    agy shows quota as model-group remainingFraction from cascadeModelConfigData,
    not the planStatus prompt/flow credits (which track a separate billing metric).
    """
    us  = data.get('userStatus', data)
    ps  = us.get('planStatus', {})
    pi  = ps.get('planInfo', {})
    cmd = us.get('cascadeModelConfigData', {})

    # Aggregate model groups from cascadeModelConfigData (same source as agy's UI).
    # Local server uses opaque model enum IDs (MODEL_PLACEHOLDER_Mxx), so group by
    # display label text instead of model ID.
    agg: dict[str, dict[str, Any]] = {}
    for mc in (cmd.get('clientModelConfigs') or []):
        lbl = (mc.get('label') or '').lower()
        if 'gemini' in lbl:
            grp_key, grp_label = 'gemini', 'GEMINI'
        elif 'claude' in lbl or 'gpt' in lbl:
            grp_key, grp_label = 'claude_gpt', 'CLAUDE & GPT'
        else:
            continue
        qi          = mc.get('quotaInfo') or {}
        # API omits remainingFraction when quota is fully exhausted; treat as 0.0
        remaining   = float(qi.get('remainingFraction', 0.0))
        utilization = max(0.0, min(100.0, (1.0 - remaining) * 100))
        resets_at   = qi.get('resetTime') or None
        cur = agg.get(grp_key)
        if cur is None or utilization > cur['utilization']:
            agg[grp_key] = {'label': grp_label, 'utilization': utilization, 'resets_at': resets_at}

    fields = [
        QuotaField(key=k, label=v['label'], utilization=v['utilization'], resets_at=v['resets_at'])
        for k, v in sorted(agg.items(), key=lambda kv: _GROUP_ORDER.get(kv[0], 99))
    ]

    extras: dict[str, str] = {}
    if us.get('email'):
        extras['email'] = us['email']
    plan = pi.get('planName', '')
    if plan:
        extras['plan_name'] = plan

    return fields, extras


class AntigravityProvider(Provider):
    provider_id   = 'antigravity'
    provider_name = 'Antigravity'

    def __init__(self) -> None:
        self._port: int | None = None   # last known agy port, to skip the port scan

    def is_available(self) -> bool:
        return _CONFIG_DIR.exists()

    def _snapshot_from_port(self, port: int) -> UsageSnapshot | None:
        data = _local_get_user_status(port)
        if not data:
            return None
        fields, extras = _fields_from_user_status(data)
        if not fields:
            return None
        fields.sort(key=lambda f: f.utilization, reverse=True)
        return self._ok(fields, extras)

    def fetch(self) -> UsageSnapshot:
        # Happy path: reuse the cached port and skip the powershell + netstat scan.
        if self._port is not None:
            snap = self._snapshot_from_port(self._port)
            if snap is not None:
                return snap
            self._port = None  # cached port went away — fall through to a rescan

        for port in _agy_local_ports():
            snap = self._snapshot_from_port(port)
            if snap is not None:
                self._port = port
                return snap

        return self._err('Run agy to see quota')
