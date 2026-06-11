import sys
sys.path.insert(0, r'G:\Poc\soc-claude-monitor')

print('Testing imports...')
from monitor import __version__
print(f'  version: {__version__}')

from monitor.api import read_token, fetch_usage, fetch_profile, quota_fields, field_label
print('  api: OK')

from monitor.tray import create_icon, create_status_icon, taskbar_is_light
print('  tray: OK')

# Test icon rendering
icon = create_icon(37, 17)
print(f'  icon rendered: {icon.size}')

icon_err = create_status_icon('!')
print(f'  status icon rendered: {icon_err.size}')

print()
print('All imports OK')
print(f'taskbar light: {taskbar_is_light()}')
