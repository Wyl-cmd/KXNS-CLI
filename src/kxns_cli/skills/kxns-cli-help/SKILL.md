---
name: kxns-cli-help
description: Answer KXNS CLI usage, configuration, and troubleshooting questions. Use when user asks about KXNS CLI installation, setup, configuration, slash commands, keyboard shortcuts, MCP integration, providers, environment variables, how something works internally, or any questions about KXNS CLI itself.
---

# KXNS CLI Help

Help users with KXNS CLI questions by consulting documentation and source code.

## Strategy

1. **Prefer official documentation** for most questions
2. **Read local source** when in kxns-cli project itself, or when user is developing with kxns-cli as a library (e.g., importing from `kxns_cli` in their code)
3. **Clone and explore source** for complex internals not covered in docs - **ask user for confirmation first**

## Documentation

Base URL: `https://github.com/Wyl-cmd/kxns-cli`

Fetch documentation index to find relevant pages:

```
https://github.com/Wyl-cmd/kxns-cli
```

### Topic Mapping

| Topic | Location |
|-------|----------|
| Installation, first run | README.md |
| Config files | src/kxns_cli/config.py |
| Providers, models | src/kxns_cli/llm.py |
| Environment variables | src/kxns_cli/utils/envvar.py |
| Slash commands | src/kxns_cli/soul/slash.py |
| CLI flags | src/kxns_cli/cli/__init__.py |
| Keyboard shortcuts | src/kxns_cli/ui/shell/keyboard.py |
| MCP | src/kxns_cli/cli/mcp.py |
| Agents | src/kxns_cli/agents/ |
| Skills | src/kxns_cli/skills/ |

## Source Code

Repository: `https://github.com/Wyl-cmd/kxns-cli`

When to read source:

- In kxns-cli project directory (check `pyproject.toml` for `name = "kxns-cli"`)
- User is importing `kxns_cli` as a library in their project
- Question about internals not covered in docs (ask user before cloning)
