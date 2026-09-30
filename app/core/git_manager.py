from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.core.command_builder import CommandSpec
from app.core.process_manager import CapturedProcess


class GitManager(QObject):
    refreshed = Signal(str, str)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: CapturedProcess | None = None
        self._project_path = ""
        self._status = ""
        self._pending_path: str | None = None

    def refresh(self, project_path: str) -> None:
        if self._process and self._process.running:
            # A status/diff round trip is already in flight. Remember only
            # the latest request instead of starting a second process or
            # silently dropping it; the in-flight cycle triggers it once it
            # finishes (see _advance_pending).
            self._pending_path = project_path
            return
        self._pending_path = None
        self._project_path = project_path
        self._start(
            CommandSpec("git", ("-C", project_path, "status", "--short"), project_path),
            self._on_status,
        )

    def _advance_pending(self) -> None:
        if self._pending_path is None:
            return
        path = self._pending_path
        self._pending_path = None
        self.refresh(path)

    def _start(self, command: CommandSpec, callback: object) -> None:
        process = CapturedProcess(self)
        self._process = process
        process.finished.connect(callback)  # type: ignore[arg-type]
        process.start_failed.connect(lambda message: self._on_failure(process, message))
        process.start(command)

    def _on_status(self, exit_code: int, stdout: str, stderr: str) -> None:
        process = self._take_process()
        if process:
            process.deleteLater()
        if exit_code != 0:
            self.failed.emit(stderr.strip() or "无法读取 Git 状态。")
            self._advance_pending()
            return
        self._status = stdout.strip() or "[clean]"
        self._start(
            CommandSpec(
                "git",
                ("-C", self._project_path, "diff", "--no-ext-diff", "--no-color", "HEAD", "--", "."),
                self._project_path,
            ),
            self._on_diff,
        )

    def _on_diff(self, exit_code: int, stdout: str, stderr: str) -> None:
        process = self._take_process()
        if process:
            process.deleteLater()
        if exit_code != 0:
            self.failed.emit(stderr.strip() or "无法读取 Git Diff。")
        else:
            self.refreshed.emit(self._status, stdout.strip() or "[no diff]")
        self._advance_pending()

    def _on_failure(self, process: CapturedProcess, message: str) -> None:
        if self._process is process:
            self._process = None
        process.deleteLater()
        self.failed.emit(f"Git 进程启动失败：{message}")
        self._advance_pending()

    def _take_process(self) -> CapturedProcess | None:
        process = self._process
        self._process = None
        return process

