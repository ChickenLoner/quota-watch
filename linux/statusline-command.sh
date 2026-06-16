#!/usr/bin/env bash
input=$(cat)
input_safe=$(echo "$input" | sed 's/\\/\\\\/g')
model=$(echo "$input_safe" | jq -r 'if (.model | type) == "string" then .model elif (.model | type) == "object" then .model.display_name // .model.id // "?" else "?" end' 2>/dev/null)
cwd=$(echo "$input_safe" | jq -r '.cwd // empty' 2>/dev/null)
used_pct=$(echo "$input_safe" | jq -r '.context_window.used_percentage // empty' 2>/dev/null)
remaining_pct=$(echo "$input_safe" | jq -r '.context_window.remaining_percentage // empty' 2>/dev/null)
ctx_size=$(echo "$input_safe" | jq -r '.context_window.context_window_size // 200000' 2>/dev/null)
duration_ms=$(echo "$input_safe" | jq -r '.cost.total_duration_ms // 0' 2>/dev/null)
cost_usd=$(echo "$input_safe" | jq -r '.cost.total_cost_usd // 0' 2>/dev/null)
if [ -z "$model" ] || [ "$model" = "null" ] || [ "$model" = "?" ]; then
  model=$(echo "$input" | grep -o '"display_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"display_name"[[:space:]]*:[[:space:]]*"//;s/"//')
  [ -z "$model" ] && model="?"
fi
if [ -z "$cwd" ] || [ "$cwd" = "null" ]; then
  cwd=$(echo "$input" | grep -o '"cwd"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"cwd"[[:space:]]*:[[:space:]]*"//;s/"//')
fi
home_dir="$HOME"
short_cwd="${cwd/#$home_dir/~}"
git_branch=""
if [ -n "$cwd" ] && git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git_branch=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null || git -C "$cwd" rev-parse --short HEAD 2>/dev/null)
fi
if [ -n "$used_pct" ] && [ "$used_pct" != "null" ]; then
  pct=${used_pct%.*}
elif [ -n "$remaining_pct" ] && [ "$remaining_pct" != "null" ]; then
  remaining_int=${remaining_pct%.*}
  pct=$(( 100 - remaining_int ))
else
  pct=0
fi
ctx_int=${ctx_size%.*}
used_tokens=$(( pct * ctx_int / 100 ))
if [ "$used_tokens" -ge 1000 ] 2>/dev/null; then
  used_k="$(( (used_tokens + 500) / 1000 ))k"
else
  used_k="${used_tokens:-0}"
fi
if [ "$ctx_int" -ge 1000 ] 2>/dev/null; then
  total_k="$(( (ctx_int + 500) / 1000 ))k"
else
  total_k="${ctx_int:-200k}"
fi
bar_width=20
filled=$(( pct * bar_width / 100 ))
empty=$(( bar_width - filled ))
bar=""
for ((i=0; i<filled; i++)); do bar+="█"; done
for ((i=0; i<empty; i++)); do bar+="░"; done
remaining_health=$(( 100 - pct ))
if [ "$remaining_health" -gt 50 ]; then
  bar_color='\033[32m'
elif [ "$remaining_health" -gt 20 ]; then
  bar_color='\033[33m'
else
  bar_color='\033[31m'
fi
parts=()
[ -n "$model" ] && parts+=("$(printf '\033[36m%s\033[0m' "$model")")
[ -n "$short_cwd" ] && parts+=("$(printf '\033[33m%s\033[0m' "$short_cwd")")
[ -n "$git_branch" ] && parts+=("$(printf '\033[35m%s\033[0m' "$git_branch")")
bar_display="$(printf "${bar_color}[%s] %s%%\033[0m" "$bar" "$pct")"
token_display="$(printf '\033[37m%s/%s tokens\033[0m' "$used_k" "$total_k")"
parts+=("${bar_display}")
parts+=("${token_display}")
dur_int=${duration_ms%.*}
[ -z "$dur_int" ] || [ "$dur_int" = "null" ] && dur_int=0
dur_sec=$(( dur_int / 1000 ))
dur_h=$(( dur_sec / 3600 ))
dur_m=$(( (dur_sec % 3600) / 60 ))
cost_display=""
if [ -n "$cost_usd" ] && [ "$cost_usd" != "null" ] && [ "$cost_usd" != "0" ]; then
  cost_display=$(printf ' $%.2f' "$cost_usd")
fi
time_str="$(printf '\033[90m⏱ %d:%02d%s\033[0m' "$dur_h" "$dur_m" "$cost_display")"
parts+=("${time_str}")
claude_usage=$(python3 ~/.claude/fetch-claude-usage.py 2>/dev/null)
[ -n "$claude_usage" ] && parts+=("$claude_usage")
sep="$(printf ' \033[90m|\033[0m ')"
result=""
for part in "${parts[@]}"; do
  if [ -z "$result" ]; then
    result="$part"
  else
    result="${result}${sep}${part}"
  fi
done
printf '%b\n' "$result"
