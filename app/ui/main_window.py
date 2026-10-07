from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.constants import AGENT_LABELS, RUN_MODE_LABELS
from app.core.git_manager import GitManager, is_inside_repository
from app.core.orchestrator_client import OrchestratorClient
from app.core.task_state import (
    StateSnapshot,
    TaskPhase,
    active_isolation,
    final_phase,
    phase_from_log,
    resumable_run_id,
)
from app.models.environment import EnvironmentStatus
from app.models.settings import AppSettings
from app.models.task import AgentTask, utc_now_iso
from app.services.cli_detector import CliDetector
from app.services.history_service import HistoryService
from app.services.provider_service import TOOLS, TOOL_LABELS, ProviderService
from app.services.settings_service import SettingsService
from app.ui.chat_view import ChatView
from app.ui.git_panel import GitPanel
from app.ui.history_panel import HistoryPanel
from app.ui.log_panel import LogPanel
from app.ui.provider_dialog import ProviderDialog
from app.ui.result_panel import ResultPanel
from app.ui.settings_dialog import SettingsDialog
from app.ui.status_panel import StatusPanel
from app.ui.task_panel import TaskPanel
from app.ui.theme import application_style
from app.ui.wallpaper import IMAGE_FILTER, PRESETS, WallpaperCanvas, is_preset, load_wallpaper, preset_value
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
        # The plan-only run whose plan card is on screen awaiting a decision.
        self._plan_source: AgentTask | None = None
        # What to do once a `git init` offered by _ensure_repository succeeds.
        self._after_git_init: Callable[[], None] | None = None
        # The orchestrator's own last error line of the current process; the
        # only explanation when it fails before writing any run state.
        self._last_orchestrator_error: str | None = None
        # The worktree of the run shown in the chat, while not yet applied.
        self._shown_isolation: dict[str, str] | None = None
        # The task and action ("apply"/"discard") of an operation in flight.
        self._settling: tuple[AgentTask, str] | None = None

        self.client = OrchestratorClient(self.settings.orchestrator_path, self)
        self.git_manager = GitManager(self)
        self.cli_detector = CliDetector(self)

        self._build_ui()
        self._connect_signals()
        self.task_panel.apply_settings(self.settings)
        self.history_panel.set_workspace(self.settings.project_path)
        self._apply_appearance()
        self._set_home_layout(self.chat_view.is_empty())
        self.log_panel.auto_scroll.setChecked(self.settings.auto_scroll_logs)
        self.history_panel.set_history(self.history)
        self.status_panel.set_snapshot(StateSnapshot(TaskPhase.IDLE, "空闲"))
        self._update_phase_pill(StateSnapshot(TaskPhase.IDLE, "空闲"))
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
        self.header_bar = header
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
        # 16 here plus the panel's own 16 lines the composer up with the chat
        # column; the panel's margin holds the composer's shadow.
        composer_layout.setContentsMargins(16, 0, 16, 0)
        composer_layout.setSpacing(0)
        composer_layout.addStretch(0)
        self.task_panel = TaskPanel()
        # Matches the chat column (760px plus the panel's own margins).
        self.task_panel.setMaximumWidth(792)
        self.task_panel.setMinimumHeight(140)
        composer_layout.addWidget(self.task_panel, 1)
        composer_layout.addStretch(0)
        center_layout.addWidget(composer_host)
        # On the home screen this takes the same share of height as the chat
        # area above, which puts the title and the composer mid-window.
        self._home_spacer = QWidget()
        center_layout.addWidget(self._home_spacer, 1)
        self.splitter.addWidget(center)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("inspector")
        # Paints its own (frosted) background over a wallpaper.
        self.tabs.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
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
        # Everything sits on the wallpaper canvas, which paints the backdrop.
        self.canvas = WallpaperCanvas()
        canvas_layout = QVBoxLayout(self.canvas)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.addWidget(self.splitter)
        self.setCentralWidget(self.canvas)
        self._build_wallpaper_menu()
        # The status bar appears only while it has something to say, so the
        # sidebar and chat reach the bottom edge the rest of the time.
        status_bar = self.statusBar()
        status_bar.setSizeGripEnabled(False)
        status_bar.messageChanged.connect(lambda message: status_bar.setVisible(bool(message)))
        status_bar.hide()

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
        self.history_panel.providers_requested.connect(self._show_providers)
        self.git_panel.refresh_requested.connect(self._refresh_git)
        self.history_panel.task_selected.connect(self._show_history_task)
        self.inspector_toggle.toggled.connect(self._set_inspector_visible)
        self.chat_view.show_diff_requested.connect(self._show_diff)
        self.chat_view.resume_requested.connect(self._resume_run)
        self.chat_view.plan_approved.connect(self._approve_plan)
        self.chat_view.plan_replan_requested.connect(self._replan)
        self.chat_view.plan_discarded.connect(self._discard_plan)
        self.chat_view.empty_changed.connect(self._set_home_layout)
        self.chat_view.apply_requested.connect(self._apply_run)
        self.chat_view.discard_requested.connect(self._discard_run)

        self.client.log_received.connect(self._append_log)
        self.client.task_started.connect(self._on_task_started)
        # Only the inspector's workflow panel follows phase_changed, because
        # that signal also carries the 3-second `status --json` poll. The poll
        # can lag behind the log or report between-task states the log never
        # prints, and each such snapshot opened a duplicate step card. Chat
        # cards and the header pill are driven by log lines (_feed_chat).
        self.client.phase_changed.connect(self.status_panel.set_snapshot)
        self.client.status_updated.connect(self._on_status_updated)
        self.client.task_finished.connect(self._on_task_finished)
        self.client.operation_finished.connect(self._on_operation_finished)
        self.client.error_occurred.connect(self._show_client_error)

        self.git_manager.refreshed.connect(self.git_panel.set_content)
        self.git_manager.failed.connect(self.git_panel.set_error)
        self.git_manager.initialized.connect(self._on_git_initialized)
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
        # An "空闲" badge on an empty screen says nothing; show it only when
        # there is a run (or its outcome) to describe.
        self.phase_pill.setVisible(snapshot.message != "空闲")

    def _build_wallpaper_menu(self) -> None:
        menu = QMenu(self)
        self._wallpaper_actions = QActionGroup(menu)
        self._wallpaper_actions.setExclusive(True)
        choices = [("无壁纸", "")] + [(f"渐变 · {preset.label}", preset_value(preset.key)) for preset in PRESETS]
        for label, value in choices:
            action = QAction(label, menu, checkable=True)
            action.setData(value)
            action.triggered.connect(lambda _checked=False, chosen=value: self._set_wallpaper(chosen))
            self._wallpaper_actions.addAction(action)
            menu.addAction(action)
        # The current image, when one is set; filled in when the menu opens.
        self._image_action = QAction("", menu, checkable=True)
        self._image_action.triggered.connect(lambda _checked=False: self._set_wallpaper(self.settings.wallpaper))
        self._wallpaper_actions.addAction(self._image_action)
        menu.addAction(self._image_action)
        menu.addSeparator()
        menu.addAction("选择本地图片…", self._choose_wallpaper_image)
        menu.addAction("调整模糊和遮罩…", self._show_settings)
        menu.aboutToShow.connect(self._refresh_wallpaper_menu)
        self.history_panel.wallpaper_button.setMenu(menu)

    def _refresh_wallpaper_menu(self) -> None:
        current = self.settings.wallpaper
        image = bool(current) and not is_preset(current)
        self._image_action.setVisible(image)
        if image:
            self._image_action.setText(f"图片 · {Path(current).name}")
        for action in self._wallpaper_actions.actions():
            action.setChecked(action is self._image_action if image else action.data() == current)

    def _choose_wallpaper_image(self) -> None:
        current = self.settings.wallpaper
        start = str(Path(current).parent) if current and not is_preset(current) else str(Path.home() / "Pictures")
        filename, _selected = QFileDialog.getOpenFileName(self, "选择壁纸图片", start, IMAGE_FILTER)
        if filename:
            self._set_wallpaper(filename)

    def _set_wallpaper(self, wallpaper: str) -> None:
        self.settings.wallpaper = wallpaper
        self._settings_service.save(self.settings)
        self._apply_appearance()

    def _apply_appearance(
        self, wallpaper: str | None = None, blur: int | None = None, veil: int | None = None
    ) -> None:
        """Shows the saved wallpaper, or a preview of the given values."""
        wallpaper = self.settings.wallpaper if wallpaper is None else wallpaper
        image = load_wallpaper(
            wallpaper, self.settings.wallpaper_blur if blur is None else blur
        )
        if wallpaper and image is None and not is_preset(wallpaper):
            self._notify(f"无法打开壁纸图片：{wallpaper}")
        self.canvas.set_wallpaper(image, self.settings.wallpaper_veil if veil is None else veil)
        # Panels turn translucent only when there is something behind them.
        app = QApplication.instance()
        style = application_style(glass=image is not None)
        if isinstance(app, QApplication) and app.styleSheet() != style:
            app.setStyleSheet(style)

    def _notify(self, message: str, timeout_ms: int = 8000) -> None:
        # Transient: progress and outcomes stay in the chat and the inspector.
        self.statusBar().showMessage(message, timeout_ms)

    def _set_home_layout(self, home: bool) -> None:
        # The home screen has no thread yet: no header, composer centred.
        self.header_bar.setVisible(not home)
        self._home_spacer.setVisible(home)

    def _set_thread_title(self, description: str) -> None:
        first_line = description.splitlines()[0].strip() if description else ""
        self.thread_title.set_full_text(first_line or "新任务")

    def _new_task(self) -> None:
        if self.client.running:
            return
        self.chat_view.clear()
        self._shown_isolation = None
        self.result_panel.clear()
        self.log_panel.clear()
        self.json_view.clear()
        self.history_panel.clear_selection()
        self.status_panel.set_snapshot(StateSnapshot(TaskPhase.IDLE, "空闲"))
        self.thread_title.set_full_text("新任务")
        self._update_phase_pill(StateSnapshot(TaskPhase.IDLE, "空闲"))
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
        self.history_panel.set_workspace(project_path)
        self.settings.project_path = project_path
        self._settings_service.save(self.settings)

    def _ensure_repository(self, project: str, then: Callable[[], None]) -> bool:
        """Offer `git init` when `project` is not inside a Git repository.

        The orchestrator refuses non-Git workspaces (unless its config sets
        safety.allowNonGit) because Git is how the Executor's edits are
        tracked and reviewed; without this the user only saw "退出码 1".
        Returns True when the caller may continue right away; otherwise
        `then` runs once `git init` succeeds, or never if the user cancels."""
        if is_inside_repository(project):
            return True
        answer = QMessageBox.question(
            self,
            "不是 Git 仓库",
            f"{project}\n不在任何 Git 仓库中。Dual Agent 用 Git 跟踪 Executor 的修改，"
            "非 Git 目录会被拒绝运行。\n\n"
            "是否先在这里执行 git init？（不会自动提交任何文件）\n"
            "选“否”则不初始化直接继续（仅适用于配置了 safety.allowNonGit 的项目）。",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.No:
            return True
        if answer == QMessageBox.StandardButton.Yes:
            self._after_git_init = then
            self._notify("正在执行 git init…")
            self.git_manager.init_repository(project)
        return False

    def _on_git_initialized(self, ok: bool, message: str) -> None:
        then, self._after_git_init = self._after_git_init, None
        if not ok:
            QMessageBox.warning(self, "git init 失败", message or "git init 失败。")
            self._notify("git init 失败")
            return
        self._append_log("System", message or "已初始化 Git 仓库。")
        self._notify("已初始化 Git 仓库")
        self._refresh_git()
        if then is not None:
            then()

    def _initialize_project(self, *, repository_checked: bool = False) -> None:
        project = self._valid_project_or_warn()
        if not project:
            return
        if not repository_checked and not self._ensure_repository(
            project, lambda: self._initialize_project(repository_checked=True)
        ):
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
        self._notify("正在初始化 Dual Agent…")
        self.client.init_project(project, force=force)

    def _start_task(self, *, repository_checked: bool = False) -> None:
        project = self._valid_project_or_warn()
        if not project:
            return
        description = self.task_panel.description()
        if not description:
            QMessageBox.warning(self, "缺少任务", "请输入任务描述。")
            return
        if not repository_checked and not self._ensure_repository(
            project, lambda: self._start_task(repository_checked=True)
        ):
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
        self.settings.confirm_plan = self.task_panel.confirm_plan_checkbox.isChecked()
        self.settings.run_mode = self.task_panel.mode()
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
            mode=self.task_panel.mode(),
        )
        plan_only = self.task_panel.confirm_plan()
        meta = _task_meta(task) + (" · 先确认计划" if plan_only else "")
        if self._launch(
            task,
            lambda: self.client.run_task(task, plan_only=plan_only),
            message=description,
            meta=meta,
            new_conversation=True,
        ):
            self.task_panel.clear_description()

    def _launch(
        self,
        task: AgentTask,
        start: Callable[[], None],
        *,
        message: str,
        meta: str,
        new_conversation: bool,
    ) -> bool:
        """Start one orchestrator process for `task` and show it in the chat.

        A new conversation replaces what the chat shows; a follow-up (plan
        approval, re-plan, resume) is appended to it so the user sees the
        plan or blocked result it continues from. Returns whether the
        process was started."""
        self.current_task = task
        self._task_finalized = False
        self._last_orchestrator_error = None
        self.log_panel.clear()
        self.result_panel.clear()
        self.json_view.clear()
        self._open_log(task)
        self.task_panel.set_running(True)
        starting = StateSnapshot(TaskPhase.RUNNING, "正在启动任务")
        self.status_panel.set_snapshot(starting)
        self._update_phase_pill(starting)
        if new_conversation:
            self.chat_view.clear()
            self._shown_isolation = None
            self._set_thread_title(task.description)
        self.chat_view.add_user_message(message, meta)
        try:
            start()
        except (FileNotFoundError, RuntimeError) as error:
            self._append_log("Error", str(error))
            self._finish_without_process(str(error))
            return False
        return True

    def _follow_up_task(self, source: AgentTask, description: str | None = None) -> AgentTask:
        # Same agents as the run being continued: stored session ids belong
        # to those providers, whatever the composer currently selects.
        return AgentTask(
            description=description or source.description,
            project_path=source.project_path,
            brain=source.brain,
            executor=source.executor,
            max_retries=source.max_retries,
            status=TaskPhase.RUNNING.value,
            started_at=utc_now_iso(),
            mode=source.mode,
        )

    def _close_source(self, source: AgentTask, status: str) -> None:
        # The entry a plan was approved, replanned, resumed or discarded from
        # otherwise kept its "awaiting approval" (or stopped) state and stood
        # in the sidebar as if it still needed attention.
        source.status = status
        self.history = self._history_service.update(source)
        self.history_panel.set_history(self.history)

    def _busy(self) -> bool:
        if self.client.running:
            QMessageBox.information(self, "任务进行中", "请等当前任务结束后再继续。")
            return True
        return False

    def _approve_plan(self, skip: list[str], note: str) -> None:
        source = self._plan_source
        run_id = resumable_run_id(source.status_json) if source else None
        if source is None or run_id is None or self._busy():
            return
        self._plan_source = None
        self._close_source(source, "continued")
        task = self._follow_up_task(source)
        meta = "开始执行计划" + (f" · 跳过 {', '.join(skip)}" if skip else "")
        self._launch(
            task,
            lambda: self.client.resume_task(task, run_id, skip=skip, note=note),
            message=note or "按计划开始执行",
            meta=meta,
            new_conversation=False,
        )

    def _replan(self, note: str) -> None:
        source = self._plan_source
        if source is None or self._busy():
            return
        self._plan_source = None
        self._close_source(source, "continued")
        task = self._follow_up_task(source, f"{source.description}\n\n补充说明：\n{note}")
        self._launch(
            task,
            lambda: self.client.run_task(task, plan_only=True),
            message=note,
            meta="按补充说明重新规划",
            new_conversation=False,
        )

    def _discard_plan(self) -> None:
        if self._plan_source is not None:
            self._close_source(self._plan_source, "discarded")
        self._plan_source = None
        self._update_phase_pill(StateSnapshot(TaskPhase.IDLE, "计划已放弃"))
        self._notify("计划已放弃，代码未做任何修改。")

    def _resume_run(self, source: AgentTask) -> None:
        run_id = resumable_run_id(source.status_json)
        if run_id is None or self._busy():
            return
        note, accepted = QInputDialog.getMultiLineText(
            self,
            "继续执行",
            "已完成的任务会保留，从中断的任务接着执行。\n补充说明（可选，会交给 Brain 和 Executor）：",
        )
        if not accepted:
            return
        self._close_source(source, "continued")
        task = self._follow_up_task(source)
        self._launch(
            task,
            lambda: self.client.resume_task(task, run_id, note=note),
            message=note.strip() or "继续执行",
            meta="从中断处继续",
            new_conversation=False,
        )

    def _show_outcome(self, task: AgentTask, payload: dict[str, object] | None) -> None:
        """End of a run in the chat: a plan awaiting approval gets the plan
        card, anything else the result card (with "继续执行" when the run
        stopped short and can be resumed)."""
        self._shown_isolation = None
        plan = payload.get("plan") if payload else None
        if task.status == TaskPhase.AWAITING_APPROVAL and isinstance(plan, dict):
            self._plan_source = task
            self.chat_view.add_plan(plan)
            return
        # A continued entry was already taken up again in a newer entry.
        resumable = (
            task.status not in {TaskPhase.PASSED, "continued", "discarded"}
            and resumable_run_id(payload) is not None
        )
        isolation = active_isolation(payload)
        self._shown_isolation = isolation
        self.chat_view.add_result(task, payload, resumable=resumable, isolation=isolation)

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
        self._notify("任务正在运行")
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
        task.result_summary = _final_summary(
            phase, payload, exit_code, self._last_orchestrator_error
        )
        final_snapshot = StateSnapshot(phase, task.result_summary)
        self.status_panel.set_snapshot(final_snapshot)
        self.chat_view.set_phase(final_snapshot)
        self._update_phase_pill(final_snapshot)
        self.result_panel.set_task(task, payload)
        if payload:
            self.json_view.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))
        self._append_log(
            "Success"
            if phase in {TaskPhase.PASSED, TaskPhase.AWAITING_APPROVAL}
            else "Warning" if phase == TaskPhase.CANCELLED else "Error",
            task.result_summary,
        )
        self._show_outcome(task, payload)
        self._close_log()
        self.history = self._history_service.add(task)
        self.history_panel.set_history(self.history)
        self.task_panel.set_running(False)
        self._notify(task.result_summary)
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
        if source == "Error" and text.lstrip().startswith(_ORCHESTRATOR_PREFIX):
            self._last_orchestrator_error = text.lstrip()[len(_ORCHESTRATOR_PREFIX):].strip()
        # Messages logged while no task runs (init/doctor results, client
        # errors) are not part of the conversation on screen, which may be a
        # replayed history task.
        if self.current_task is not None:
            self._feed_chat(source, text)
            if "hit a usage limit" in text and "Continuing this run with" in text:
                # The orchestrator switched the Brain after Claude's usage
                # limit; say so plainly instead of leaving it in a step log.
                self._notify("Brain 的额度用完了，本次任务已自动改用 Codex 作为 Brain 继续。", 60_000)
        if self._log_handle:
            self._log_handle.write(f"[{source}] {text}\n")
            self._log_handle.flush()

    def _feed_chat(self, source: str, text: str) -> None:
        """Route one log line into the chat: phase lines open step cards and
        update the header pill, everything except System lines is appended
        to the active card. Shared by live runs and history replay so both
        render the same conversation."""
        if source == "System":
            return
        if source == "Process":
            snapshot = phase_from_log(text)
            if snapshot:
                self.chat_view.set_phase(snapshot)
                self._update_phase_pill(snapshot)
        self.chat_view.append_log(source, text)

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
        # While the shown run's changes sit on their own branch, the diff
        # worth showing is that worktree against the run's starting point;
        # the checkout itself has not changed.
        isolation = self._shown_isolation
        if isolation and Path(isolation["path"]).is_dir():
            self.git_manager.refresh(isolation["path"], isolation["base"])
            return
        project = self.task_panel.project_path()
        if not project or not Path(project).is_dir():
            self.git_panel.set_error("请选择有效项目目录。")
            return
        self.git_manager.refresh(project)

    def _check_environment(self) -> None:
        if self.cli_detector.running:
            return
        self.environment_button.setEnabled(False)
        self._notify("正在检查环境…")
        self.cli_detector.check(
            self.settings.orchestrator_path,
            self.task_panel.project_path(),
            self.task_panel.brain(),
            self.task_panel.executor(),
        )

    def _on_environment_finished(self, status: EnvironmentStatus) -> None:
        self.environment_button.setEnabled(True)
        self.status_panel.set_environment(status)
        self._notify("环境检查完成" if status.ready else "环境检查发现问题")

    def _apply_run(self, task: AgentTask) -> None:
        self._settle_run(task, "apply")

    def _discard_run(self, task: AgentTask) -> None:
        self._settle_run(task, "discard")

    def _settle_run(self, task: AgentTask, action: str) -> None:
        """Apply an isolated run's branch to the checkout, or throw it away."""
        isolation = active_isolation(task.status_json)
        run_id = task.status_json.get("runId") if task.status_json else None
        if isolation is None or not isinstance(run_id, str) or self._busy():
            return
        if action == "apply":
            question = (
                f"把分支 {isolation['branch']} 上的改动应用到你的工作区？\n\n"
                "如果你在运行期间改过同样的地方，会用三方合并处理，可能需要你解决冲突。"
            )
        else:
            question = f"丢弃分支 {isolation['branch']} 上的全部改动？\n\n删除后无法恢复。"
        answer = QMessageBox.question(
            self,
            "应用到工作区" if action == "apply" else "丢弃改动",
            question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._settling = (task, action)
        self._notify("正在应用改动…" if action == "apply" else "正在丢弃改动…")
        if action == "apply":
            self.client.apply_run(task.project_path, run_id)
        else:
            self.client.discard_run(task.project_path, run_id)

    def _on_settled(self, success: bool, output: str) -> None:
        task, action = self._settling or (None, "")
        self._settling = None
        if task is None:
            return
        if not success:
            QMessageBox.warning(self, "操作失败", output or "操作失败。")
            self._append_log("Error", output or f"{action} 失败。")
            return
        # Record the outcome in the task's stored status so history replays
        # no longer offer to apply or discard it.
        state = "applied" if action == "apply" else "discarded"
        if task.status_json and isinstance(task.status_json.get("isolation"), dict):
            task.status_json["isolation"]["state"] = state
            self.history = self._history_service.add(task)
            self.history_panel.set_history(self.history)
        conflicts = "conflict" in output.lower()
        outcome = (
            "改动已应用到你的工作区，但有冲突需要你手动解决。"
            if conflicts
            else "改动已应用到你的工作区。" if action == "apply" else "改动已丢弃，工作区未受影响。"
        )
        self.chat_view.settle_isolation(task.id, outcome)
        self._shown_isolation = None
        self._append_log("System", output or outcome)
        self._notify(outcome)
        if conflicts:
            QMessageBox.warning(self, "需要解决冲突", output)
        self._refresh_git()

    def _on_operation_finished(self, name: str, success: bool, output: str) -> None:
        if name in {"apply", "discard"}:
            self._on_settled(success, output)
            return
        title = "环境检查" if name == "doctor" else "项目初始化"
        if success:
            QMessageBox.information(self, title, output or "操作完成。")
            self._append_log("System", output or f"{name} 完成。")
        else:
            QMessageBox.warning(self, title, output or "操作失败。")
            self._append_log("Error", output or f"{name} 失败。")
        self.statusBar().clearMessage()

    def _show_client_error(self, message: str) -> None:
        LOGGER.error(message)
        self._append_log("Error", message)
        QMessageBox.critical(self, "Dual Agent 错误", message)

    def _show_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self, preview=self._apply_appearance)
        if not dialog.exec():
            self._apply_appearance()  # undo the dialog's live preview
            return
        updated = dialog.settings()
        path_changed = updated.orchestrator_path != self.settings.orchestrator_path
        self.settings = updated
        self.settings.project_path = self.task_panel.project_path()
        self._settings_service.save(self.settings)
        self.task_panel.apply_settings(self.settings)
        self.history_panel.set_workspace(self.settings.project_path)
        self.log_panel.auto_scroll.setChecked(self.settings.auto_scroll_logs)
        self._apply_appearance()
        if path_changed:
            self.client.set_orchestrator_path(self.settings.orchestrator_path)
        self._check_environment()

    def _show_providers(self) -> None:
        dialog = ProviderDialog(ProviderService(), self)
        dialog.exec()
        state = dialog.state
        summary = "，".join(
            f"{TOOL_LABELS[tool]}：{profile.name if (profile := state.active_profile(tool)) else '官方登录'}"
            for tool in TOOLS
        )
        self.statusBar().showMessage(f"API 配置已更新（{summary}），下次运行生效。", 6000)
        self._check_environment()

    def _show_history_task(self, task: AgentTask) -> None:
        if self.client.running:
            self.history_panel.clear_selection()
            return
        self.chat_view.clear()
        self.chat_view.add_user_message(task.description, _task_meta(task))
        self._set_thread_title(task.description)
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
                    self._feed_chat(*parsed)
        self.phase_pill.set_full_text(task.result_summary or "历史任务")
        self._show_outcome(task, task.status_json)

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
    executor = AGENT_LABELS.get(task.executor, task.executor)
    if task.mode == "single":
        return f"单 agent · {executor} · 不规划、不验收"
    brain = AGENT_LABELS.get(task.brain, task.brain)
    mode = RUN_MODE_LABELS.get(task.mode, task.mode)
    return f"{brain} → {executor} · {mode} · 最多返工 {task.max_retries} 次"


def _parse_log_line(line: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"\[([^\]\r\n]+)\] (.*)", line.rstrip("\r\n"))
    return (match.group(1), match.group(2)) if match else None


_ORCHESTRATOR_PREFIX = "[dual-agent] "


def _final_summary(
    phase: TaskPhase,
    payload: dict[str, object] | None,
    exit_code: int,
    orchestrator_error: str | None = None,
) -> str:
    if phase == TaskPhase.PASSED and payload and payload.get("mode") == "single":
        return "Executor 已完成任务（单 agent 模式，未经 Brain 验收）。"
    if phase == TaskPhase.PASSED and payload and payload.get("route") == "direct":
        return "Executor 已完成任务（Brain 判断为小改动，直接执行，未经验收）。"
    if phase == TaskPhase.PASSED:
        return "任务完成，所有步骤已通过 Brain 验收。"
    if phase == TaskPhase.AWAITING_APPROVAL:
        return "计划已生成，确认后开始修改代码。"
    if phase == TaskPhase.CANCELLED:
        return "任务已由用户取消。"
    if payload and isinstance(payload.get("error"), str):
        return str(payload["error"])
    if phase == TaskPhase.BLOCKED:
        return "任务已阻塞，未达到最终通过状态。"
    if orchestrator_error:
        return f"任务执行失败：{orchestrator_error}"
    if phase == TaskPhase.UNKNOWN:
        return "进程已结束，但无法确认最终验收状态。"
    return f"任务执行失败，退出码：{exit_code}。"
