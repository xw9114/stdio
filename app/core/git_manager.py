from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.core.command_builder import CommandSpec
from app.core.process_manager import CapturedProcess


def is_inside_repository(path: str) -> bool:
    """Whether `path` or one of its parents holds a `.git` entry (a
    directory, or a file for worktrees and submodules). Cheap and
    synchronous, so the UI can ask before starting anything."""
    current = Path(path).resolve()
    return any((candidate / ".git").exists() for candidate in (current, *current.parents))


class GitManager(QObject):
    refreshed = Signal(str, str)
    failed = Signal(str)
    initialized = Signal(bool, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: CapturedProcess | None = None
        self._init_process: CapturedProcess | None = None
        self._project_path = ""
        self._base = "HEAD"
        self._status = ""
        self._pending: tuple[str, str] | None = None

    def init_repository(self, project_path: str) -> None:
        """Run `git init` in `project_path`; `initialized(ok, message)`
        reports the outcome. No commit is made: what goes into the first
        commit is the user's call."""
        if self._init_process and self._init_process.running:
            return
        process = CapturedProcess(self)
        self._init_process = process

        def finish(ok: bool, message: str) -> None:
            if self._init_process is process:
                self._init_process = None
            process.deleteLater()
            self.initialized.emit(ok, message)

        process.finished.connect(
            lambda code, stdout, stderr: finish(
                code == 0, (stdout if code == 0 else stderr or stdout).strip()
            )
        )
        process.start_failed.connect(lambda message: finish(False, f"Git 启动失败：{message}"))
        process.start(CommandSpec("git", ("init",), project_path))

    def refresh(self, project_path: str, base: str = "HEAD") -> None:
        """Show `project_path`'s status and its diff against `base`: HEAD for
        the user's checkout, the run's starting commit for a run worktree
        (whose HEAD already holds the run's own checkpoint commits)."""
        if self._process and self._process.running:
            # A status/diff round trip is already in flight. Remember only
            # the latest request instead of starting a second process or
            # silently dropping it; the in-flight cycle triggers it once it
            # finishes (see _advance_pending).
            self._pending = (project_path, base)
            return
        self._pending = None
        self._project_path = project_path
        self._base = base
        self._start(
            CommandSpec("git", ("-C", project_path, *_READABLE_PATHS, "status", "--short"), project_path),
            self._on_status,
        )

    def _advance_pending(self) -> None:
        if self._pending is None:
            return
        path, base = self._pending
        self._pending = None
        self.refresh(path, base)

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
                ("-C", self._project_path, *_READABLE_PATHS, "diff", "--no-ext-diff", "--no-color", self._base, "--", "."),
                self._project_path,
            ),
            self._on_diff,
        )

    def _on_diff(self, exit_code: int, stdout: str, stderr: str) -> None:
        process = self._take_process()
        if process:
            process.deleteLater()
        if exit_code != 0 and _is_unborn_head(stderr):
            # A freshly initialized repository has no HEAD to diff against;
            # the status above already lists every new file.
            self.refreshed.emit(self._status, "[仓库还没有任何提交，暂无可对比的 Diff；新文件见上方状态]")
        elif exit_code != 0:
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


# Git escapes non-ASCII file names as octal ("\344\270...") by default,
# which turned every Chinese path in the panel into noise.
_READABLE_PATHS = ("-c", "core.quotepath=false")


def _is_unborn_head(stderr: str) -> bool:
    lowered = stderr.lower()
    return "head" in lowered and (
        "bad revision" in lowered or "ambiguous argument" in lowered or "unknown revision" in lowered
    )

