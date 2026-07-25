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


CORE_TOOLS = ("python3", "bash", "nmap", "curl", "rg")


async def run_precheck(
    config: Config | None = None,
    *,
    options: PrecheckOptions | None = None,
) -> PrecheckSummary:
    """Full diagnostics with blocking failure classification for scans."""
    config = config or load_config()
    options = options or PrecheckOptions(
        require_postgres=config.blackboard.require_postgres if config.blackboard else True,
    )

    results = await run_full_diagnostics(config)
    blocking: list[DiagnosticResult] = []

    for r in results:
        if r.ok:
            continue
        name = r.name
        if (
            (
                options.require_core_tools
                and name.startswith("tool:")
                and name.removeprefix("tool:") in CORE_TOOLS
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
