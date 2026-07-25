"""Burp Suite MCP attack bridge — proxy/repeater/intruder via MCP (port 9876, SSE)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, override

from kosong.tooling import CallableTool2, ToolReturnValue
from pydantic import BaseModel, Field

from kxns_cli.scan.coordinator import current_engagement_id, current_target_id
from kxns_cli.scan.models import FindingSeverity, FindingStatus
from kxns_cli.soul.agent import Runtime
from kxns_cli.soul.approval import Approval
from kxns_cli.tools.burp.burp_tools import BURP_ACTION_TOOL_CANDIDATES
from kxns_cli.tools.utils import ToolRejectedError, ToolResultBuilder, load_desc

_MCP_TIMEOUT = 30.0


class Params(BaseModel):
    action: str = Field(
        default="list_tools",
        description="MCP action: list_tools, call_tool, proxy_url, scan_passive",
    )
    tool_name: str = Field(default="", description="Burp MCP tool name when action=call_tool")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON arguments for call_tool",
    )
    url: str = Field(default="", description="Target URL for proxy_url / scan_passive")
    mcp_server: str = Field(default="burp", description="MCP server name in mcp.json")


class BurpMCP(CallableTool2[Params]):
    name: str = "BurpMCP"
    params: type[Params] = Params

    def __init__(self, approval: Approval, runtime: Runtime):
        super().__init__(
            description=load_desc(Path(__file__).parent / "mcp_attack.md", {}),
        )
        self._approval = approval
        self._runtime = runtime

    @override
    async def __call__(self, params: Params) -> ToolReturnValue:
        builder = ToolResultBuilder()
        action = params.action.strip().lower()

        if not await self._approval.request(
            self.name,
            "burp attack",
            f"Burp MCP {action} on {params.url or params.tool_name}",
        ):
            return ToolRejectedError()

        try:
            from kxns_cli.mcp_store import get_mcp_server

            server = get_mcp_server(params.mcp_server)
        except KeyError:
            return builder.error(
                f"MCP '{params.mcp_server}' not configured. Web → MCP → burp 预设 (9876, sse)",
                brief="No burp MCP",
            )

        import fastmcp

        try:
            client = fastmcp.Client({"mcpServers": {params.mcp_server: server}})
            async with client:
                tools = await asyncio.wait_for(client.list_tools(), timeout=_MCP_TIMEOUT)
                tool_names = [t.name for t in tools]

                if action == "list_tools":
                    builder.write("Burp MCP tools:\n" + "\n".join(f"- {n}" for n in tool_names))
                    return builder.ok(f"{len(tool_names)} tools")

                if action == "call_tool":
                    if not params.tool_name:
                        return builder.error("tool_name required for call_tool")
                    result = await asyncio.wait_for(
                        client.call_tool(params.tool_name, params.arguments),
                        timeout=_MCP_TIMEOUT,
                    )
                    text = str(result)
                    builder.write(text)
                    await self._maybe_record(params.url, f"Burp MCP {params.tool_name}", text)
                    return builder.ok("Burp MCP call completed")

                if action in ("proxy_url", "scan_passive", "repeater", "intruder"):
                    if not params.url and action in ("proxy_url", "scan_passive"):
                        return builder.error("url required")
                    candidates = BURP_ACTION_TOOL_CANDIDATES.get(action, [])
                    invoked = False
                    for name in candidates:
                        if name not in tool_names:
                            continue
                        args: dict[str, Any] = {"url": params.url} if params.url else {}
                        if name == "send_http_request" and params.url:
                            from urllib.parse import urlparse

                            host = urlparse(params.url).netloc or params.url
                            args = {
                                "request": (
                                    f"GET {params.url} HTTP/1.1\r\n"
                                    f"Host: {host}\r\n"
                                    "Connection: close\r\n\r\n"
                                )
                            }
                        await asyncio.wait_for(
                            client.call_tool(name, args),
                            timeout=_MCP_TIMEOUT,
                        )
                        builder.write(f"Invoked {name}({args})\n")
                        invoked = True
                        break
                    if not invoked:
                        builder.write(
                            f"Available tools: {tool_names}\n"
                            "Use action=call_tool with tool_name from list."
                        )
                        return builder.ok("Listed tools; no auto-match", brief="manual call_tool")
                    await self._maybe_record(params.url, f"Burp {action}", params.url)
                    return builder.ok(f"Burp {action} dispatched")

                return builder.error(f"Unknown action: {action}")
        except TimeoutError:
            return builder.error("Burp MCP timeout (30s)", brief="Timeout")
        except Exception as exc:
            return builder.error(f"Burp MCP failed: {exc}", brief="Error")

    async def _maybe_record(self, url: str, title: str, detail: str) -> None:
        bb = self._runtime.blackboard
        if bb is None:
            return
        eid = current_engagement_id.get() or self._runtime.scan_engagement_id
        if eid is None:
            return
        await bb.upsert_finding(
            eid,
            title,
            FindingSeverity.INFO,
            target_id=current_target_id.get(),
            status=FindingStatus.CANDIDATE,
            description=detail[:2000],
            poc=url or detail[:500],
        )
