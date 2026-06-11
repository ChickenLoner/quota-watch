import sys
sys.path.insert(0, r'G:\Poc\soc-claude-monitor')

from monitor import __version__
from monitor.api import fetch_usage, fetch_profile, quota_fields, field_label
from monitor.formatting import elapsed_pct, field_period, midnight_positions, time_until
from monitor.claude_cli import find_installations

print('=== API ===')
data = fetch_usage()
for k, v in quota_fields(data):
    pct    = v.get('utilization', 0) or 0
    period = field_period(k)
    tpct   = elapsed_pct(v.get('resets_at', ''), period) if period else None
    reset  = time_until(v.get('resets_at', ''))
    mids   = midnight_positions(v.get('resets_at', ''), period) if period else []
    print(f'  {field_label(k):<30} {pct:5.1f}%  elapsed={tpct}  reset="{reset}"  midnights={len(mids)}')

print()
print('=== INSTALLS ===')
for inst in find_installations():
    print(f'  {inst.name:<20} {inst.version}')

print()
print('=== PROFILE ===')
p = fetch_profile()
if p:
    acct = p.get('account', {})
    org  = p.get('organization', {})
    print(f'  email: {acct.get("email")}')
    print(f'  plan:  {org.get("organization_type")}')
    print(f'  all keys: {list(p.keys())}')
