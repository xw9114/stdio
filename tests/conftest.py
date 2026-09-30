from __future__ import annotations

import os
import sys

import pytest


@pytest.fixture(scope="session", autouse=True)
def _shared_qt_application():
    """Some test modules need QtCore only (QCoreApplication) and others need
    real widgets (QApplication). Qt does not allow both types to coexist as
    the global singleton, and whichever test module runs first would
    otherwise decide which one the whole session is stuck with. Creating the
    (widget-capable) QApplication once, here, before any test module's own
    fixture runs, means every later `QCoreApplication.instance() or
    QCoreApplication(...)` call just returns this same instance.
    """
    if os.name != "nt":
        yield None
        return
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        yield None
        return
    app = QApplication.instance() or QApplication(sys.argv)
    yield app
