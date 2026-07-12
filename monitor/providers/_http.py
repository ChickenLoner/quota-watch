"""Shared HTTP transport for providers — one GET+error-classification path.

Providers get the raw JSON on success, or an `HttpError` carrying the status
and (when present) Retry-After, and map it to their own user-facing messages.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

# One pooled session across all polls — keep-alive reuses TCP/TLS connections
# instead of a fresh handshake on every provider fetch.
_session = requests.Session()


@dataclass
class HttpError:
    """Transport/HTTP failure. `status` is the HTTP code (0 for transport errors);
    `transport` is '' for HTTP errors, else 'connection' | 'unknown'."""
    status: int = 0
    transport: str = ''
    retry_after: float | None = None


def _retry_after(resp: requests.Response | None) -> float | None:
    if resp is None:
        return None
    try:
        return float(resp.headers.get('Retry-After', ''))
    except (ValueError, TypeError):
        return None


def get_json(url: str, headers: dict[str, str], timeout: float = 10) -> tuple[dict[str, Any] | None, HttpError | None]:
    """GET `url` and parse JSON. Returns (data, None) on success, (None, HttpError) on failure."""
    try:
        r = _session.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json(), None
    except requests.HTTPError as e:
        resp = e.response
        status = resp.status_code if resp is not None else 0
        return None, HttpError(status=status, retry_after=_retry_after(resp))
    except requests.ConnectionError:
        return None, HttpError(transport='connection')
    except Exception:
        return None, HttpError(transport='unknown')
