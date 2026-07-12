"""Parse-logic tests for each provider — the refactor-prone normalization code."""
from __future__ import annotations

from monitor.providers.antigravity import _fields_from_user_status
from monitor.providers.claude import _parse_response
from monitor.providers.codex import CodexProvider
from monitor.providers.windsurf import WindsurfProvider


def test_codex_parse_primary_secondary():
    data = {
        'rate_limit': {
            'primary_window':   {'used_percent': 50, 'limit_window_seconds': 18000,  'reset_at': 1783850699},
            'secondary_window': {'used_percent': 20, 'limit_window_seconds': 604800, 'reset_at': 1784357408},
        },
        'email': 'a@b.com', 'plan_type': 'plus',
    }
    snap = CodexProvider()._parse(data)
    assert [f.key for f in snap.fields] == ['five_hour', 'seven_day']
    assert [f.label for f in snap.fields] == ['SESSION - 5H', 'WEEKLY - 7D']
    assert snap.fields[0].utilization == 50
    assert snap.fields[0].resets_at.startswith('20')  # unix_to_iso ISO string
    assert snap.extras == {'email': 'a@b.com', 'plan_type': 'plus'}


def test_codex_parse_skips_null_used_percent():
    data = {'rate_limit': {'primary_window': {'used_percent': None, 'limit_window_seconds': 18000}}}
    snap = CodexProvider()._parse(data)
    assert snap.fields == []


def test_claude_parse_fields_and_extras():
    data = {
        'five_hour': {'utilization': 62.5, 'resets_at': '2026-07-12T20:00:00Z'},
        'seven_day': {'utilization': 41,   'resets_at': None},
        'extra_usage': {'is_enabled': True},
    }
    fields, extras = _parse_response(data)
    by = {f.key: f for f in fields}
    assert set(by) == {'five_hour', 'seven_day'}          # extra_usage excluded from fields
    assert by['five_hour'].utilization == 62.5
    assert by['five_hour'].label == 'SESSION - 5H'
    assert by['seven_day'].resets_at is None
    assert extras['extra_usage'] == {'is_enabled': True}


def test_claude_parse_ignores_non_quota_dicts():
    fields, _ = _parse_response({'account': {'email': 'x'}, 'five_hour': {'utilization': 10, 'resets_at': None}})
    assert [f.key for f in fields] == ['five_hour']       # 'account' has no utilization → skipped


def test_windsurf_parse_remaining_to_used():
    plan = {
        'quotaUsage': {
            'dailyRemainingPercent': 40, 'weeklyRemainingPercent': 80,
            'dailyResetAtUnix': 1783850699, 'weeklyResetAtUnix': 1784357408,
        },
        'planName': 'Pro',
    }
    snap = WindsurfProvider()._parse(plan)
    by = {f.key: f for f in snap.fields}
    assert by['one_day'].utilization == 60.0     # 100 - 40
    assert by['seven_day'].utilization == 20.0   # 100 - 80
    assert by['one_day'].resets_at.startswith('20')
    assert snap.extras['plan_name'] == 'Pro'


def test_antigravity_group_aggregation_takes_most_consumed():
    data = {'userStatus': {
        'cascadeModelConfigData': {'clientModelConfigs': [
            {'label': 'Gemini 3 Pro',  'quotaInfo': {'remainingFraction': 0.25, 'resetTime': '2026-07-12T20:00:00Z'}},
            {'label': 'Claude Sonnet', 'quotaInfo': {'remainingFraction': 0.90}},
            {'label': 'GPT-5',         'quotaInfo': {'remainingFraction': 0.10}},
        ]},
        'email': 'x@y.com',
        'planStatus': {'planInfo': {'planName': 'Pro'}},
    }}
    fields, extras = _fields_from_user_status(data)
    by = {f.key: f for f in fields}
    assert by['gemini'].utilization == 75.0                 # (1 - 0.25) * 100
    assert by['claude_gpt'].utilization == 90.0             # gpt 90% used beats claude 10% used
    assert extras == {'email': 'x@y.com', 'plan_name': 'Pro'}


def test_antigravity_missing_remaining_fraction_is_exhausted():
    data = {'userStatus': {'cascadeModelConfigData': {'clientModelConfigs': [
        {'label': 'Gemini 3 Pro', 'quotaInfo': {}},   # API omits remainingFraction when exhausted
    ]}}}
    fields, _ = _fields_from_user_status(data)
    assert fields[0].utilization == 100.0
