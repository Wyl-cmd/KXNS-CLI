"""Burp Suite MCP integration (SSE 9876)."""

from __future__ import annotations

from dataclasses import dataclass

from kxns_cli.infra.connectivity import BURP_MCP_URL, probe_burp_mcp, probe_mcp_server


@dataclass
class BurpMCPAdapter:
    """Burp MCP via PortSwigger SSE extension (default port 9876)."""

    mcp_url: str = BURP_MCP_URL
    mcp_name: str = "burp"

    async def is_available(self) -> bool:
        mcp = await probe_mcp_server(self.mcp_name)
        return mcp.ok

    async def scan_url(self, url: str) -> str:
        mcp = await probe_mcp_server(self.mcp_name)
        if mcp.ok:
            return f"Burp MCP 已连接 ({mcp.message})。使用 MCP 工具代理/扫描: {url}"
        port = probe_burp_mcp()
        if port.ok:
            return (
                f"Burp MCP 端口 {self.mcp_url} 可达，但 MCP 握手失败。"
                f'请在 mcp.json 为 burp 设置 "transport": "sse"。目标: {url}'
            )
        return (
            f"Burp MCP 未就绪。启动 Burp → Extensions → MCP Server → 监听 9876。"
            f"Web 设置 → MCP → 安装 burp 预设（{self.mcp_url}，transport=sse）"
        )
