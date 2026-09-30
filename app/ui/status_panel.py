from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.task_state import StateSnapshot, TaskPhase
from app.models.environment import EnvironmentCheck, EnvironmentStatus
from app.ui.theme import ACTIVE_COLOR, DANGER, DONE_COLOR, PENDING_COLOR


class _StageRow(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        self.dot = QFrame()
        self.dot.setFixedSize(10, 10)
        self.title = QLabel(title)
        self.detail = QLabel("")
        self.detail.setObjectName("muted")
        layout.addWidget(self.dot)
        layout.addWidget(self.title)
        layout.addStretch()
        layout.addWidget(self.detail)
        self.set_state("pending")

    def set_state(self, state: str, detail: str = "") -> None:
        colors = {
            "pending": PENDING_COLOR,
            "active": ACTIVE_COLOR,
            "done": DONE_COLOR,
            "failed": DANGER,
        }
        color = colors.get(state, colors["pending"])
        self.dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
        self.detail.setText(detail)


class StatusPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("section")

        # Same rationale as TaskPanel: the stage rows + environment grid can
        # need more height than a smaller/lower-resolution monitor leaves
        # available, so this scrolls instead of risking overlapping content.
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; }")
        outer_layout.addWidget(scroll_area)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        scroll_area.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        title = QLabel("工作流程")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.overall = QLabel("空闲")
        self.overall.setObjectName("statusBadge")
        layout.addWidget(self.overall)

        self.plan_stage = _StageRow("Brain 分析")
        self.execute_stage = _StageRow("Executor 执行")
        self.review_stage = _StageRow("Brain 验收")
        self.final_stage = _StageRow("最终结果")
        for stage in (
            self.plan_stage,
            self.execute_stage,
            self.review_stage,
            self.final_stage,
        ):
            layout.addWidget(stage)

        environment_title = QLabel("环境状态")
        environment_title.setObjectName("sectionTitle")
        layout.addSpacing(8)
        layout.addWidget(environment_title)
        self.environment_grid = QGridLayout()
        self.environment_labels: dict[str, QLabel] = {}
        names = (
            ("claude_cli", "Claude CLI"),
            ("claude_auth", "Claude 登录"),
            ("codex_cli", "Codex CLI"),
            ("codex_auth", "Codex 登录"),
            ("git", "Git"),
            ("orchestrator", "Orchestrator"),
            ("doctor", "Doctor"),
        )
        for row, (key, label) in enumerate(names):
            self.environment_grid.addWidget(QLabel(label), row, 0)
            value = QLabel("未检查")
            value.setObjectName("muted")
            value.setToolTip("尚未执行环境检查")
            self.environment_labels[key] = value
            self.environment_grid.addWidget(value, row, 1)
        self.environment_grid.setColumnStretch(1, 1)
        layout.addLayout(self.environment_grid)
        layout.addStretch()

    def set_snapshot(self, snapshot: StateSnapshot) -> None:
        self.overall.setText(snapshot.message)
        for stage in (
            self.plan_stage,
            self.execute_stage,
            self.review_stage,
            self.final_stage,
        ):
            stage.set_state("pending")

        phase = snapshot.phase
        if phase in {TaskPhase.IDLE, TaskPhase.CHECKING}:
            return
        if phase in {TaskPhase.RUNNING, TaskPhase.PLANNING}:
            self.plan_stage.set_state("active")
            return
        self.plan_stage.set_state("done")
        if phase in {TaskPhase.EXECUTING, TaskPhase.RETRYING}:
            detail = f"第 {snapshot.attempt} 次" if snapshot.attempt else ""
            self.execute_stage.set_state("active", detail)
            return
        self.execute_stage.set_state("done")
        if phase == TaskPhase.REVIEWING:
            self.review_stage.set_state("active")
            return
        if phase == TaskPhase.PASSED:
            self.review_stage.set_state("done")
            self.final_stage.set_state("done", "通过")
            return
        if phase in {TaskPhase.BLOCKED, TaskPhase.FAILED, TaskPhase.CANCELLED, TaskPhase.UNKNOWN}:
            self.review_stage.set_state("failed")
            label = {
                TaskPhase.BLOCKED: "阻塞",
                TaskPhase.FAILED: "失败",
                TaskPhase.CANCELLED: "已取消",
                TaskPhase.UNKNOWN: "未知",
            }[phase]
            self.final_stage.set_state("failed", label)

    def set_environment_progress(self, key: str, check: EnvironmentCheck) -> None:
        label = self.environment_labels.get(key)
        if not label:
            return
        label.setText("可用" if check.available else "不可用")
        label.setStyleSheet(f"color: {DONE_COLOR if check.available else DANGER};")
        label.setToolTip(check.detail)

    def set_environment(self, status: EnvironmentStatus) -> None:
        for key in self.environment_labels:
            self.set_environment_progress(key, getattr(status, key))

