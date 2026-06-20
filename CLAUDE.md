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

Current providers: `ClaudeProvider`, `CodexProvider`, `WindsurfProvider`, `AntigravityProvider`

### Auth sources
| Provider | Token location |
|---|---|
| Claude | `~/.claude/.credentials.json` → `oauth_token` |
| Codex | `~/.codex/auth.json` → `OPENAI_API_KEY` or `tokens.access_token` |
| Windsurf | `%APPDATA%\Windsurf\User\globalStorage\state.vscdb` (SQLite, no auth) |
| Antigravity | Windows Credential Manager `gemini:antigravity` → JSON `{token:{access_token, refresh_token, expiry}}` |

### Antigravity specifics
- Reads token from Win Credential Manager via ctypes `CredReadW`. Token dict has `access_token` + ISO `expiry`.
- Does **not** self-refresh (would need Antigravity's OAuth client secret — deliberately not shipped). agy refreshes the stored token on its own loop. If `access_token` is missing/expired → `auth_error` snapshot ("Token expired — open Antigravity to refresh").
- Quota API `cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels` returns ~20 models sharing quota per family → collapsed into 4 groups (`CLAUDE`, `GEMINI PRO`, `GEMINI FLASH`, `GPT-OSS`) by `_aggregate_groups`. Each group shows its most-consumed member. Edit `_GROUPS` to adjust.
- `is_available()` = `~/.gemini/antigravity-cli/` exists. Dormant if Antigravity not installed.

### Alert keys
Composite format: `"{provider_id}:{field_key}"` e.g. `"claude:five_hour"`.
Thresholds live in `app.py:_THRESHOLDS`.

### Popup data flow
`app.py:_write_status_cache()` → `popup.py:_build_payload()` → `popup.js:init()/refreshDone()`

Payload shape: `{ providers: [name, ...], provider_profiles: {name: {email, plan, auth_status, re_auth_hint?}}, usage: [...], ... }`

- `providers` now includes ALL polled providers (even errored ones), so auth-errored providers show as tabs.
- `provider_profiles[name].auth_status`: `'connected' | 'auth_error' | 'error'`. Auth-error tabs show `AUTH EXPIRED` + re-auth hint instead of usage bars.
- `re_auth_hint`: CLI command string (e.g. `'claude auth login'`), only present on auth_error entries.

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

### Polling behavior
- Normal: 180s interval; fast: 30s when Claude session usage is rising (3 consecutive fast polls).
- Error backoff: `[30, 60, 120, 240, 600]s` ramp — resets to 0 on first success.
- At-limit skip: if `snap.fields[0].utilization >= 100` and `resets_at` is still in the future (+5 min grace), the provider's API call is skipped and the cached snapshot is reused. This saves API calls while at quota.

## Adding a new provider
1. Create `monitor/providers/yourprovider.py` — subclass `Provider`, implement `fetch()` and `is_available()`
2. Add to `self._providers` list in `app.py:App.__init__`
3. No changes to popup/tabs needed — they pick up new providers automatically
