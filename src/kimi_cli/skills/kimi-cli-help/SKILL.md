---
name: kxns-cli-help
description: Answer KXNS CLI usage, configuration, and troubleshooting questions. Use when user asks about KXNS CLI installation, setup, configuration, slash commands, keyboard shortcuts, MCP integration, providers, environment variables, how something works internally, or any questions about KXNS CLI itself.
---

# KXNS CLI Help

Help users with KXNS CLI questions by consulting documentation and source code.

## Strategy

1. **Prefer official documentation** for most questions
2. **Read local source** when in kxns-cli project itself, or when user is developing with kxns-cli as a library (e.g., importing from `kimi_cli` in their code)
3. **Clone and explore source** for complex internals not covered in docs - **ask user for confirmation first**

## Documentation

Base URL: `https://github.com/Wyl-cmd/KXNS-CLI/`

Fetch documentation index to find relevant pages:
```
https://github.com/Wyl-cmd/KXNS-CLI/llms.txt
```

### Page URL Pattern

- English: `https://github.com/Wyl-cmd/KXNS-CLI/en/...`
- Chinese: `https://github.com/Wyl-cmd/KXNS-CLI/zh/...`

### Topic Mapping

| Topic | Page |
|-------|------|
| Installation, first run | `/en/guides/getting-started.md` |
| Config files | `/en/configuration/config-files.md` |
| Providers, models | `/en/configuration/providers.md` |
| Environment variables | `/en/configuration/env-vars.md` |
| Slash commands | `/en/reference/slash-commands.md` |
| CLI flags | `/en/reference/kxns-command.md` |
| Keyboard shortcuts | `/en/reference/keyboard.md` |
| MCP | `/en/customization/mcp.md` |
| Agents | `/en/customization/agents.md` |
| Skills | `/en/customization/skills.md` |
| FAQ | `/en/faq.md` |

## Source Code

Repository: `https://github.com/Wyl-cmd/KXNS-CLI`

When to read source:
- In kxns-cli project directory (check `pyproject.toml` for `name = "kxns-cli"`)
- User is importing `kimi_cli` as a library in their project
- Question about internals not covered in docs (ask user before cloning)
