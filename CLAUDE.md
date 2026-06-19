# QuotaWatch — CLAUDE.md

## Stack
- Python 3.11+, `uv` only (never pip)
- `pystray` tray icon, `pywebview` popup (WebView2 on Windows)
- `pillow` for tray icon rendering
- PyInstaller for single-file EXE: `uv run pyinstaller quota_watch.spec --noconfirm`

## Run
```powershell
uv run python -m monitor
```

## Architecture

### Provider abstraction (`monitor/providers/`)
Every AI service is a `Provider` subclass returning a `UsageSnapshot`:
- `QuotaField(key, label, utilization: float 0–100, resets_at: ISO8601 | None)`
- `UsageSnapshot(provider_id, provider_name, fields, error, auth_error, extras)`
- `extras` carries provider-specific metadata (email, plan_type, credits)

Current providers: `ClaudeProvider`, `CodexProvider`, `WindsurfProvider`

### Auth sources
| Provider | Token location |
|---|---|
| Claude | `~/.claude/.credentials.json` → `oauth_token` |
| Codex | `~/.codex/auth.json` → `OPENAI_API_KEY` or `tokens.access_token` |
| Windsurf | `%APPDATA%\Windsurf\User\globalStorage\state.vscdb` (SQLite, no auth) |

### Alert keys
Composite format: `"{provider_id}:{field_key}"` e.g. `"claude:five_hour"`.
Thresholds live in `app.py:_THRESHOLDS`.

### Popup data flow
`app.py:_write_status_cache()` → `popup.py:_build_payload()` → `popup.js:init()/refreshDone()`

Payload shape: `{ providers: [name, ...], provider_profiles: {name: {email, plan}}, usage: [{provider, label, fill_pct, warn, ...}], ... }`

Tab switching: `activeProvider` in `popup.js` filters `allUsageBars` by `bar.provider`.

### Status cache
Written to `~/.claude/cache/soc-monitor-status.json` after each poll.
Contains `providers` dict (all providers) + legacy `fields` key (Claude only, for statusline compat).

## Key conventions
- `provider_id` lowercase slug (`claude`, `codex`, `windsurf`)
- `provider_name` display name (`Claude`, `Codex`, `Windsurf`) — used as tab label and profile key
- Field `key` values match window duration: `five_hour`, `seven_day`, `thirty_day`, etc.
- `utilization` is 0–100 float (percent used, not remaining)
- `resets_at` always ISO8601 UTC string or `None`

## Adding a new provider
1. Create `monitor/providers/yourprovider.py` — subclass `Provider`, implement `fetch()` and `is_available()`
2. Add to `self._providers` list in `app.py:App.__init__`
3. No changes to popup/tabs needed — they pick up new providers automatically
