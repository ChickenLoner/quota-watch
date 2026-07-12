"""Tests for the shared HTTP transport (providers/_http.py)."""
from __future__ import annotations

import requests

from monitor.providers import _http
from monitor.providers._http import HttpError, get_json


class _FakeResp:
    def __init__(self, status=200, json_data=None, headers=None):
        self.status_code = status
        self._json = json_data if json_data is not None else {}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f'HTTP {self.status_code}')
            err.response = self  # type: ignore[assignment]
            raise err

    def json(self):
        return self._json


def _patch_get(monkeypatch, fn):
    monkeypatch.setattr(_http._session, 'get', fn)


def test_ok(monkeypatch):
    _patch_get(monkeypatch, lambda *a, **k: _FakeResp(200, {'x': 1}))
    data, err = get_json('http://x', {})
    assert err is None
    assert data == {'x': 1}


def test_401_auth(monkeypatch):
    _patch_get(monkeypatch, lambda *a, **k: _FakeResp(401))
    data, err = get_json('http://x', {})
    assert data is None
    assert isinstance(err, HttpError) and err.status == 401 and err.transport == ''


def test_429_retry_after(monkeypatch):
    _patch_get(monkeypatch, lambda *a, **k: _FakeResp(429, headers={'Retry-After': '120'}))
    data, err = get_json('http://x', {})
    assert data is None
    assert err.status == 429 and err.retry_after == 120.0


def test_429_no_retry_after(monkeypatch):
    _patch_get(monkeypatch, lambda *a, **k: _FakeResp(429))
    _, err = get_json('http://x', {})
    assert err.status == 429 and err.retry_after is None


def test_500_server(monkeypatch):
    _patch_get(monkeypatch, lambda *a, **k: _FakeResp(503))
    _, err = get_json('http://x', {})
    assert err.status == 503


def test_connection_error(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError()
    _patch_get(monkeypatch, boom)
    data, err = get_json('http://x', {})
    assert data is None and err.status == 0 and err.transport == 'connection'


def test_unknown_error(monkeypatch):
    def boom(*a, **k):
        raise ValueError('boom')
    _patch_get(monkeypatch, boom)
    data, err = get_json('http://x', {})
    assert data is None and err.transport == 'unknown'
