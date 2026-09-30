from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.theme import APPLICATION_STYLE
from app.utils.logging_config import configure_logging


def main() -> int:
    configure_logging()
    # Must be set before QApplication is constructed. Without it, Qt's
    # default DPI-scale rounding can miscompute layouts when a window moves
    # between monitors with different scale factors (or is resized smaller
    # than the scale factor it was originally laid out for), producing
    # overlapping widgets instead of a clean re-layout - reported behavior:
    # the UI only renders correctly on one external monitor and overlaps
    # once the window shrinks or moves to a differently-scaled display.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Dual Agent Studio")
    app.setOrganizationName("Dual Agent Studio")
    app.setStyleSheet(APPLICATION_STYLE)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

