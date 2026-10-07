"""API profiles for Claude and Codex, in the manner of cc-switch.

Every profile (a name, a base URL, an API key and an optional model) is kept
in providers.json; the active one for each tool is written to the project's
.env, which every orchestrator command Studio starts reads. Nothing global
changes: ~/.claude and ~/.codex are left alone, and choosing the official
login simply leaves the variables out.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.utils.paths import env_path, providers_path

TOOLS = ("claude", "codex")
TOOL_LABELS = {"claude": "Claude", "codex": "Codex"}

# Environment variable per field. Claude Code reads its own; Codex has no
# such variables, so the orchestrator turns these into -c provider overrides.
ENV_KEYS: dict[str, dict[str, str]] = {
    "claude": {"base_url": "ANTHROPIC_BASE_URL", "api_key": "ANTHROPIC_AUTH_TOKEN", "model": "ANTHROPIC_MODEL"},
    "codex": {
        "base_url": "DUAL_AGENT_CODEX_BASE_URL",
        "api_key": "DUAL_AGENT_CODEX_API_KEY",
        "model": "DUAL_AGENT_CODEX_MODEL",
    },
}
MANAGED_KEYS = {key for fields in ENV_KEYS.values() for key in fields.values()}
_BLOCK_START = "# --- API 配置（由 Dual Agent Studio 写入，请在应用内修改） ---"
_BLOCK_END = "# --- API 配置结束 ---"


@dataclass
class ApiProfile:
    name: str
    base_url: str
    api_key: str
    model: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def masked_key(self) -> str:
        key = self.api_key.strip()
        if not key:
            return "未填写 Key"
        return f"{key[:4]}••••{key[-4:]}" if len(key) > 10 else "••••"


@dataclass
class ProviderState:
    profiles: dict[str, list[ApiProfile]] = field(default_factory=lambda: {tool: [] for tool in TOOLS})
    # Profile id per tool; "" means the CLI's own (official) login.
    active: dict[str, str] = field(default_factory=lambda: {tool: "" for tool in TOOLS})

    def active_profile(self, tool: str) -> ApiProfile | None:
        return next((p for p in self.profiles.get(tool, []) if p.id == self.active.get(tool)), None)


class ProviderService:
    def __init__(self, path: Path | None = None, env_file: Path | None = None) -> None:
        self.path = path or providers_path()
        self.env_file = env_file or env_path()

    def load(self) -> ProviderState:
        state = ProviderState()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return state
        for tool in TOOLS:
            entries = raw.get("profiles", {}).get(tool, []) if isinstance(raw, dict) else []
            for entry in entries if isinstance(entries, list) else []:
                if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                    state.profiles[tool].append(
                        ApiProfile(
                            name=entry["name"],
                            base_url=str(entry.get("base_url", "")),
                            api_key=str(entry.get("api_key", "")),
                            model=str(entry.get("model", "")),
                            id=str(entry.get("id") or uuid.uuid4().hex[:12]),
                        )
                    )
            active = raw.get("active", {}).get(tool, "") if isinstance(raw, dict) else ""
            state.active[tool] = active if any(p.id == active for p in state.profiles[tool]) else ""
        return state

    def save(self, state: ProviderState) -> None:
        """Stores every profile and rewrites the .env for the active ones."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "profiles": {tool: [asdict(p) for p in state.profiles[tool]] for tool in TOOLS},
            "active": dict(state.active),
        }
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)
        self.write_env(state)

    def write_env(self, state: ProviderState) -> None:
        """Replaces Studio's block in .env, keeping every other line the user wrote."""
        try:
            lines = self.env_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        kept: list[str] = []
        inside = False
        for line in lines:
            stripped = line.strip()
            if stripped == _BLOCK_START:
                inside = True
                continue
            if stripped == _BLOCK_END:
                inside = False
                continue
            # Managed keys outside the block too: one source of truth.
            if inside or _key_of(stripped) in MANAGED_KEYS:
                continue
            kept.append(line)
        block: list[str] = []
        for tool in TOOLS:
            profile = state.active_profile(tool)
            if profile is None:
                continue
            keys = ENV_KEYS[tool]
            block.append(f"# {TOOL_LABELS[tool]}: {profile.name}")
            block.append(f"{keys['base_url']}={_quote(profile.base_url.strip())}")
            block.append(f"{keys['api_key']}={_quote(profile.api_key.strip())}")
            if profile.model.strip():
                block.append(f"{keys['model']}={_quote(profile.model.strip())}")
        while kept and not kept[-1].strip():
            kept.pop()
        text = "\n".join(kept)
        if block:
            text = (text + "\n\n" if text else "") + "\n".join([_BLOCK_START, *block, _BLOCK_END])
        if text or self.env_file.exists():
            self.env_file.parent.mkdir(parents=True, exist_ok=True)
            self.env_file.write_text(text + ("\n" if text else ""), encoding="utf-8")


def read_env_file(path: Path | None = None) -> dict[str, str]:
    """KEY=VALUE pairs of a .env file; comments, blanks and bad lines skipped."""
    try:
        lines = (path or env_path()).read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return {}
    values: dict[str, str] = {}
    for line in lines:
        key = _key_of(line.strip())
        if not key:
            continue
        value = line.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def _key_of(line: str) -> str:
    if not line or line.startswith("#") or "=" not in line:
        return ""
    key = line.split("=", 1)[0].strip()
    if key.startswith("export "):
        key = key[len("export "):].strip()
    return key if key.replace("_", "").isalnum() else ""


def _quote(value: str) -> str:
    return f'"{value}"' if any(ch in value for ch in " #'\"") else value
