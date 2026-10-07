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


@pytest.fixture(autouse=True)
def _isolated_api_settings(tmp_path_factory, monkeypatch):
    """Keeps the developer's real .env and API profiles out of every test:
    commands read .env at each launch."""
    import app.services.provider_service as provider_service

    directory = tmp_path_factory.mktemp("api")
    monkeypatch.setattr(provider_service, "env_path", lambda: directory / ".env")
    monkeypatch.setattr(provider_service, "providers_path", lambda: directory / "providers.json")
    return directory
