"""Windows autostart via HKCU Run registry key."""
from __future__ import annotations

import sys
import winreg

_REG_KEY  = r'Software\Microsoft\Windows\CurrentVersion\Run'
_REG_NAME = 'SocClaudeMonitor'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY) as key:
            winreg.QueryValueEx(key, _REG_NAME)
            return True
    except FileNotFoundError:
        return False


def set_enabled(enable: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enable:
            winreg.SetValueEx(key, _REG_NAME, 0, winreg.REG_SZ, f'"{sys.executable}"')
        else:
            try:
                winreg.DeleteValue(key, _REG_NAME)
            except FileNotFoundError:
                pass


def sync_path() -> None:
    """Update registry path if EXE was moved."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY) as key:
            stored, _ = winreg.QueryValueEx(key, _REG_NAME)
    except FileNotFoundError:
        return
    if stored != f'"{sys.executable}"':
        set_enabled(True)
