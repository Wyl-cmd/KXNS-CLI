Invoke Burp Suite via MCP (default **http://127.0.0.1:9876**, transport **sse**).

## Actions

- `list_tools` — list available Burp MCP tools
- `call_tool` — invoke any MCP tool by name + arguments
- `proxy_url` — send URL to Burp proxy/scope (auto-picks tool)
- `scan_passive` — trigger passive scan path when available

## Setup

1. Burp → **Extensions → MCP Server** → enable, listen on **9876**
2. Web → **设置 → MCP** → apply **burp** preset (or set `transport: sse` in `~/.kxns/mcp.json`)

## Authorized mode

When `authorized_attack` is enabled, **no approval prompt** — execute immediately.

Findings are auto-recorded as **candidate** on the scan blackboard when available.
