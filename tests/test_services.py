import json
from pathlib import Path

from app.models.settings import AppSettings
from app.models.task import AgentTask
from app.services.history_service import HistoryService
from app.services.settings_service import SettingsService


def test_settings_round_trip_and_invalid_file_fallback(tmp_path: Path) -> None:
    path = tmp_path / "data" / "settings.json"
    service = SettingsService(path)
    settings = AppSettings(project_path=r"E:\项目 空格", default_max_retries=5)
    service.save(settings)
    loaded = service.load()
    assert loaded.project_path == r"E:\项目 空格"
    assert loaded.default_max_retries == 5

    path.write_text("not-json", encoding="utf-8")
    assert service.load().default_brain == "claude"


def test_history_keeps_latest_one_hundred_items(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    service = HistoryService(path)
    for index in range(105):
        service.add(
            AgentTask(
                id=f"task-{index}",
                description=f"task {index}",
                project_path=str(tmp_path),
                brain="claude",
                executor="codex",
                max_retries=3,
                status="passed",
            )
        )
    loaded = service.load()
    assert len(loaded) == 100
    assert loaded[0].id == "task-104"
    assert loaded[-1].id == "task-5"
    assert isinstance(json.loads(path.read_text(encoding="utf-8")), list)



def test_run_mode_migrates_from_older_settings_and_history() -> None:
    from app.models.settings import AppSettings
    from app.models.task import AgentTask

    assert AppSettings.from_dict({}).run_mode == "auto"
    assert AppSettings.from_dict({"single_agent": True}).run_mode == "single"
    assert AppSettings.from_dict({"single_agent": False}).run_mode == "auto"
    assert AppSettings.from_dict({"run_mode": "reviewed", "single_agent": True}).run_mode == "reviewed"
    assert AppSettings.from_dict({"run_mode": "bogus"}).run_mode == "auto"

    base = {"description": "d", "project_path": "p"}
    # Entries written before modes existed ran the multi-task plan flow.
    assert AgentTask.from_dict(base).mode == "planned"
    assert AgentTask.from_dict({**base, "mode": "dual"}).mode == "planned"
    assert AgentTask.from_dict({**base, "mode": "single"}).mode == "single"
    assert AgentTask.from_dict({**base, "mode": "auto"}).mode == "auto"


def test_removed_agent_choices_fall_back_to_defaults() -> None:
    settings = AppSettings.from_dict({"default_brain": "sub2api", "default_executor": "sub2api"})
    assert settings.default_brain == "claude"
    assert settings.default_executor == "codex"
    kept = AppSettings.from_dict({"default_brain": "codex", "default_executor": "openai-api"})
    assert (kept.default_brain, kept.default_executor) == ("codex", "openai-api")


def test_history_update_keeps_the_entry_in_place(tmp_path: Path) -> None:
    service = HistoryService(tmp_path / "history.json")
    first = AgentTask("first", "C:/p", "claude", "codex", 1, status="awaiting_approval")
    second = AgentTask("second", "C:/p", "claude", "codex", 1)
    service.add(first)
    service.add(second)
    first.status = "continued"
    history = service.update(first)
    assert [task.description for task in history] == ["second", "first"]
    assert history[1].status == "continued"
