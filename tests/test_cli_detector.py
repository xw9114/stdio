from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from app.services.cli_detector import CliDetector
from qt_helpers import run_event_loop

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows-specific process launch behaviour")


def test_doctor_runs_when_the_orchestrator_is_a_node_forwarder(tmp_path: Path) -> None:
    """Regression: the builder launches dual-agent.cmd's one-line forwarder
    as `node cli.ts`, and the detector checked that "node" was a file, so
    doctor was always reported missing."""
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    script = tmp_path / "src" / "cli.ts"
    script.parent.mkdir()
    script.write_text('console.log("Workspace: ok");\n', encoding="utf-8")
    wrapper = tmp_path / "dual-agent.cmd"
    wrapper.write_text('@echo off\r\nnode "%~dp0src\cli.ts" %*\r\n', encoding="utf-8")

    results = {}
    detector = CliDetector()
    detector.progress.connect(lambda key, check: results.__setitem__(key, check))
    detector.finished.connect(lambda _status: app.quit())
    detector.check(str(wrapper), str(tmp_path), "claude", "codex")
    run_event_loop(app, 120_000)

    assert results["doctor"].available, results["doctor"].detail
    assert "Workspace: ok" in results["doctor"].detail
