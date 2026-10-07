from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QDialog, QLabel, QPushButton

from app.services.provider_service import ApiProfile, ProviderService, read_env_file
from app.ui import provider_dialog
from app.ui.provider_dialog import ProfileEditor, ProviderDialog

pytestmark = pytest.mark.skipif(os.name != "nt", reason="uses real QWidgets on Windows")


def _texts(dialog: ProviderDialog, kind) -> list[str]:
    return [widget.text() for widget in dialog._scroll.widget().findChildren(kind)]


def test_adding_a_first_profile_activates_it_and_switching_rewrites_env(tmp_path: Path, monkeypatch) -> None:
    service = ProviderService(tmp_path / "providers.json", tmp_path / ".env")
    dialog = ProviderDialog(service)
    assert "官方登录" in _texts(dialog, QLabel) and "使用中" in _texts(dialog, QLabel)

    profile = ApiProfile("中转 A", "https://relay.example", "sk-test-1234567")
    monkeypatch.setattr(ProfileEditor, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(ProfileEditor, "profile", lambda self: profile)
    dialog._show_tool("codex")
    dialog._add_profile()
    assert service.load().active["codex"] == profile.id
    assert read_env_file(service.env_file)["DUAL_AGENT_CODEX_BASE_URL"] == "https://relay.example"
    assert "sk-t••••4567" in " ".join(_texts(dialog, QLabel)), "the key is shown masked"

    # One click on the official card's 启用 goes back to the CLI's login.
    [use] = [b for b in dialog._scroll.widget().findChildren(QPushButton) if b.text() == "启用"]
    use.click()
    assert service.load().active["codex"] == ""
    assert read_env_file(service.env_file) == {}
    # Claude's list was never touched.
    dialog._show_tool("claude")
    assert service.load().profiles["claude"] == []


def test_deleting_the_active_profile_falls_back_to_the_official_login(tmp_path: Path, monkeypatch) -> None:
    service = ProviderService(tmp_path / "providers.json", tmp_path / ".env")
    dialog = ProviderDialog(service)
    profile = ApiProfile("A", "https://a.example", "sk-aaaaaaaaaa")
    dialog.state.profiles["claude"].append(profile)
    dialog._activate(profile)
    assert read_env_file(service.env_file)["ANTHROPIC_AUTH_TOKEN"] == "sk-aaaaaaaaaa"
    monkeypatch.setattr(provider_dialog.QMessageBox, "question", lambda *args: provider_dialog.QMessageBox.StandardButton.Yes)
    dialog._delete_profile(profile)
    assert service.load().profiles["claude"] == [] and read_env_file(service.env_file) == {}


def test_editor_validates_before_saving_and_keeps_the_id() -> None:
    original = ApiProfile("A", "https://a.example", "sk-1", id="keep")
    editor = ProfileEditor("codex", original)
    editor.url_edit.setText("relay.example")
    editor._accept()
    assert editor.result() != QDialog.DialogCode.Accepted and "http" in editor.test_result.text()
    editor.url_edit.setText("https://b.example/")
    editor._accept()
    assert editor.result() == QDialog.DialogCode.Accepted
    assert editor.profile() == ApiProfile("A", "https://b.example", "sk-1", id="keep")


def test_closing_the_editor_mid_test_aborts_the_request_safely() -> None:
    from PySide6.QtWidgets import QApplication

    for _ in range(3):
        editor = ProfileEditor("claude", None)
        # Unroutable address: the request is still in flight when we close.
        editor.url_edit.setText("http://10.255.255.1:9")
        editor.key_edit.setText("sk-test")
        editor._test()
        assert not editor.test_button.isEnabled()
        editor.reject()
        assert editor._reply is None
        del editor
        QApplication.processEvents()
