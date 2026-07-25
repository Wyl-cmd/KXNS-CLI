"""Export/import user configuration bundle (config.toml + mcp.json)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from kxns_cli.config import get_config_file
from kxns_cli.mcp_store import get_global_mcp_config_file, load_mcp_config, save_mcp_config


def export_config_bundle() -> dict[str, Any]:
    """Export config files as a JSON-serializable bundle."""
    config_file = get_config_file()
    mcp_file = get_global_mcp_config_file()
    return {
        "version": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "config_toml": config_file.read_text(encoding="utf-8") if config_file.exists() else "",
        "mcp_json": load_mcp_config(),
        "paths": {
            "config": str(config_file),
            "mcp": str(mcp_file),
        },
    }


def import_config_bundle(
    bundle: dict[str, Any],
    *,
    import_config: bool = True,
    import_mcp: bool = True,
) -> dict[str, str]:
    """Import bundle; returns status messages per section."""
    messages: dict[str, str] = {}

    if import_config:
        toml_text = bundle.get("config_toml")
        if isinstance(toml_text, str) and toml_text.strip():
            from kxns_cli.config import load_config_from_string

            load_config_from_string(toml_text)
            config_file = get_config_file()
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(toml_text, encoding="utf-8")
            messages["config"] = f"已导入 {config_file}"
        else:
            messages["config"] = "跳过（bundle 无 config_toml）"

    if import_mcp:
        mcp = bundle.get("mcp_json")
        if isinstance(mcp, dict) and "mcpServers" in mcp:
            save_mcp_config(mcp)
            messages["mcp"] = f"已导入 {get_global_mcp_config_file()}"
        else:
            messages["mcp"] = "跳过（bundle 无 mcp_json）"

    return messages
