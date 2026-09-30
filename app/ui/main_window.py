from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import TextIO

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.constants import AGENT_LABELS
from app.core.git_manager import GitManager
from app.core.orchestrator_client import OrchestratorClient
from app.core.task_state import StateSnapshot, TaskPhase, final_phase, phase_from_log
from app.models.environment import EnvironmentStatus
from app.models.settings import AppSettings
from app.models.task import AgentTask, utc_now_iso
from app.services.cli_detector import CliDetector
from app.services.history_service import HistoryService
from app.services.settings_service import SettingsService
from app.ui.chat_view import ChatView
from app.ui.git_panel import GitPanel
from app.ui.history_panel import HistoryPanel
from app.ui.log_panel import LogPanel
from app.ui.result_panel import ResultPanel
from app.ui.settings_dialog import SettingsDialog
from app.ui.status_panel import StatusPanel
from app.ui.task_panel import TaskPanel
from app.ui.welcome_dialog import WelcomeDialog
from app.utils.paths import logs_directory

LOGGER = logging.getLogger(__name__)


class _ElidedLabel(QLabel):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.set_full_text(text)

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._update_text()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_text()

    def _update_text(self) -> None:
        displayed = self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, max(1, self.width())
        )
        if self.text() != displayed:
            self.setText(displayed)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Dual Agent Studio")
        self.resize(1200, 800)
        self.setMinimumSize(900, 650)

        self._settings_service = SettingsService()
        self._history_service = HistoryService()
        self.settings = self._settings_service.load()
        self.history = self._history_service.load()
        self.current_task: AgentTask | None = None
        self._log_handle: TextIO | None = None
        self._task_finalized = False
        self._close_after_task = False

        self.client = OrchestratorClient(self.settings.orchestrator_path, self)
        self.git_manager = GitManager(self)
        self.cli_detector = CliDetector(self)

        self._build_ui()
        self._connect_signals()
        self.task_panel.apply_settings(self.settings)
        self.log_panel.auto_scroll.setChecked(self.settings.auto_scroll_logs)
        self.history_panel.set_history(self.history)
        self.status_panel.set_snapshot(StateSnapshot(TaskPhase.IDLE, "空闲"))
        if self.settings.project_path:
            QTimer.singleShot(0, self._refresh_git)
        QTimer.singleShot(0, self._after_show)

    def _build_ui(self) -> None:
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.history_panel = HistoryPanel()
        self.environment_button = self.history_panel.environment_button
        self.splitter.addWidget(self.history_panel)

        center = QWidget()
        center.setMinimumWidth(420)
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("headerBar")
        header.setFixedHeight(48)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)
        header_layout.setSpacing(10)
        self.thread_title = _ElidedLabel("新任务")
        self.thread_title.setObjectName("threadTitle")
        header_layout.addWidget(self.thread_title, 1)
        self.phase_pill = _ElidedLabel("空闲")
        self.phase_pill.setObjectName("phasePill")
        self.phase_pill.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.phase_pill.setMinimumWidth(100)
        self.phase_pill.setMaximumWidth(210)
        header_layout.addWidget(self.phase_pill)
        self.inspector_toggle = QPushButton("详情")
        self.inspector_toggle.setObjectName("toolButton")
        self.inspector_toggle.setCheckable(True)
        header_layout.addWidget(self.inspector_toggle)
        center_layout.addWidget(header)

        self.chat_view = ChatView()
        center_layout.addWidget(self.chat_view, 1)

        composer_host = QWidget()
        composer_layout = QHBoxLayout(composer_host)
        composer_layout.setContentsMargins(24, 0, 24, 16)
        composer_layout.setSpacing(0)
        composer_layout.addStretch(0)
        self.task_panel = TaskPanel()
        self.task_panel.setMaximumWidth(860)
        self.task_panel.setMinimumHeight(280)
        composer_layout.addWidget(self.task_panel, 1)
        composer_layout.addStretch(0)
        center_layout.addWidget(composer_host)
        self.splitter.addWidget(center)

        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(220)
        self.tabs.setMaximumWidth(500)
        self.tabs.tabBar().setUsesScrollButtons(True)
        self.result_panel = ResultPanel()
        self.status_panel = StatusPanel()
        self.log_panel = LogPanel()
        self.git_panel = GitPanel()
        self.json_view = self._create_json_view()
        self.tabs.addTab(self.result_panel, "概要")
        self.tabs.addTab(self.status_panel, "流程")
        self.tabs.addTab(self.git_panel, "Git Diff")
        self.tabs.addTab(self.log_panel, "日志")
        self.tabs.addTab(self.json_view, "JSON")
        self.splitter.addWidget(self.tabs)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setCollapsible(2, True)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([248, 760, 380])
        self.tabs.hide()
        self.setCentralWidget(self.splitter)
        self.statusBar().showMessage("就绪")

    @staticmethod
    def _create_json_view():
        from PySide6.QtWidgets import QPlainTextEdit

        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        view.setPlaceholderText("status --json 的原始结果将在这里显示。")
        return view

    def _connect_signals(self) -> None:
        self.task_panel.browse_requested.connect(self._choose_project)
        self.task_panel.init_requested.connect(self._initialize_project)
        self.task_panel.start_requested.connect(self._start_task)
        self.task_panel.stop_requested.connect(self._stop_task)
        self.task_panel.project_changed.connect(self._on_project_changed)
        self.history_panel.new_task_requested.connect(self._new_task)
        self.history_panel.environment_requested.connect(self._check_environment)
        self.history_panel.settings_requested.connect(self._show_settings)
        self.git_panel.refresh_requested.connect(self._refresh_git)
        self.history_panel.task_selected.connect(self._show_history_task)
        self.inspector_toggle.toggled.connect(self._set_inspector_visible)
        self.chat_view.show_diff_requested.connect(self._show_diff)

        self.client.log_received.connect(self._append_log)
        self.client.task_started.connect(self._on_task_started)
        self.client.phase_changed.connect(self.status_panel.set_snapshot)
        self.client.phase_changed.connect(self.chat_view.set_phase)
        self.client.phase_changed.connect(self._update_phase_pill)
        self.client.status_updated.connect(self._on_status_updated)
        self.client.task_finished.connect(self._on_task_finished)
        self.client.operation_finished.connect(self._on_operation_finished)
        self.client.error_occurred.connect(self._show_client_error)

        self.git_manager.refreshed.connect(self.git_panel.set_content)
        self.git_manager.failed.connect(self.git_panel.set_error)
        self.cli_detector.progress.connect(self.status_panel.set_environment_progress)
        self.cli_detector.finished.connect(self._on_environment_finished)

    def _set_inspector_visible(self, visible: bool) -> None:
        self.tabs.setVisible(visible)
        if visible:
            sidebar_width = self.history_panel.width() or 248
            available = self.splitter.width() - sidebar_width - 2 * self.splitter.handleWidth()
            inspector_width = min(380, max(220, available - 420))
            self.splitter.setSizes(
                [sidebar_width, max(420, available - inspector_width), inspector_width]
            )

    def _show_diff(self) -> None:
        self.inspector_toggle.setChecked(True)
        self.tabs.setCurrentWidget(self.git_panel)

    def _update_phase_pill(self, snapshot: StateSnapshot) -> None:
        self.phase_pill.set_full_text(snapshot.message)

    def _set_thread_title(self, description: str) -> None:
        first_line = description.splitlines()[0].strip() if description else ""
        self.thread_title.set_full_text(first_line or "新任务")

    def _new_task(self) -> None:
        if self.client.running:
            return
        self.chat_view.clear()
        self.result_panel.clear()
        self.log_panel.clear()
        self.json_view.clear()
        self.history_panel.clear_selection()
        self.status_panel.set_snapshot(StateSnapshot(TaskPhase.IDLE, "空闲"))
        self.thread_title.set_full_text("新任务")
        self.phase_pill.set_full_text("空闲")
        self.task_panel.description_edit.setFocus()

    def _after_show(self) -> None:
        if not Path(self.settings.orchestrator_path).is_file():
            dialog = WelcomeDialog(self.settings.orchestrator_path, self)
            if dialog.exec():
                self.settings.orchestrator_path = dialog.orchestrator_path()
                self._settings_service.save(self.settings)
                self.client.set_orchestrator_path(self.settings.orchestrator_path)
        if self.settings.check_environment_on_start:
            self._check_environment()

    def _choose_project(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择 Git 项目",
            self.task_panel.project_path() or str(Path.home()),
        )
        if not selected:
            return
        if not (Path(selected) / ".git").exists():
            answer = QMessageBox.question(
                self,
                "不是 Git 仓库",
                "当前目录似乎不是 Git 仓库。\n\n是否继续使用？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.task_panel.set_project_path(selected)
        self._refresh_git()

    def _on_project_changed(self, project_path: str) -> None:
        self.settings.project_path = project_path
        self._settings_service.save(self.settings)

    def _initialize_project(self) -> None:
        project = self._valid_project_or_warn()
        if not project:
            return
        config = Path(project) / "dual-agent.config.json"
        force = False
        if config.exists():
            answer = QMessageBox.question(
                self,
                "项目已经初始化",
                "dual-agent.config.json 已存在。\n\n是否明确覆盖现有配置？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            force = True
        self.statusBar().showMessage("正在初始化 Dual Agent…")
        self.client.init_project(project, force=force)

    def _start_task(self) -> None:
        project = self._valid_project_or_warn()
        if not project:
            return
        description = self.task_panel.description()
        if not description:
            QMessageBox.warning(self, "缺少任务", "请输入任务描述。")
            return
        if not Path(self.settings.orchestrator_path).is_file():
            QMessageBox.critical(
                self,
                "找不到 Orchestrator",
                "找不到 dual-agent.cmd。\n\n"
                f"当前路径：\n{self.settings.orchestrator_path}\n\n"
                "请在设置中重新选择。",
            )
            return

        self.settings.project_path = project
        self.settings.default_brain = self.task_panel.brain()
        self.settings.default_executor = self.task_panel.executor()
        self.settings.default_max_retries = self.task_panel.max_retries()
        self.settings.auto_detect_roles = self.task_panel.auto_detect_checkbox.isChecked()
        self.settings.auto_scroll_logs = self.log_panel.auto_scroll.isChecked()
        self._settings_service.save(self.settings)

        task = AgentTask(
            description=description,
            project_path=project,
            brain=self.task_panel.brain(),
            executor=self.task_panel.executor(),
            max_retries=self.task_panel.max_retries(),
            status=TaskPhase.RUNNING.value,
            started_at=utc_now_iso(),
        )
        self.current_task = task
        self._task_finalized = False
        self.log_panel.clear()
        self.result_panel.clear()
        self.json_view.clear()
        self._open_log(task)
        self.task_panel.set_running(True)
        starting = StateSnapshot(TaskPhase.RUNNING, "正在启动任务")
        self.status_panel.set_snapshot(starting)
        self._update_phase_pill(starting)
        try:
            self.client.run_task(task)
        except (FileNotFoundError, RuntimeError) as error:
            self.chat_view.clear()
            self.chat_view.add_user_message(description, _task_meta(task))
            self._set_thread_title(description)
            self._append_log("Error", str(error))
            self._finish_without_process(str(error))
            return
        self.chat_view.clear()
        self.chat_view.add_user_message(description, _task_meta(task))
        self._set_thread_title(description)
        self.task_panel.clear_description()

    def _stop_task(self) -> None:
        if not self.client.running:
            return
        answer = QMessageBox.question(
            self,
            "停止任务",
            "确定停止当前任务吗？\n只会终止本次任务创建的进程树。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._append_log("Warning", "用户请求停止当前任务。")
            self.client.cancel_task()

    def _on_task_started(self) -> None:
        self.statusBar().showMessage("任务正在运行")
        self._append_log("System", "Orchestrator 已启动。")

    def _on_status_updated(self, payload: dict[str, object]) -> None:
        self.json_view.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))

    def _on_task_finished(
        self,
        exit_code: int,
        payload: dict[str, object] | None,
        cancelled: bool,
    ) -> None:
        if self._task_finalized or not self.current_task:
            return
        self._task_finalized = True
        task = self.current_task
        phase = final_phase(exit_code, payload, cancelled)
        task.status = phase.value
        task.exit_code = exit_code
        task.finished_at = utc_now_iso()
        task.status_json = payload
        task.result_summary = _final_summary(phase, payload, exit_code)
        final_snapshot = StateSnapshot(phase, task.result_summary)
        self.status_panel.set_snapshot(final_snapshot)
        self.chat_view.set_phase(final_snapshot)
        self._update_phase_pill(final_snapshot)
        self.result_panel.set_task(task, payload)
        if payload:
            self.json_view.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))
        self._append_log(
            "Success" if phase == TaskPhase.PASSED else "Warning" if phase == TaskPhase.CANCELLED else "Error",
            task.result_summary,
        )
        self.chat_view.add_result(task, payload)
        self._close_log()
        self.history = self._history_service.add(task)
        self.history_panel.set_history(self.history)
        self.task_panel.set_running(False)
        self.statusBar().showMessage(task.result_summary)
        if self.tabs.isVisible():
            self.tabs.setCurrentWidget(self.result_panel)
        self._refresh_git()
        self.current_task = None
        if self._close_after_task:
            self._close_after_task = False
            QTimer.singleShot(0, self.close)

    def _finish_without_process(self, message: str) -> None:
        if not self.current_task:
            return
        self._on_task_finished(-1, {"status": "failed", "error": message}, False)

    def _append_log(self, source: str, text: str) -> None:
        self.log_panel.append_line(source, text)
        if source != "System":
            if source == "Process":
                snapshot = phase_from_log(text)
                if snapshot:
                    self.chat_view.set_phase(snapshot)
            self.chat_view.append_log(source, text)
        if self._log_handle:
            self._log_handle.write(f"[{source}] {text}\n")
            self._log_handle.flush()

    def _open_log(self, task: AgentTask) -> None:
        filename = f"{task.started_at[:19].replace(':', '').replace('T', '_')}_{task.id[:8]}.log"
        # The log file is a convenience copy of what the log panel shows.
        # Failing to create it (disk full, permissions) must not abort the
        # task after the UI has already switched into its running state.
        try:
            path = logs_directory() / filename
            self._log_handle = path.open("w", encoding="utf-8")
        except OSError as error:
            LOGGER.warning("Could not create task log file: %s", error)
            self._log_handle = None
            task.log_path = None
            self._append_log("Warning", f"无法创建日志文件，本次日志不会保存到磁盘：{error}")
            return
        task.log_path = str(path)

    def _close_log(self) -> None:
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None

    def _refresh_git(self) -> None:
        project = self.task_panel.project_path()
        if not project or not Path(project).is_dir():
            self.git_panel.set_error("请选择有效项目目录。")
            return
        self.git_manager.refresh(project)

    def _check_environment(self) -> None:
        if self.cli_detector.running:
            return
        self.environment_button.setEnabled(False)
        self.statusBar().showMessage("正在检查环境…")
        self.cli_detector.check(
            self.settings.orchestrator_path,
            self.task_panel.project_path(),
        )

    def _on_environment_finished(self, status: EnvironmentStatus) -> None:
        self.environment_button.setEnabled(True)
        self.status_panel.set_environment(status)
        self.statusBar().showMessage("环境检查完成" if status.ready else "环境检查发现问题")

    def _on_operation_finished(self, name: str, success: bool, output: str) -> None:
        title = "环境检查" if name == "doctor" else "项目初始化"
        if success:
            QMessageBox.information(self, title, output or "操作完成。")
            self._append_log("System", output or f"{name} 完成。")
        else:
            QMessageBox.warning(self, title, output or "操作失败。")
            self._append_log("Error", output or f"{name} 失败。")
        self.statusBar().showMessage("就绪")

    def _show_client_error(self, message: str) -> None:
        LOGGER.error(message)
        self._append_log("Error", message)
        QMessageBox.critical(self, "Dual Agent 错误", message)

    def _show_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if not dialog.exec():
            return
        updated = dialog.settings()
        path_changed = updated.orchestrator_path != self.settings.orchestrator_path
        self.settings = updated
        self.settings.project_path = self.task_panel.project_path()
        self._settings_service.save(self.settings)
        self.task_panel.apply_settings(self.settings)
        self.log_panel.auto_scroll.setChecked(self.settings.auto_scroll_logs)
        if path_changed:
            self.client.set_orchestrator_path(self.settings.orchestrator_path)
        self._check_environment()

    def _show_history_task(self, task: AgentTask) -> None:
        if self.client.running:
            self.history_panel.clear_selection()
            return
        self.chat_view.clear()
        self.chat_view.add_user_message(task.description, _task_meta(task))
        self._set_thread_title(task.description)
        self.phase_pill.set_full_text(task.result_summary or "历史任务")
        self.result_panel.set_task(task, task.status_json)
        self.json_view.setPlainText(
            json.dumps(task.status_json, ensure_ascii=False, indent=2)
            if task.status_json
            else ""
        )
        self.log_panel.clear()
        if task.log_path and Path(task.log_path).is_file():
            try:
                log_text = Path(task.log_path).read_text(encoding="utf-8")
            except OSError as error:
                self.log_panel.set_text(f"无法读取历史日志：{error}")
            else:
                self.log_panel.set_text(log_text)
                for line in log_text.splitlines():
                    parsed = _parse_log_line(line)
                    if parsed is None:
                        continue
                    source, text = parsed
                    if source == "System":
                        continue
                    if source == "Process":
                        snapshot = phase_from_log(text)
                        if snapshot:
                            self.chat_view.set_phase(snapshot)
                    self.chat_view.append_log(source, text)
        self.chat_view.add_result(task, task.status_json)

    def _valid_project_or_warn(self) -> str | None:
        project = self.task_panel.project_path()
        if not project or not Path(project).is_dir():
            QMessageBox.warning(self, "项目目录不存在", "请选择有效的项目目录。")
            return None
        return project

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.client.running:
            answer = QMessageBox.question(
                self,
                "退出应用",
                "任务仍在运行。是否停止本次任务并退出？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._close_after_task = True
            self.client.cancel_task()
            event.ignore()
            return
        self.settings.project_path = self.task_panel.project_path()
        self.settings.auto_scroll_logs = self.log_panel.auto_scroll.isChecked()
        self._settings_service.save(self.settings)
        self._close_log()
        event.accept()


def _task_meta(task: AgentTask) -> str:
    brain = AGENT_LABELS.get(task.brain, task.brain)
    executor = AGENT_LABELS.get(task.executor, task.executor)
    return f"{brain} → {executor} · 最多返工 {task.max_retries} 次"


def _parse_log_line(line: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"\[([^\]\r\n]+)\] (.*)", line.rstrip("\r\n"))
    return (match.group(1), match.group(2)) if match else None


def _final_summary(
    phase: TaskPhase,
    payload: dict[str, object] | None,
    exit_code: int,
) -> str:
    if phase == TaskPhase.PASSED:
        return "任务完成，所有步骤已通过 Brain 验收。"
    if phase == TaskPhase.CANCELLED:
        return "任务已由用户取消。"
    if payload and isinstance(payload.get("error"), str):
        return str(payload["error"])
    if phase == TaskPhase.BLOCKED:
        return "任务已阻塞，未达到最终通过状态。"
    if phase == TaskPhase.UNKNOWN:
        return "进程已结束，但无法确认最终验收状态。"
    return f"任务执行失败，退出码：{exit_code}。"
