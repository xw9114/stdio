"""API settings: switch Claude and Codex between API profiles (cc-switch style)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.services.provider_service import TOOL_LABELS, TOOLS, ApiProfile, ProviderService, ProviderState
from app.ui.icons import icon
from app.ui.theme import TEXT_MUTED

_OFFICIAL_DETAIL = {
    "claude": "使用 Claude Code 自己的登录和配置（不写入 .env）",
    "codex": "使用 Codex CLI 自己的登录和 config.toml（不写入 .env）",
}
_URL_HINT = {
    "claude": "https://api.example.com（Anthropic 兼容接口）",
    "codex": "https://api.example.com/v1（OpenAI Responses 兼容接口）",
}


class ProviderDialog(QDialog):
    def __init__(self, service: ProviderService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("API 配置")
        self.setMinimumSize(640, 520)
        self._service = service
        self._state = service.load()
        self._tool = "claude"
        # Whether anything was saved, so the caller only reports real changes.
        self.changed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)
        title = QLabel("API 配置")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        subtitle = QLabel("为 Claude 和 Codex 准备多套 API，一键切换。切换后写入项目的 .env，只影响 Studio 之后启动的任务，不改全局配置。")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        segment_bar = QFrame()
        segment_bar.setObjectName("segmentBar")
        segments = QHBoxLayout(segment_bar)
        segments.setContentsMargins(3, 3, 3, 3)
        segments.setSpacing(2)
        self._tool_buttons = QButtonGroup(self)
        for tool in TOOLS:
            button = QPushButton(TOOL_LABELS[tool])
            button.setObjectName("segment")
            button.setCheckable(True)
            button.setChecked(tool == self._tool)
            button.clicked.connect(lambda _checked=False, chosen=tool: self._show_tool(chosen))
            self._tool_buttons.addButton(button)
            segments.addWidget(button)
        bar_row = QHBoxLayout()
        bar_row.addWidget(segment_bar)
        bar_row.addStretch()
        layout.addLayout(bar_row)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("profileScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self._scroll, 1)

        bottom = QHBoxLayout()
        self.add_button = QPushButton("+ 添加配置")
        self.add_button.setObjectName("primaryButton")
        self.add_button.clicked.connect(self._add_profile)
        bottom.addWidget(self.add_button)
        location = QLabel(f".env：{service.env_file}")
        location.setObjectName("muted")
        location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        location.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        bottom.addWidget(location, 1)
        close = QPushButton("完成")
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        layout.addLayout(bottom)
        self._render()

    @property
    def state(self) -> ProviderState:
        return self._state

    def _show_tool(self, tool: str) -> None:
        self._tool = tool
        self._render()

    def _render(self) -> None:
        content = QWidget()
        content.setObjectName("profileList")
        cards = QVBoxLayout(content)
        cards.setContentsMargins(0, 4, 4, 4)
        cards.setSpacing(8)
        active = self._state.active[self._tool]
        if self._tool == "claude":
            hint = QLabel(
                "「启用」让 Brain 和 Executor 都走这个 API；「仅 Executor」只让 Executor 走它，"
                "Brain 继续用上面选中的，适合用便宜的模型做修改、Claude 负责规划和验收。"
            )
            hint.setObjectName("muted")
            hint.setWordWrap(True)
            cards.addWidget(hint)
        cards.addWidget(self._card(None, active == ""))
        for profile in self._state.profiles[self._tool]:
            cards.addWidget(self._card(profile, profile.id == active))
        if not self._state.profiles[self._tool]:
            empty = QLabel("还没有自定义配置。点击下方“添加配置”，填入中转或官方 API 的地址和 Key。")
            empty.setObjectName("muted")
            empty.setWordWrap(True)
            cards.addWidget(empty)
        cards.addStretch()
        self._scroll.setWidget(content)

    def _card(self, profile: ApiProfile | None, active: bool) -> QFrame:
        card = QFrame()
        card.setObjectName("profileCard")
        card.setProperty("active", "true" if active else "false")
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 11, 10, 11)
        row.setSpacing(8)
        text = QVBoxLayout()
        text.setSpacing(3)
        name = QLabel("官方登录" if profile is None else profile.name)
        name.setObjectName("profileName")
        text.addWidget(name)
        if profile is None:
            detail_text = _OFFICIAL_DETAIL[self._tool]
        else:
            parts = [profile.base_url or "未填写地址", profile.masked_key()]
            if profile.model:
                parts.append(f"模型 {profile.model}")
            detail_text = " · ".join(parts)
        detail = QLabel(detail_text)
        detail.setObjectName("profileDetail")
        detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        detail.setToolTip(detail_text)
        text.addWidget(detail)
        row.addLayout(text, 1)

        if active:
            badge = QLabel("使用中")
            badge.setObjectName("activePill")
            row.addWidget(badge)
        else:
            use = QPushButton("启用")
            use.setObjectName("toolButton")
            use.clicked.connect(lambda _checked=False: self._activate(profile))
            row.addWidget(use)
        if profile is not None and self._tool == "claude":
            if profile.id == self._state.executor:
                badge = QLabel("Executor 使用中")
                badge.setObjectName("activePill")
                row.addWidget(badge)
                stop = QPushButton("停用")
                stop.setObjectName("toolButton")
                stop.setToolTip("Executor 改回跟随上面「使用中」的配置")
                stop.clicked.connect(lambda _checked=False: self._use_for_executor(None))
                row.addWidget(stop)
            else:
                executor = QPushButton("仅 Executor")
                executor.setObjectName("toolButton")
                executor.setToolTip("只让 Executor 走这个 API，Brain 不受影响")
                executor.clicked.connect(lambda _checked=False: self._use_for_executor(profile))
                row.addWidget(executor)
        if profile is not None:
            for icon_name, tip, handler in (
                ("edit", "编辑", lambda _checked=False: self._edit_profile(profile)),
                ("trash", "删除", lambda _checked=False: self._delete_profile(profile)),
            ):
                button = QToolButton()
                button.setObjectName("iconButton")
                button.setIcon(icon(icon_name, TEXT_MUTED, 16))
                button.setIconSize(QSize(16, 16))
                button.setToolTip(tip)
                button.clicked.connect(handler)
                row.addWidget(button)
        return card

    def _activate(self, profile: ApiProfile | None) -> None:
        self._state.active[self._tool] = "" if profile is None else profile.id
        self._save()

    def _use_for_executor(self, profile: ApiProfile | None) -> None:
        if profile is not None and not profile.model.strip():
            # Without one the Executor asks the gateway for Claude's default
            # model, which a third-party gateway usually does not have.
            answer = QMessageBox.question(
                self,
                "没有填写模型",
                f"“{profile.name}”没有填写模型。第三方 API 通常不认识 Claude 的默认模型名，"
                "Executor 可能会调用失败。\n\n仍然用于 Executor 吗？（可以先编辑配置填上模型）",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._state.executor = "" if profile is None else profile.id
        self._save()

    def _add_profile(self) -> None:
        editor = ProfileEditor(self._tool, None, self)
        if editor.exec():
            profile = editor.profile()
            self._state.profiles[self._tool].append(profile)
            # A first profile is what the user wants to use.
            if not self._state.active[self._tool]:
                self._state.active[self._tool] = profile.id
            self._save()

    def _edit_profile(self, profile: ApiProfile) -> None:
        editor = ProfileEditor(self._tool, profile, self)
        if editor.exec():
            updated = editor.profile()
            profile.name, profile.base_url, profile.api_key, profile.model = (
                updated.name,
                updated.base_url,
                updated.api_key,
                updated.model,
            )
            self._save()

    def _delete_profile(self, profile: ApiProfile) -> None:
        answer = QMessageBox.question(self, "删除配置", f"删除“{profile.name}”？")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._state.profiles[self._tool] = [p for p in self._state.profiles[self._tool] if p.id != profile.id]
        if self._state.active[self._tool] == profile.id:
            self._state.active[self._tool] = ""
        if self._state.executor == profile.id:
            self._state.executor = ""
        self._save()

    def _save(self) -> None:
        try:
            self._service.save(self._state)
            self.changed = True
        except OSError as error:
            QMessageBox.warning(self, "保存失败", f"无法写入配置：{error}")
        self._render()


class ProfileEditor(QDialog):
    """Adds or edits one profile, with a quick connection test."""

    def __init__(self, tool: str, profile: ApiProfile | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tool = tool
        self._original = profile
        self.setWindowTitle(f"{'编辑' if profile else '添加'} {TOOL_LABELS[tool]} 配置")
        self.setMinimumWidth(520)
        self._network = QNetworkAccessManager(self)
        self._pending: list[str] = []
        self._reply: QNetworkReply | None = None
        self._key = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        form = QFormLayout()
        form.setVerticalSpacing(10)
        self.name_edit = QLineEdit(profile.name if profile else "")
        self.name_edit.setPlaceholderText("例如：中转站 A")
        form.addRow("名称", self.name_edit)
        self.url_edit = QLineEdit(profile.base_url if profile else "")
        self.url_edit.setPlaceholderText(_URL_HINT[tool])
        form.addRow("Base URL", self.url_edit)
        key_row = QHBoxLayout()
        self.key_edit = QLineEdit(profile.api_key if profile else "")
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("sk-…")
        key_row.addWidget(self.key_edit, 1)
        self.reveal_button = QPushButton("显示")
        self.reveal_button.setObjectName("toolButton")
        self.reveal_button.setCheckable(True)
        self.reveal_button.toggled.connect(self._toggle_key)
        key_row.addWidget(self.reveal_button)
        form.addRow("API Key", key_row)
        self.model_edit = QLineEdit(profile.model if profile else "")
        self.model_edit.setPlaceholderText("可选，留空使用默认模型")
        form.addRow("模型", self.model_edit)
        layout.addLayout(form)

        test_row = QHBoxLayout()
        self.test_button = QPushButton("测试连接")
        self.test_button.clicked.connect(self._test)
        test_row.addWidget(self.test_button)
        self.test_result = QLabel("")
        self.test_result.setObjectName("testResult")
        self.test_result.setWordWrap(True)
        test_row.addWidget(self.test_result, 1)
        layout.addLayout(test_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setText("保存")
        save.setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def profile(self) -> ApiProfile:
        profile = ApiProfile(
            name=self.name_edit.text().strip(),
            base_url=self.url_edit.text().strip().rstrip("/"),
            api_key=self.key_edit.text().strip(),
            model=self.model_edit.text().strip(),
        )
        if self._original is not None:
            profile.id = self._original.id
        return profile

    def _accept(self) -> None:
        if not self.name_edit.text().strip():
            self._show_result("请填写名称。", ok=False)
            return
        url = self.url_edit.text().strip()
        if not url.startswith(("http://", "https://")):
            self._show_result("Base URL 需要以 http:// 或 https:// 开头。", ok=False)
            return
        if not self.key_edit.text().strip():
            self._show_result("请填写 API Key。", ok=False)
            return
        self.accept()

    def _toggle_key(self, visible: bool) -> None:
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)
        self.reveal_button.setText("隐藏" if visible else "显示")

    def _test(self) -> None:
        """Lists the gateway's models: proves the address answers and, where
        listing is supported, that the key is accepted - without spending
        tokens on a real request."""
        base = self.url_edit.text().strip().rstrip("/")
        key = self.key_edit.text().strip()
        if not base.startswith(("http://", "https://")) or not key:
            self._show_result("先填好 Base URL 和 API Key。", ok=False)
            return
        if base.endswith("/v1"):
            self._pending = [f"{base}/models"]
        else:
            self._pending = [f"{base}/v1/models", f"{base}/models"]
        self._key = key
        self.test_button.setEnabled(False)
        self._show_result("正在连接…", ok=None)
        self._request_next()

    def _request_next(self) -> None:
        request = QNetworkRequest(QUrl(self._pending.pop(0)))
        request.setTransferTimeout(15_000)
        request.setRawHeader(b"Authorization", f"Bearer {self._key}".encode())
        if self._tool == "claude":
            request.setRawHeader(b"x-api-key", self._key.encode())
            request.setRawHeader(b"anthropic-version", b"2023-06-01")
        # A bound slot, not a lambda: Qt drops the connection when the editor
        # goes away, so a reply finishing after close cannot reach a dead one.
        self._reply = self._network.get(request)
        self._reply.finished.connect(self._on_reply)

    def _on_reply(self) -> None:
        reply, self._reply = self._reply, None
        if reply is None:
            return
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        reason = reply.attribute(QNetworkRequest.Attribute.HttpReasonPhraseAttribute) or ""
        error_text = reply.errorString()
        reply.deleteLater()
        if status == 404 and self._pending:
            self._request_next()
            return
        self.test_button.setEnabled(True)
        if status is None:
            self._show_result(f"无法连接：{error_text}", ok=False)
        elif 200 <= int(status) < 300:
            self._show_result(f"连接成功，Key 有效（HTTP {status}）", ok=True)
        elif int(status) in {401, 403}:
            self._show_result(f"地址可以访问，但 Key 无效或没有权限（HTTP {status}）", ok=False)
        elif int(status) == 404:
            self._show_result("地址可以访问，但该接口不支持列出模型，无法验证 Key；可直接保存后用一次小任务确认。", ok=None)
        else:
            self._show_result(f"服务返回 HTTP {status} {reason}".strip(), ok=False)

    def done(self, result: int) -> None:
        if self._reply is not None:
            reply, self._reply = self._reply, None
            reply.finished.disconnect(self._on_reply)
            reply.abort()
            reply.deleteLater()
        super().done(result)

    def _show_result(self, text: str, ok: bool | None) -> None:
        self.test_result.setText(text)
        self.test_result.setProperty("state", {True: "ok", False: "error", None: "pending"}[ok])
        self.test_result.style().unpolish(self.test_result)
        self.test_result.style().polish(self.test_result)
