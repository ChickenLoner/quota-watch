#!/usr/bin/env bash
# install.sh — Install Claude Monitor for Linux/Kali
# Deploys the statusline fetcher, TUI dashboard, and statusline script.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
LOCAL_BIN="$HOME/.local/bin"

echo "Claude Monitor — Linux Installer"
echo "================================="

# --- Prerequisites --------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required. Install it with: sudo apt install python3"
    exit 1
fi
if ! python3 -c "import requests, rich" 2>/dev/null; then
    echo "Installing required Python packages..."
    pip3 install --user requests rich
fi
if [ ! -f "$CLAUDE_DIR/.credentials.json" ]; then
    echo "Warning: ~/.claude/.credentials.json not found."
    echo "  Run 'claude login' first, then re-run this installer."
fi

# --- Deploy files ---------------------------------------------------------
echo ""
echo "Deploying files..."

cp "$SCRIPT_DIR/fetch-claude-usage.py" "$CLAUDE_DIR/fetch-claude-usage.py"
chmod +x "$CLAUDE_DIR/fetch-claude-usage.py"
echo "  ✓  ~/.claude/fetch-claude-usage.py"

cp "$SCRIPT_DIR/statusline-command.sh" "$CLAUDE_DIR/statusline-command.sh"
chmod +x "$CLAUDE_DIR/statusline-command.sh"
echo "  ✓  ~/.claude/statusline-command.sh"

mkdir -p "$LOCAL_BIN"
cp "$SCRIPT_DIR/claude-usage" "$LOCAL_BIN/claude-usage"
chmod +x "$LOCAL_BIN/claude-usage"
echo "  ✓  ~/.local/bin/claude-usage"

# --- Claude Code statusline config ----------------------------------------
SETTINGS="$CLAUDE_DIR/settings.json"
STATUSLINE_CMD="bash ~/.claude/statusline-command.sh"

if [ ! -f "$SETTINGS" ]; then
    echo '{"statusLine":{"type":"command","command":"bash ~/.claude/statusline-command.sh"}}' \
        > "$SETTINGS"
    echo "  ✓  ~/.claude/settings.json (created)"
elif ! grep -q "statusline-command.sh" "$SETTINGS" 2>/dev/null; then
    echo ""
    echo "Note: ~/.claude/settings.json exists but doesn't reference statusline-command.sh."
    echo "  Add this manually to enable the statusline:"
    echo '  "statusLine": {"type": "command", "command": "bash ~/.claude/statusline-command.sh"}'
else
    echo "  ✓  ~/.claude/settings.json (statusline already configured)"
fi

# --- PATH check -----------------------------------------------------------
if ! echo "$PATH" | grep -q "$LOCAL_BIN"; then
    echo ""
    echo "Note: $LOCAL_BIN is not in your PATH."
    echo "  Add this to ~/.bashrc or ~/.zshrc:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "Done! Run 'claude-usage' to open the dashboard."
echo "     Run 'claude-usage -w' for live watch mode."
