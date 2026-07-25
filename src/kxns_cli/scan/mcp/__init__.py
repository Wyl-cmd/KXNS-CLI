"""MCP adapters for swarm scan mode."""

from kxns_cli.scan.mcp.burp import BurpMCPAdapter
from kxns_cli.scan.mcp.msf import MsfMCPAdapter
from kxns_cli.scan.mcp.zap import ZapMCPAdapter

SWARM_ADAPTERS = {
    "burp": BurpMCPAdapter(),
    "zap": ZapMCPAdapter(),
    "msf": MsfMCPAdapter(),
}

__all__ = ["SWARM_ADAPTERS", "BurpMCPAdapter", "ZapMCPAdapter", "MsfMCPAdapter"]
