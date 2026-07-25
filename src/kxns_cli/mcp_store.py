"""Shared MCP configuration load/save for CLI and Web UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastmcp.mcp_config import MCPConfig

from kxns_cli.share import get_share_dir


def get_global_mcp_config_file() -> Path:
    return get_share_dir() / "mcp.json"


def load_mcp_config() -> dict[str, Any]:
    mcp_file = get_global_mcp_config_file()
    if not mcp_file.exists():
        return {"mcpServers": {}}
    try:
        config = json.loads(mcp_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in MCP config file '{mcp_file}': {exc}") from exc
    MCPConfig.model_validate(config)
    return config


def save_mcp_config(config: dict[str, Any]) -> None:
    MCPConfig.model_validate(config)
    mcp_file = get_global_mcp_config_file()
    mcp_file.parent.mkdir(parents=True, exist_ok=True)
    mcp_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def list_mcp_servers() -> dict[str, dict[str, Any]]:
    return load_mcp_config().get("mcpServers", {})


def get_mcp_server(name: str) -> dict[str, Any]:
    from kxns_cli.infra.connectivity import normalize_mcp_server_config

    servers = list_mcp_servers()
    if name not in servers:
        raise KeyError(name)
    return normalize_mcp_server_config(name, servers[name])


def upsert_mcp_server(name: str, server: dict[str, Any]) -> None:
    config = load_mcp_config()
    servers = config.setdefault("mcpServers", {})
    servers[name] = server
    save_mcp_config(config)


def remove_mcp_server(name: str) -> bool:
    config = load_mcp_config()
    servers = config.get("mcpServers", {})
    if name not in servers:
        return False
    del servers[name]
    save_mcp_config(config)
    return True
