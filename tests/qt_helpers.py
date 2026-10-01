from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QTimer


def run_event_loop(app: QCoreApplication, timeout_ms: int) -> None:
    """Run `app`'s event loop until something quits it, or `timeout_ms`.

    Never use `QTimer.singleShot(timeout_ms, app.quit)` as the safety net:
    that timer cannot be cancelled, so it fires during whichever test runs
    next and quits that test's loop early - which made unrelated tests fail
    at random with "never finished". This timer is stopped on the way out.
    """
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(app.quit)
    timer.start(timeout_ms)
    try:
        app.exec()
    finally:
        timer.stop()
