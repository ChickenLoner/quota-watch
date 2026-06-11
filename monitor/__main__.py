"""Entry point: suppress console, set DPI, start webview loop, run app in background."""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import traceback

# Hide console window in dev mode (EXE build uses console=False in PyInstaller spec)
if not getattr(sys, 'frozen', False):
    ctypes.windll.kernel32.FreeConsole()

# Per-Monitor V2 DPI — must be set before pywebview loads SetProcessDPIAware
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_ssize_t(-4))

import webview  # type: ignore[import-untyped]  # noqa: E402

from monitor.app import App  # noqa: E402

_result: dict = {}


def _run_app() -> None:
    """Run the tray app in webview's background thread."""
    try:
        app = App()
        _result['app'] = app
        app.run()
    except Exception:
        ctypes.windll.user32.MessageBoxW(
            0, traceback.format_exc()[:2000],
            'SOC Monitor - Error', 0x10,
        )
    finally:
        for win in list(webview.windows):
            try:
                win.destroy()
            except Exception:
                pass


def main() -> None:
    webview.create_window('', html='', hidden=True)
    webview.start(func=_run_app)

    app = _result.get('app')
    if app and app.restart_requested:
        if getattr(sys, 'frozen', False):
            env = {k: v for k, v in os.environ.items() if not k.startswith(('_PYI_', '_MEI'))}
            subprocess.Popen([sys.executable], env=env, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen(
                [sys.executable, '-m', 'monitor'],
                cwd=str(__file__.replace('\\monitor\\__main__.py', '')),
                creationflags=subprocess.CREATE_NO_WINDOW,
            )


if __name__ == '__main__':
    main()
