# Claude Monitor — Linux / Kali

Linux port of [SOC Claude Monitor](../README.md). Two components:

1. **Statusline integration** — live usage appended to the Claude Code prompt bar
2. **TUI dashboard** — standalone `claude-usage` terminal command

Both use `GET /api/oauth/usage` with the OAuth token from `~/.claude/.credentials.json` — no separate login, zero token cost.

---

## Screenshot

```
╭──────────  Claude Usage   2026-06-16  19:52:38   · cached 38s ago  ──────────╮
│                                                                              │
│   5-Hour Session    ░░░░░░░░░░░░░░░░░░░░░░    4%  [NOMINAL]   ↺ 4h 57m      │
│                                                                              │
│   7-Day Weekly      ██████████░░░░░░░░░░░░   49%  [NOMINAL]   ↺ 19h 07m     │
│  ──────────────────────────────────────────────────────────────              │
│   Active limit     7d               Severity         [NOMINAL]               │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
```

Statusline (appended to Claude Code prompt bar):
```
claude-sonnet-4-6 | ~/project | [████░] 23% | 46k/200k tokens | ⏱ 0:05 | ⬆4% 7d:49% ↺4h57m
```

---

## Requirements

- Linux (tested on Kali)
- Python 3.10+
- `pip install requests rich`
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated (`claude login`)

---

## Install

```bash
cd linux/
bash install.sh
```

The installer:
- Copies `fetch-claude-usage.py` → `~/.claude/`
- Copies `statusline-command.sh` → `~/.claude/`
- Copies `claude-usage` → `~/.local/bin/`
- Checks `~/.claude/settings.json` for statusline config

---

## Usage

```bash
# TUI dashboard
claude-usage           # show current usage (uses 5-min cache)
claude-usage -r        # force live refresh
claude-usage -w        # watch mode, auto-refresh every 60s
claude-usage -w 30     # watch mode, refresh every 30s

# Statusline runs automatically inside Claude Code sessions
```

---

## How it works

```
linux/
  fetch-claude-usage.py   fetcher + statusline output (deployed to ~/.claude/)
  statusline-command.sh   Claude Code statusline script (deployed to ~/.claude/)
  claude-usage            TUI dashboard (deployed to ~/.local/bin/)
  install.sh              installer
```

**Auth**: reads `claudeAiOauth.accessToken` from `~/.claude/.credentials.json` — written automatically by `claude login`.

**API**: `GET https://api.anthropic.com/api/oauth/usage` with `Authorization: Bearer <token>`. Returns 5h and 7d utilisation (0–100) and ISO 8601 reset timestamps directly as JSON — no parsing tricks needed.

**Cache**: both tools share `~/.cache/claude-usage.json` (300s TTL). The statusline serves the cached string in ~40ms; the TUI shows a spinner on cold start and refreshes the full dataset.

**Severity colours** (from API `limits[].severity`):

| Severity | Colour | Label |
|---|---|---|
| normal | green | NOMINAL |
| warning | yellow | WARNING |
| critical | red | CRITICAL |
| breach | magenta | BREACH |

---

## Security

- Reads one local file (`~/.claude/.credentials.json`)
- HTTPS to `api.anthropic.com` only — no other network destinations
- No telemetry, analytics, or third-party services
- 300s cache prevents excessive API polling
