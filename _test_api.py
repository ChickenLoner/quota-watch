import sys
sys.path.insert(0, r'G:\Poc\soc-claude-monitor')
import monitor.api as api

token = api.read_token()
print('Token found:', bool(token))

data = api.fetch_usage()
if 'error' in data:
    print('Error:', data['error'])
else:
    fields = api.quota_fields(data)
    print('Active quota fields:')
    for k, v in fields:
        pct = v.get('utilization', 0)
        label = api.field_label(k)
        print(f'  {label:<30} {pct}%  -> {v.get("resets_at", "")}')
    print()
    print('All keys:', list(data.keys()))
