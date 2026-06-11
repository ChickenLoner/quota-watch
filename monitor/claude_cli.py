"""Discover Claude Code installations on the system."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


def _discover() -> Path:
    found = shutil.which('claude')
    if found:
        p = Path(found)
        if p.suffix.lower() == '.ps1':
            for ext in ('.cmd', '.exe'):
                alt = p.with_suffix(ext)
                if alt.is_file():
                    return alt
        return p

    appdata = os.environ.get('APPDATA')
    if appdata:
        for name in ('claude.cmd', 'claude.exe'):
            c = Path(appdata) / 'npm' / name
            if c.is_file():
                return c

    return Path.home() / '.local' / 'bin' / 'claude.exe'


CLI_PATH = _discover()

_EXT_DIRS: list[tuple[str, Path]] = [
    ('VS Code',         Path.home() / '.vscode'         / 'extensions'),
    ('VS Code Insiders', Path.home() / '.vscode-insiders' / 'extensions'),
    ('Cursor',          Path.home() / '.cursor'         / 'extensions'),
    ('Windsurf',        Path.home() / '.windsurf'        / 'extensions'),
]
_EXT_PREFIX = 'anthropic.claude-code-'
_version_cache: dict[Path, tuple[float, str]] = {}


@dataclass
class Installation:
    name: str
    version: str
    path: Path


def cli_version(path: Path) -> str:
    try:
        mtime = path.stat().st_mtime
        cached = _version_cache.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
        proc = subprocess.run(
            [str(path), '--version'],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        m = re.match(r'(\d+\.\d+\.\d+)', proc.stdout.strip())
        version = m.group(1) if m else ''
        _version_cache[path] = (mtime, version)
        return version
    except Exception:
        return ''


def find_installations() -> list[Installation]:
    results: list[Installation] = []

    if CLI_PATH.is_file():
        v = cli_version(CLI_PATH)
        if v:
            results.append(Installation('CLI', v, CLI_PATH))

    for ide_name, ext_dir in _EXT_DIRS:
        if not ext_dir.is_dir():
            continue
        best_ver, best_parts, best_path = '', (), None
        for entry in ext_dir.iterdir():
            if not entry.name.startswith(_EXT_PREFIX):
                continue
            m = re.match(r'(\d+\.\d+\.\d+)', entry.name[len(_EXT_PREFIX):])
            if m:
                ver = m.group(1)
                parts = tuple(int(x) for x in ver.split('.'))
                if parts > best_parts:
                    best_ver, best_parts, best_path = ver, parts, entry
        if best_ver and best_path:
            results.append(Installation(ide_name, best_ver, best_path))

    return results
