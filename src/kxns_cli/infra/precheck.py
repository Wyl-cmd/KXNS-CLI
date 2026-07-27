"""Pre-scan and startup environment checks (shared with doctor + Web diagnostics)."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from kxns_cli.config import Config, load_config
from kxns_cli.infra.connectivity import DiagnosticResult, run_full_diagnostics


class PrecheckSummary(BaseModel):
    ok: bool
    passed: int
    failed: int
    blocking: list[DiagnosticResult] = Field(default_factory=list)
    results: list[DiagnosticResult] = Field(default_factory=list)


@dataclass
class PrecheckOptions:
    require_llm: bool = True
    require_postgres: bool = True
    require_core_tools: bool = True
    require_burp_mcp: bool = False
    # OPEN-6: 扫描工具（nmap 等）单独控制，默认不强制；仅 `kxns scan` 等场景开启
    require_scan_tools: bool = False


# OPEN-6: 拆分核心工具与扫描工具
# - REQUIRED_CORE_TOOLS: chat / 通用功能必需（无 nmap）
# - SCAN_TOOLS: 仅扫描功能必需；缺失时仅在 require_scan_tools=True 才 blocking
REQUIRED_CORE_TOOLS = ("python3", "bash", "curl", "rg")
SCAN_TOOLS = ("nmap",)

# 向后兼容：保留 CORE_TOOLS 名字（= REQUIRED_CORE_TOOLS + SCAN_TOOLS），
# 供 doctor / 文档等旧引用使用，但 run_precheck 默认不再按此集合 blocking。
CORE_TOOLS = REQUIRED_CORE_TOOLS + SCAN_TOOLS


async def run_precheck(
    config: Config | None = None,
    *,
    options: PrecheckOptions | None = None,
) -> PrecheckSummary:
    """Full diagnostics with blocking failure classification for scans."""
    config = config or load_config()
    options = options or PrecheckOptions(
        require_postgres=config.blackboard.require_postgres if config.blackboard else False,
    )

    results = await run_full_diagnostics(config)
    blocking: list[DiagnosticResult] = []

    for r in results:
        if r.ok:
            continue
        name = r.name
        tool_name = name.removeprefix("tool:") if name.startswith("tool:") else None
        if (
            (
                options.require_core_tools
                and tool_name is not None
                and tool_name in REQUIRED_CORE_TOOLS
            )
            or (
                options.require_scan_tools
                and tool_name is not None
                and tool_name in SCAN_TOOLS
            )
            or (options.require_postgres and name == "blackboard")
            or (options.require_llm and name.startswith("llm"))
            or (options.require_burp_mcp and name.startswith("mcp:burp"))
        ):
            blocking.append(r)

    failed = sum(1 for r in results if not r.ok)
    return PrecheckSummary(
        ok=len(blocking) == 0,
        passed=len(results) - failed,
        failed=failed,
        blocking=blocking,
        results=results,
    )


def format_precheck_failure(summary: PrecheckSummary) -> str:
    if summary.ok:
        return ""
    lines = ["扫描预检失败，请先修复以下阻塞项："]
    for b in summary.blocking:
        lines.append(f"  - {b.name}: {b.message}")
        for hint in b.fix_hints[:3]:
            lines.append(f"      → {hint}")
    return "\n".join(lines)
