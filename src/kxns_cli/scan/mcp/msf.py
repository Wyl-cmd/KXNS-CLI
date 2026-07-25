"""Metasploit MCP / RPC integration for swarm scan mode.

Requires MSF RPC or MCP bridge. Setup:
  - Start MSF RPC: msfrpcd -U kxns -P kxns -p 55553 -a 127.0.0.1
  - OR install "msf" MCP preset (Web settings -> MCP)
  - Defaults: http://127.0.0.1:55553/ transport: sse
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kxns_cli.infra.connectivity import probe_mcp_server


@dataclass
class MsfMCPAdapter:
    rpc_url: str = "http://127.0.0.1:55553/"
    mcp_name: str = "msf"

    async def is_available(self) -> bool:
        """Check if MSF MCP/RPC is reachable."""
        mcp = await probe_mcp_server(self.mcp_name)
        return mcp.ok

    async def scan_url(self, url: str) -> str:
        """Search MSF modules and suggest exploits for target context."""
        mcp = await probe_mcp_server(self.mcp_name)
        if mcp.ok:
            return (
                f"MSF MCP connected. Use MCP tools: "
                f"search('exploit') -> info(result) -> run(module, target={url}) "
                f"for module-based exploitation."
            )
        return (
            "MSF MCP not ready. Install 'msf' MCP preset "
            "(Web settings -> MCP) or start msfrpcd bridge."
        )

    async def run_resource(self, target: str) -> str:
        """Run MSF modules against a named resource (host or engagement ID)."""
        return await self.scan_url(target)


@dataclass
class MsfConfig:
    """MSF connection defaults — override via environment or config."""

    host: str = field(default_factory=lambda: _env("MSF_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_env("MSF_RPC_PORT", "55553")))
    user: str = field(default_factory=lambda: _env("MSF_USER", "kxns"))
    password: str = field(default_factory=lambda: _env("MSF_PASS", "kxns"))


def _env(key: str, fallback: str) -> str:
    import os

    return os.environ.get(key, fallback)
