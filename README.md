# SOC Claude Monitor

A cybersecurity-themed Windows system tray app that monitors your [Claude](https://claude.ai) API usage limits in real time.

Built as a personal replacement for [usage-monitor-for-claude](https://github.com/jens-duttke/usage-monitor-for-claude), styled after a SOC (Security Operations Center) console — dark navy background, cyan/amber/red severity indicators, hex grid backdrop.

---

## Screenshots

> **Tray icon** — dual progress bars + session countdown

<!-- TODO: replace with actual screenshot -->
```
┌─────────────────────────────────────────┐
│  Tray icon (64×64, scaled to ~20px)     │
│  ┌──────────────────────────────────┐   │
│  │ ████████████████░░░░░░░░░░░░░░░ │  ← SESSION bar (green/amber/red)
│  │             4h22                 │  ← countdown in cyan
│  │ ████░░░░░░░░░░░░░░░░░░░░░░░░░░░ │  ← WEEKLY bar
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

> **Status popup** — click tray icon to open

<!-- TODO: replace with actual screenshot (popup.png) -->
```
┌─────────────────────────────────────────┐
│ ● CLAUDE MONITOR                   ↻ × │
├─────────────────────────────────────────┤
│ ║ OPERATOR                              │
│   EMAIL    operator@example.com         │
│   CLEARANCE  Claude Pro                 │
├─────────────────────────────────────────┤
│ ║ QUOTA CHANNELS                        │
│                                         │
│  SESSION - 5H          63%  [WARNING]   │
│  ████████████████░░░░░░░░░░░░░░░░░░░   │
│  RESETS IN 4H 22M (06:00)               │
│                                         │
│  WEEKLY - 7D            5%  [NOMINAL]   │
│  ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
│  RESETS IN 6D 22H 39M (WED 01:59)      │
│                                         │
├─────────────────────────────────────────┤
│ ║ CLAUDE CODE                CHANGELOG  │
│   CLI        1.x.x                      │
│   VS Code    1.x.x                      │
├─────────────────────────────────────────┤
│ UPDATED 12S AGO · NEXT IN 2M      v0.1.0│
└─────────────────────────────────────────┘
```

---

## Features

- **Live tray icon** — dual progress bars (session 5h + weekly 7d) color-coded green/amber/red by threshold (Design tokens now merged into session 5h)
- **Session countdown on icon** — reset timer (e.g. `4h22`) drawn directly on the tray icon in cyan
- **On-demand refresh** — `↻` button in popup header fetches fresh data instantly without waiting for the next poll
- **Detail popup** — SOC-themed overlay with all active quota channels, severity badges (NOMINAL / WARNING / CRITICAL / BREACH), account info, and Claude Code versions
- **Live reset countdown** — each bar shows a ticking cyan countdown: `RESETS IN 4H 22M (06:00)` for same-day, `RESETS IN 6D 22H 39M (WED 01:59)` for weekly
- **Smart alerts** — tray notifications at 50%, 80%, 95% session usage; 95% weekly; re-arm automatically after quota reset
- **Reset detection** — notifies when a quota resets (usage drops sharply after near-exhaustion)
- **Time-aware alerts** — skips alert if usage is proportionally on-track for elapsed time (not a false alarm)
- **Adaptive polling** — 3-minute intervals normally; drops to 30 seconds when session usage is rising
- **Extra usage** — shows credit balance and % if extra usage is enabled on the account
- **Claude Code versions** — discovers CLI and IDE extension versions (VS Code, VS Code Insiders, Cursor, Windsurf)
- **Start with Windows** — optional autostart via registry (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`)
- **Restart** — tray menu option to restart the monitor (picks up token refresh without re-login)
- **No console window** — runs silently; error dialogs only on fatal crash

---

## Quota channels (as of 2026-06)

| API field | Display label | Your plan |
|---|---|---|
| `five_hour` | SESSION - 5H | ✓ active |
| `seven_day` | WEEKLY - 7D | ✓ active |
| `seven_day_omelette` | DESIGN [beta] - 7D | merged into SESSION - 5H (no longer separate) |
| `seven_day_opus` | OPUS - 7D | Claude Max only |
| `seven_day_sonnet` | SONNET - 7D | Claude Max only |
| `seven_day_cowork` | COWORK - 7D | — |
| `seven_day_oauth_apps` | OAUTH APPS - 7D | — |

New fields from the API appear automatically — no code changes needed.

---

## Requirements

- Windows 10 or later
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated (`claude auth login`)
- [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) — pre-installed on Windows 11; download separately for Windows 10

---

## Usage

### Pre-built EXE

Download `SocClaudeMonitor.exe` from [Releases](../../releases) and run it. No installation needed.

### From source

```powershell
git clone https://github.com/ChickenLoner/soc-claude-monitor
cd soc-claude-monitor
uv sync
uv run -m monitor
```

> Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

---

## Build EXE

```powershell
uv add pyinstaller --dev
pyinstaller soc_claude_monitor.spec --noconfirm
# Output: dist\SocClaudeMonitor.exe  (~13 MB, single file)
```

---

## How it works

Reads the Claude OAuth token from `~/.claude/.credentials.json` (written by `claude auth login`) and polls `api.anthropic.com/api/oauth/usage` every 3 minutes. Credentials are used only in the `Authorization` header — never logged, stored elsewhere, or transmitted to any other destination.

---

## Project structure

```
monitor/
  __main__.py      entry point — DPI setup, webview loop, restart
  app.py           tray icon, polling loop, threshold alerts
  api.py           token reading, API calls (credentials isolated here)
  tray.py          Pillow icon renderer, theme watcher
  popup.py         pywebview popup window, payload builder
  formatting.py    time/countdown formatters
  autostart.py     Windows registry autostart
  claude_cli.py    Claude CLI/extension version discovery
  html/
    popup.html     popup markup
    popup.css      SOC console theme
    popup.js       live data rendering, countdown tick, refresh
```

---

## Security

- Reads one local file (`~/.claude/.credentials.json`) and two registry keys (theme + autostart)
- HTTPS to `api.anthropic.com` only — no other network destinations
- No telemetry, analytics, or third-party services
- No `eval()`, `exec()`, dynamic imports, or obfuscated strings
- All source in this repo — audit before running

---

## License

MIT
