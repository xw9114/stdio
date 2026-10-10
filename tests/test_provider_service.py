from __future__ import annotations

import json
from pathlib import Path

from app.core.command_builder import CommandBuilder
from app.services.provider_service import ApiProfile, ProviderService, ProviderState, read_env_file


def _service(tmp_path: Path) -> ProviderService:
    return ProviderService(tmp_path / "providers.json", tmp_path / ".env")


def test_profiles_round_trip_and_only_active_ones_reach_env(tmp_path: Path) -> None:
    service = _service(tmp_path)
    state = ProviderState()
    relay = ApiProfile("中转 A", "https://relay.example/v1", "sk-codex-123456", "gpt-5")
    spare = ApiProfile("备用", "https://spare.example", "sk-spare-000000")
    claude = ApiProfile("Claude 中转", "https://claude.example", "sk-ant-abcdef")
    state.profiles["codex"] += [relay, spare]
    state.profiles["claude"].append(claude)
    state.active.update(codex=relay.id, claude=claude.id)
    service.save(state)

    loaded = service.load()
    assert loaded.profiles == state.profiles and loaded.active == state.active
    assert read_env_file(service.env_file) == {
        "ANTHROPIC_BASE_URL": "https://claude.example",
        "ANTHROPIC_AUTH_TOKEN": "sk-ant-abcdef",
        "DUAL_AGENT_CODEX_BASE_URL": "https://relay.example/v1",
        "DUAL_AGENT_CODEX_API_KEY": "sk-codex-123456",
        "DUAL_AGENT_CODEX_MODEL": "gpt-5",
    }

    # Back to the official login: the variables leave .env.
    loaded.active.update(codex="", claude="")
    service.save(loaded)
    assert read_env_file(service.env_file) == {}


def test_env_keeps_the_users_own_lines_and_drops_stale_managed_keys(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.env_file.write_text(
        "# mine\nFOO=bar\nexport ANTHROPIC_BASE_URL=https://old.example\nBAZ='a b'\n", encoding="utf-8"
    )
    state = ProviderState()
    profile = ApiProfile("A", "https://new.example", "key with space")
    state.profiles["claude"].append(profile)
    state.active["claude"] = profile.id
    for _ in range(2):  # rewriting is stable
        service.save(state)
    text = service.env_file.read_text(encoding="utf-8")
    assert text.startswith("# mine\nFOO=bar\nBAZ='a b'\n")
    assert text.count("ANTHROPIC_BASE_URL") == 1
    assert read_env_file(service.env_file) == {
        "FOO": "bar",
        "BAZ": "a b",
        "ANTHROPIC_BASE_URL": "https://new.example",
        "ANTHROPIC_AUTH_TOKEN": "key with space",
    }


def test_bad_files_load_as_empty_and_dangling_active_ids_are_dropped(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.path.write_text("{oops", encoding="utf-8")
    assert service.load() == ProviderState()
    service.path.write_text(
        json.dumps({"profiles": {"codex": [{"name": "x", "id": "a"}, "junk"]}, "active": {"codex": "gone"}}),
        encoding="utf-8",
    )
    state = service.load()
    assert [p.id for p in state.profiles["codex"]] == ["a"] and state.active["codex"] == ""


def test_masked_key_never_shows_the_middle() -> None:
    assert ApiProfile("a", "u", "sk-1234567890abcd").masked_key() == "sk-1••••abcd"
    assert ApiProfile("a", "u", "short").masked_key() == "••••"


def test_orchestrator_commands_carry_the_env_file_at_launch(tmp_path: Path, _isolated_api_settings: Path) -> None:
    builder = CommandBuilder(str(tmp_path / "dual-agent.cmd"))
    assert builder.build_doctor_command(str(tmp_path)).environment == ()
    (_isolated_api_settings / ".env").write_text("DUAL_AGENT_CODEX_BASE_URL=https://relay.example\n", encoding="utf-8")
    assert dict(builder.build_doctor_command(str(tmp_path)).environment) == {
        "DUAL_AGENT_CODEX_BASE_URL": "https://relay.example"
    }


def test_an_executor_only_profile_gets_its_own_variables(tmp_path: Path) -> None:
    service = _service(tmp_path)
    state = ProviderState()
    cheap = ApiProfile("便宜模型", "http://gateway.example", "gw-key-123456", "deepseek-v4.1-flash")
    state.profiles["claude"].append(cheap)
    state.executor = cheap.id
    service.save(state)

    loaded = service.load()
    assert loaded.executor == cheap.id and loaded.active["claude"] == "", "the Brain keeps the official login"
    assert read_env_file(service.env_file) == {
        "DUAL_AGENT_CLAUDE_EXECUTOR_BASE_URL": "http://gateway.example",
        "DUAL_AGENT_CLAUDE_EXECUTOR_API_KEY": "gw-key-123456",
        "DUAL_AGENT_CLAUDE_EXECUTOR_MODEL": "deepseek-v4.1-flash",
    }

    # A deleted profile's id no longer counts.
    raw = json.loads(service.path.read_text(encoding="utf-8"))
    raw["profiles"]["claude"] = []
    service.path.write_text(json.dumps(raw), encoding="utf-8")
    assert service.load().executor == ""
