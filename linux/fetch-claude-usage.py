#!/usr/bin/env python3
"""
Fetch Claude usage for terminal statusline.

Auth: OAuth Bearer token from ~/.claude/.credentials.json
API:  GET https://api.anthropic.com/api/oauth/usage  (no token cost)
Cache: ~/.cache/claude-usage.json, 300-second TTL
Output: ANSI-colored string for Claude Code statusline
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CREDS = Path.home() / ".claude" / ".credentials.json"
CACHE = Path.home() / ".cache" / "claude-usage.json"
TTL   = 300  # 5-minute cache

# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------

def _c(code, text): return f"\033[{code}m{text}\033[0m"
def grey(t):   return _c(90, t)
def green(t):  return _c(32, t)
def yellow(t): return _c(33, t)
def orange(t): return _c("38;5;208", t)
def red(t):    return _c(31, t)

def pace_color(pct: float):
    """Pace color matching original macOS app thresholds."""
    if pct < 50:  return green
    if pct < 75:  return yellow
    if pct < 90:  return orange
    return red

# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def read_token() -> str | None:
    try:
        with open(CREDS) as f:
            return json.load(f)["claudeAiOauth"]["accessToken"]
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def load_cache() -> dict | None:
    try:
        with open(CACHE) as f:
            c = json.load(f)
        if time.time() - c.get("ts", 0) < TTL:
            return c
    except Exception:
        pass
    return None

def save_cache(data: dict):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    data["ts"] = time.time()
    with open(CACHE, "w") as f:
        json.dump(data, f)

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def fetch_usage(token: str) -> dict:
    """GET /api/oauth/usage — returns JSON directly, zero token cost."""
    import requests

    r = requests.get(
        "https://api.anthropic.com/api/oauth/usage",
        headers={
            "Authorization":     f"Bearer {token}",
            "anthropic-version": "2023-06-01",
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()

def parse_response(data: dict) -> dict:
    fh = data.get("five_hour") or {}
    sd = data.get("seven_day") or {}

    limits   = data.get("limits") or []
    active   = next((l for l in limits if l.get("is_active")), None)
    severity = active.get("severity") if active else (
               limits[0].get("severity") if limits else None)

    return {
        "s_pct":    fh.get("utilization"),      # 0-100 float
        "w_pct":    sd.get("utilization"),
        "s_reset":  fh.get("resets_at"),         # ISO8601 string
        "w_reset":  sd.get("resets_at"),
        "severity": severity,                    # "normal" | "warning" | "critical"
        "limits":   limits,
    }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mins_until(iso_str: str) -> int | None:
    try:
        dt = datetime.fromisoformat(iso_str)
        return max(0, int((dt - datetime.now(timezone.utc)).total_seconds() / 60))
    except Exception:
        return None

def fmt_time(mins: int) -> str:
    h, m = divmod(int(mins), 60)
    return f"{h}h{m:02d}m" if h else f"{m}m"

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cached = load_cache()
    if cached:
        sys.stdout.write(cached.get("out", ""))
        return

    token = read_token()
    if not token:
        return  # silent — never break the statusline

    try:
        raw  = fetch_usage(token)
        data = parse_response(raw)
    except Exception:
        return

    s_pct  = data.get("s_pct")
    w_pct  = data.get("w_pct")
    s_iso  = data.get("s_reset")
    mins   = mins_until(s_iso) if s_iso else None

    parts = []
    if s_pct is not None:
        col = pace_color(s_pct)
        parts.append(col(f"⬆{int(s_pct)}%"))
    if w_pct is not None:
        parts.append(grey(f"7d:{int(w_pct)}%"))
    if mins is not None:
        parts.append(grey(f"↺{fmt_time(mins)}"))

    data["out"] = " ".join(parts)
    save_cache(data)
    sys.stdout.write(data["out"])


if __name__ == "__main__":
    main()
