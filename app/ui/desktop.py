"""Operating system touches: notifications, staying awake, opening folders
and editors. Kept apart from the windows so tests can replace them."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget

LOGGER = logging.getLogger(__name__)

# SetThreadExecutionState flags (winbase.h).
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


class Notifier:
    """Tells the user a task ended when Studio is not the active window: a
    tray balloon (a Windows toast) and a flashing taskbar button."""

    def __init__(self, window: QWidget) -> None:
        self._window = window
        self._tray: QSystemTrayIcon | None = None

    def notify(self, title: str, message: str) -> bool:
        """Returns whether the user was notified (False while Studio is in front)."""
        if self._window.isActiveWindow():
            return False
        QApplication.alert(self._window)
        if QSystemTrayIcon.isSystemTrayAvailable():
            if self._tray is None:
                icon = self._window.windowIcon()
                if icon.isNull():
                    icon = QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_ComputerIcon)
                self._tray = QSystemTrayIcon(QIcon(icon), self._window)
                self._tray.setToolTip("Dual Agent Studio")
                # A click on the balloon brings the window back.
                self._tray.messageClicked.connect(self._bring_back)
            self._tray.show()
            self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 8000)
        return True

    def _bring_back(self) -> None:
        self._window.showNormal()
        self._window.raise_()
        self._window.activateWindow()


def keep_awake(on: bool) -> None:
    """Keeps Windows from sleeping while a task runs, or lets it sleep again.
    The display may still turn off. No-op elsewhere."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        flags = _ES_CONTINUOUS | (_ES_SYSTEM_REQUIRED if on else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except (AttributeError, OSError) as error:
        LOGGER.warning("Could not change the sleep setting: %s", error)


def open_folder(path: str) -> bool:
    if not path or not Path(path).is_dir():
        return False
    return QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def find_editor() -> str | None:
    """VS Code's command, if it is installed and on PATH."""
    return shutil.which("code")


def open_in_editor(path: str) -> bool:
    editor = find_editor()
    if editor is None or not Path(path).is_dir():
        return False
    try:
        # code.cmd is a batch file: run it through cmd without a console.
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen([editor, path], creationflags=flags, env=os.environ.copy())
    except OSError as error:
        LOGGER.warning("Could not open %s in the editor: %s", path, error)
        return False
    return True
