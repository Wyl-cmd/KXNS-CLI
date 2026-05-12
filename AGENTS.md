# KXNS Hunter CLI

## Quick commands (use uv)

- `uv run ruff format`
- `uv run ruff check`
- `uv run pytest`
- `uv run pyright`

If running tools directly, use `uv run ...`.

## Project overview

KXNS Hunter CLI is a penetration-testing-focused AI agent CLI for security workflows.
It supports an interactive shell UI, Web UI mode, and MCP tool loading.

## Tech stack

- Python 3.12+ (tooling configured for 3.14)
- CLI framework: Typer
- Async runtime: asyncio
- LLM framework: kosong
- MCP integration: fastmcp
- Logging: loguru
- Package management/build: uv + uv_build; PyInstaller for binaries
- Tests: pytest + pytest-asyncio; lint/format: ruff; types: pyright + ty

## Architecture overview

- **CLI entry**: `src/kxns_cli/cli.py` (Typer) parses flags (UI mode, agent spec, config, MCP)
  and routes into `KxnsCLI` in `src/kxns_cli/app.py`.
- **App/runtime setup**: `KxnsCLI.create` loads config (`src/kxns_cli/config.py`), chooses a
  model/provider (`src/kxns_cli/llm.py`), builds a `Runtime` (`src/kxns_cli/soul/agent.py`),
  loads an agent spec, restores `Context`, then constructs `KxnsSoul`.
- **Agent specs**: YAML under `src/kxns_cli/agents/` loaded by `src/kxns_cli/agentspec.py`.
  Specs can `extend` base agents, select tools by import path, and define fixed subagents.
  System prompts live alongside specs; builtin args include `KXNS_NOW`, `KXNS_WORK_DIR`,
  `KXNS_WORK_DIR_LS`, `KXNS_AGENTS_MD`, `KXNS_SKILLS` (this file is injected via
  `KXNS_AGENTS_MD`).
- **Tooling**: `src/kxns_cli/soul/toolset.py` loads tools by import path, injects dependencies,
  and runs tool calls. Built-in tools live in `src/kxns_cli/tools/` (shell, file, web, todo,
  multiagent, dmail, think, plan). MCP tools are loaded via `fastmcp`; CLI management is in
  `src/kxns_cli/mcp.py` and stored in the share dir.
- **Subagents**: `LaborMarket` in `src/kxns_cli/soul/agent.py` manages fixed and dynamic
  subagents. The Task tool (`src/kxns_cli/tools/multiagent/`) spawns them.
- **Core loop**: `src/kxns_cli/soul/kxnssoul.py` is the main agent loop. It accepts user input,
  handles slash commands (`src/kxns_cli/soul/slash.py`), appends to `Context`
  (`src/kxns_cli/soul/context.py`), calls the LLM (kosong), runs tools, and performs compaction
  (`src/kxns_cli/soul/compaction.py`) when needed.
- **Approvals**: `src/kxns_cli/soul/approval.py` mediates user approvals for tool actions; the
  soul forwards approval requests over `Wire` for UI handling.
- **UI/Wire**: `src/kxns_cli/soul/run_soul` connects `KxnsSoul` to a `Wire`
  (`src/kxns_cli/wire/`) so UI loops can stream events. UIs live in `src/kxns_cli/ui/`
  (shell/print/wire).
- **Shell UI**: `src/kxns_cli/ui/shell/` handles interactive TUI input, shell command mode,
  and slash command autocomplete; it is the default interactive experience.
- **Web UI**: `src/kxns_cli/web/` provides a browser-based chat interface backed by
  FastAPI + WebSocket, with session management and live streaming.
- **Slash commands**: Soul-level commands live in `src/kxns_cli/soul/slash.py`; shell-level
  commands live in `src/kxns_cli/ui/shell/slash.py`. The shell UI exposes both and dispatches
  based on the registry. Standard skills register `/skill:<skill-name>` and load `SKILL.md`
  as a user prompt; flow skills register `/flow:<skill-name>` and execute the embedded flow.

## Major modules and interfaces

- `src/kxns_cli/app.py`: `KxnsCLI.create(...)` and `KxnsCLI.run(...)` are the main programmatic
  entrypoints; this is what UI layers use.
- `src/kxns_cli/soul/agent.py`: `Runtime` (config, session, builtins), `Agent` (system prompt +
  toolset), and `LaborMarket` (subagent registry).
- `src/kxns_cli/soul/kxnssoul.py`: `KxnsSoul.run(...)` is the loop boundary; it emits Wire
  messages and executes tools via `KxnsToolset`.
- `src/kxns_cli/soul/context.py`: conversation history + checkpoints; used by DMail for
  checkpointed replies.
- `src/kxns_cli/soul/toolset.py`: load tools, run tool calls, bridge to MCP tools.
- `src/kxns_cli/ui/*`: shell/print frontends; they consume `Wire` messages.
- `src/kxns_cli/wire/*`: event types and transport used between soul and UI.
- `src/kxns_cli/web/*`: Web UI server, session management, and WebSocket streaming.

## Repo map

- `src/kxns_cli/agents/`: built-in agent YAML specs and prompts
- `src/kxns_cli/prompts/`: shared prompt templates
- `src/kxns_cli/soul/`: core runtime/loop, context, compaction, approvals
- `src/kxns_cli/tools/`: built-in tools
- `src/kxns_cli/ui/`: UI frontends (shell/print)
- `src/kxns_cli/web/`: Web UI server and session management
- `src/kxns_cli/wire/`: event types and transport
- `packages/kosong/`, `packages/kaos/`: workspace deps
  + Kosong is an LLM abstraction layer designed for modern AI agent applications.
    It unifies message structures, asynchronous tool orchestration, and pluggable
    chat providers so you can build agents with ease and avoid vendor lock-in.
  + PyKAOS is a lightweight Python library providing an abstraction layer for agents
    to interact with operating systems. File operations and command executions via KAOS
    can be easily switched between local environment and remote systems over SSH.
- `tests/`: test suites

## Conventions and quality

- Python >=3.12 (ty config uses 3.14); line length 100.
- Ruff handles lint + format (rules: E, F, UP, B, SIM, I); pyright + ty for type checks.
- Tests use pytest + pytest-asyncio; files are `tests/test_*.py`.
- CLI entry points: `kxns` / `kxns-cli` -> `src/kxns_cli/cli.py`.
- User config: `~/.kxns/config.toml`; logs, sessions, and MCP config live in `~/.kxns/`.

## Git commit messages

Conventional Commits format:

```
<type>(<scope>): <subject>
```

Allowed types:
`feat`, `fix`, `test`, `refactor`, `chore`, `style`, `docs`, `perf`, `build`, `ci`, `revert`.

## Versioning

The project follows a **minor-bump-only** versioning scheme (`MAJOR.MINOR.PATCH`):

- **Patch** version is always `0`. Never bump it.
- **Minor** version is bumped for any change: new features, improvements, bug fixes, etc.
- **Major** version is only changed by explicit manual decision; it stays unchanged during
  normal development.

Examples: `0.68.0` → `0.69.0` → `0.70.0`; never `0.68.1`.

This rule applies to all packages in the repo (root, `packages/*`) as well as release
and skill workflows.

## Release workflow

1. Ensure `main` is up to date (pull latest).
2. Create a release branch, e.g. `bump-0.68` or `bump-pykaos-0.5.3`.
3. Update `CHANGELOG.md`: rename `[Unreleased]` to `[0.68] - YYYY-MM-DD`.
4. Update `pyproject.toml` version.
5. Run `uv sync` to align `uv.lock`.
6. Commit the branch and open a PR.
7. Merge the PR, then switch back to `main` and pull latest.
8. Tag and push:
   - `git tag 0.68` or `git tag pykaos-0.5.3`
   - `git push --tags`
9. GitHub Actions handles the release after tags are pushed.
