"""Built-in MCP server presets for pentest workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from kxns_cli.infra.connectivity import BURP_MCP_URL, burp_mcp_server_config
from kxns_cli.mcp_store import list_mcp_servers, upsert_mcp_server


@dataclass(frozen=True)
class MCPPreset:
    id: str
    name: str
    description: str
    transport: Literal["stdio", "http"]
    command: str | None = None
    url: str | None = None
    env: dict[str, str] | None = None
    category: str = "security"


MCP_PRESETS: dict[str, MCPPreset] = {
    "burp": MCPPreset(
        id="burp",
        name="burp",
        description="Burp Suite MCP 扩展（SSE 9876，PortSwigger MCP Server）",
        transport="http",
        url=BURP_MCP_URL,
        category="proxy",
    ),
    "burp-rest": MCPPreset(
        id="burp-rest",
        name="burp-rest",
        description="Burp Suite REST API（HTTP 1337，需 Pro + REST 扩展）",
        transport="http",
        url="http://127.0.0.1:1337/",
        category="proxy",
    ),
    "zap": MCPPreset(
        id="zap",
        name="zap",
        description="OWASP ZAP API（需 zaproxy 运行且开启 API）",
        transport="http",
        url="http://127.0.0.1:8080/JSON/",
        category="scanner",
    ),
    "msf": MCPPreset(
        id="msf",
        name="msf",
        description="Metasploit RPC（需 msfrpcd 或 msf MCP 桥接）",
        transport="http",
        url="http://127.0.0.1:55553/",
        category="exploit",
    ),
    "filesystem": MCPPreset(
        id="filesystem",
        name="filesystem",
        description="本地文件系统 MCP（读写工作目录）",
        transport="stdio",
        command="npx -y @modelcontextprotocol/server-filesystem /tmp/kxns-work",
        category="utility",
    ),
    "browser": MCPPreset(
        id="browser",
        name="browser",
        description="Playwright 浏览器自动化 MCP",
        transport="stdio",
        command="npx -y @playwright/mcp@latest",
        category="utility",
    ),
}


def list_presets() -> list[dict[str, Any]]:
    installed = set(list_mcp_servers())
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "transport": p.transport,
            "command": p.command,
            "url": p.url,
            "category": p.category,
            "installed": p.name in installed,
        }
        for p in MCP_PRESETS.values()
    ]


def apply_preset(preset_id: str, *, overwrite: bool = False) -> dict[str, Any]:
    preset = MCP_PRESETS.get(preset_id)
    if preset is None:
        raise KeyError(preset_id)

    existing = list_mcp_servers()
    if preset.name in existing and not overwrite:
        return {
            "applied": False,
            "name": preset.name,
            "message": "已存在，跳过（用 overwrite=true 覆盖）",
        }

    if preset.transport == "http":
        if not preset.url:
            raise ValueError("HTTP preset missing url")
        if preset.id == "burp":
            server = burp_mcp_server_config()
        else:
            server = {"url": preset.url}
    else:
        if not preset.command:
            raise ValueError("stdio preset missing command")
        server = {"command": preset.command.split()}
        if preset.env:
            server["env"] = preset.env

    upsert_mcp_server(preset.name, server)
    return {"applied": True, "name": preset.name, "message": f"已安装 MCP 预设: {preset.name}"}


def apply_all_security_presets(*, overwrite: bool = False) -> list[dict[str, Any]]:
    """Install burp (9876 SSE), zap, msf presets."""
    results: list[dict[str, Any]] = []
    for pid in ("burp", "zap", "msf"):
        try:
            results.append(apply_preset(pid, overwrite=overwrite))
        except KeyError:
            continue
    return results
