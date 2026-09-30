from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.theme import APPLICATION_STYLE
from app.utils.logging_config import configure_logging


def main() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Dual Agent Studio")
    app.setOrganizationName("Dual Agent Studio")
    app.setStyleSheet(APPLICATION_STYLE)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

