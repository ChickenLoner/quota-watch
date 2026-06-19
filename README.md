# QuotaWatch

SOC-themed Windows system tray app that monitors AI quota usage in real time — Claude, OpenAI Codex, and Windsurf in one place.

Inspired by [CodexBar](https://github.com/steipete/CodexBar) and [usage-monitor-for-claude](https://github.com/jens-duttke/usage-monitor-for-claude). Styled after a Security Operations Center console: dark navy, cyan/amber/red severity indicators, hex grid backdrop.

---

## Features

- **Multi-provider** — Claude, OpenAI Codex, Windsurf; tabs switch between them in the popup
- **Per-provider account info** — email and plan shown per active tab
- **Live tray icon** — dual progress bars (top usage + second field) color-coded green → amber → red
- **Session countdown** — reset timer (e.g. `4h22`) drawn on tray icon in cyan
- **Severity badges** — NOMINAL / WARNING / CRITICAL / BREACH on each bar
- **Smart alerts** — tray notifications at 50%, 80%, 95% session; 95% weekly; time-aware (skips if usage is proportionally on-track)
- **Reset detection** — notifies when quota resets after near-exhaustion
- **Adaptive polling** — 3-min normally, 30s when session usage is rising
- **Extra usage** — Claude credit balance if enabled
- **Claude Code versions** — discovers CLI + IDE extensions (VS Code, Cursor, Windsurf)
- **Start with Windows** — registry autostart (frozen EXE only)
- **No console window** — silent background tray process

---

## Providers

| Provider | Auth source | Fields tracked |
|---|---|---|
| **Claude** | `~/.claude/.credentials.json` | SESSION 5H, WEEKLY 7D, plan fields |
| **OpenAI Codex** | `~/.codex/auth.json` or `OPENAI_API_KEY` | SESSION (1H/3H/5H), DAILY, WEEKLY 7D, MONTHLY 30D |
| **Windsurf** | Local SQLite `state.vscdb` (no login needed) | DAILY 1D, WEEKLY 7D |

New quota fields from the Claude API appear automatically — no code changes needed.

---

## Platform coverage

| Platform | Implementation |
|---|---|
| Windows 10+ | System tray app — Python + WebView2 [`monitor/`](monitor/) |
| Linux / Kali | Statusline + TUI dashboard — Python + rich [`linux/`](linux/) |

---

## Requirements

### Windows
- Windows 10 or later
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated (`claude auth login`)
- [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) — pre-installed on Windows 11, download separately for Windows 10

### Linux
- Python 3.10+, `pip install requests rich`
- Claude Code installed and authenticated (`claude login`)

See [`linux/README.md`](linux/README.md) for details.

---

## Usage

### Pre-built EXE

Download `QuotaWatch.exe` from [Releases](../../releases) and run. No installation needed.

### From source

```powershell
git clone https://github.com/ChickenLoner/quota-watch
cd quota-watch
uv sync
uv run python -m monitor
```

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

---

## Build EXE

```powershell
uv run pyinstaller quota_watch.spec --noconfirm
# Output: dist\QuotaWatch.exe  (~16 MB, single file)
```

---

## Project structure

```
monitor/
  __main__.py        entry point — DPI setup, webview loop, restart
  app.py             tray icon, polling loop, alerts, status cache
  tray.py            Pillow icon renderer, theme watcher
  popup.py           pywebview popup window, payload builder
  formatting.py      time/countdown formatters
  autostart.py       Windows registry autostart
  claude_cli.py      Claude CLI/extension version discovery
  html/
    popup.html       popup markup
    popup.css        SOC console theme
    popup.js         tab switching, bar rendering, live countdowns
  providers/
    base.py          Provider ABC, QuotaField, UsageSnapshot dataclasses
    claude.py        Claude OAuth → api.anthropic.com/api/oauth/usage
    codex.py         Codex OAuth → chatgpt.com/backend-api/wham/usage
    windsurf.py      local SQLite state.vscdb (no network)
linux/               Linux/Kali statusline + TUI implementation
```

---

## How it works

Each provider reads its own auth token locally and polls its quota endpoint. Claude reads `~/.claude/.credentials.json`; Codex reads `~/.codex/auth.json`; Windsurf reads a local SQLite DB with no network call. Credentials are used only in `Authorization` headers — never logged, stored elsewhere, or sent to any other destination.

---

## Security

- Reads local credential files and SQLite DBs only — no keychain, no password prompt
- HTTPS to `api.anthropic.com` and `chatgpt.com` only
- No telemetry, analytics, or third-party services
- No `eval()`, `exec()`, dynamic imports, or obfuscated strings
- All source in this repo — audit before running

---

## License

MIT
