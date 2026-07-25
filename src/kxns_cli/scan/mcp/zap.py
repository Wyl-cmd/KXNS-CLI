"""OWASP ZAP MCP / API integration for swarm scan mode.

Requires ZAP running with MCP bridge. Setup:
  - Launch ZAP: zaproxy -daemon -host 127.0.0.1 -port 8080
  - Web settings -> MCP -> install "zap" preset
  - Defaults: http://127.0.0.1:8080/JSON/ transport: sse
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kxns_cli.infra.connectivity import probe_mcp_server


@dataclass
class ZapMCPAdapter:
    api_url: str = "http://127.0.0.1:8080/JSON/"
    mcp_name: str = "zap"

    async def is_available(self) -> bool:
        """Check if ZAP MCP is reachable via the configured MCP server."""
        mcp = await probe_mcp_server(self.mcp_name)
        return mcp.ok

    async def scan_url(self, url: str) -> str:
        """Launch spider + active scan on target via ZAP MCP tools."""
        mcp = await probe_mcp_server(self.mcp_name)
        if mcp.ok:
            return (
                f"ZAP MCP connected. Use MCP tools: "
                f"spider({url}) -> ascan({url}) -> alerts() for findings."
            )
        return (
            f"ZAP not ready. Start zaproxy and install 'zap' MCP preset "
            f"(Web settings -> MCP). Default API: {self.api_url}"
        )

    async def run_resource(self, target: str) -> str:
        """Run ZAP on a named resource (URL or engagement ID)."""
        return await self.scan_url(target)


@dataclass
class ZapConfig:
    """ZAP connection defaults — override via environment or config."""

    host: str = field(default_factory=lambda: _env("ZAP_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_env("ZAP_PORT", "8080")))
    apikey: str = field(default_factory=lambda: _env("ZAP_API_KEY", ""))


def _env(key: str, fallback: str) -> str:
    import os

    return os.environ.get(key, fallback)
