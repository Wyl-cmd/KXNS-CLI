---
name: kxns-cli-help
description: Answer KXNS CLI usage, configuration, and troubleshooting questions. Use when user asks about KXNS CLI installation, setup, configuration, slash commands, keyboard shortcuts, MCP integration, providers, environment variables, how something works internally, or any questions about KXNS CLI itself.
---

# KXNS CLI Help

Help users with KXNS CLI questions by consulting local documentation and source code.

## Strategy

1. **Prefer project documentation** — read `README.md` in the project root (single source of user docs)
2. **Read local source** when the question is about internals or configuration
3. **Do not clone or fetch from external repositories** — this is a standalone local project

## Documentation

| Topic | Location |
|-------|----------|
| Installation (Kali Linux) | `README.md`, `scripts/install-kali.sh` |
| Config files | `src/kxns_cli/config.py`, `~/.kxns/config.toml` |
| Providers, models | `src/kxns_cli/llm.py`, `src/kxns_cli/auth/platforms.py` |
| Slash commands | `src/kxns_cli/soul/slash.py`, `src/kxns_cli/ui/shell/slash.py` |
| CLI flags | `src/kxns_cli/cli/__init__.py` |
| MCP | `src/kxns_cli/cli/mcp.py` |
| Agents | `src/kxns_cli/agents/` |
| Skills | `src/kxns_cli/skills/`, `.agents/skills/` |
| Wire mode | `src/kxns_cli/wire/` |

## Source Code

When answering internals questions, read files under `src/kxns_cli/` directly. Do not reference upstream Kimi/Moonshot repositories.
