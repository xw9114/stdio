# Dual Agent Studio

Dual Agent Studio is a native Windows desktop front end for the existing `dual-agent-orchestrator` command-line application. It does not replace or modify the orchestrator. CLI users can continue using `dual-agent.cmd` directly.

## Features

- Select a Git or non-Git project folder.
- Enter a natural-language engineering task.
- Choose Brain and Executor providers supported by the installed orchestrator.
- Infer Claude/Codex roles and retry count from Chinese or English task text.
- Run `dual-agent.cmd` without blocking the interface.
- Stream stdout and stderr into a bounded live log.
- Poll `status --json` every three seconds and show verified workflow state.
- Cancel only the process tree created for the active task.
- Inspect read-only Git status and diff.
- Persist settings and the most recent 100 tasks.
- Save complete task logs and application diagnostics.

## Requirements

- Windows 10 or Windows 11
- Python 3.11 or newer
- Git CLI
- Claude Code and/or Codex CLI for the providers you select
- Existing dual-agent orchestrator, defaulting to:

```text
E:\codex\dual-agent-orchestrator\dual-agent.cmd
```

Authentication remains entirely in the CLIs. Studio does not read or save tokens or passwords.

```powershell
claude auth status
codex login
```

## Installation

```powershell
cd E:\codex\dual-agent-studio
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

For development, tests, and packaging:

```powershell
pip install -r requirements-dev.txt
```

## Run

```powershell
python main.py
```

The first screen uses the configured orchestrator path. Open **Settings** to select another `dual-agent.cmd`, set default providers and retries, and control startup environment checks.

## Typical Workflow

1. Click **Select Project** and choose the target repository.
2. Use **Initialize** to run `dual-agent.cmd init` when needed. Existing configuration is never overwritten without confirmation.
3. Enter the complete task and acceptance requirements.
4. Select Brain, Executor, and maximum retries. Optional natural-language inference never overrides a field changed manually in the current session.
5. Click **Start Task**.
6. Follow verified state, live output, raw status JSON, and Git diff.
7. Review the final status. Exit code zero alone is not treated as success; Studio also requires orchestrator status `complete`.

## Environment Checks

The environment checker actually runs:

```text
claude --version
claude auth status
codex --version
codex login status
git --version
dual-agent.cmd --help
dual-agent.cmd doctor --cwd <project>
```

Failures are shown without crashing the application. The real `doctor` result depends on the selected project's Dual Agent configuration.

## Data and Logs

During source development, files are stored under `data/`:

```text
data/settings.json
data/history.json
data/app.log
data/logs/*.log
```

In a packaged build they are stored under `%LOCALAPPDATA%\DualAgentStudio` so the application remains writable when installed in a protected directory.

## Tests

```powershell
python -m pytest
python -m compileall -q main.py app
```

The suite covers command construction, Chinese paths and tasks, natural-language inference, status/exit handling, persistence, the real orchestrator help contract, and the no-run `status --json` edge case.

## Build the Windows Application

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
.\build.ps1
```

Output:

```text
dist\Dual Agent Studio\Dual Agent Studio.exe
```

PyInstaller produces a directory build because it starts faster and is easier to diagnose than a single-file package. The application still launches by double-clicking the EXE.

## Current Scope

Implemented in the MVP:

- Project picker and initialization
- Provider and retry controls
- QProcess task execution and live output
- Process-tree cancellation
- Environment and authentication checks
- Orchestrator status polling
- Result, log, Git diff, JSON, and history views
- Persistent settings and history
- Rule-based role inference

Not implemented yet:

- Worktree or temporary-branch isolation
- User approval and merge workflow
- Multiple simultaneous tasks
- Remote execution or cloud synchronization
- Plugin/provider marketplace
- Structured event streaming from the orchestrator

