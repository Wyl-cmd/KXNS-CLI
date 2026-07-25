"""Run Kali pentest tools with structured output parsing."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import override

from kosong.tooling import CallableTool2, ToolReturnValue
from pydantic import BaseModel, Field

from kxns_cli.scan.coordinator import current_engagement_id, current_target_id
from kxns_cli.scan.models import FindingSeverity, FindingStatus
from kxns_cli.soul.agent import Runtime
from kxns_cli.soul.approval import Approval
from kxns_cli.tools.kali.base import KALI_ADAPTERS
from kxns_cli.tools.kali.registry import discover_installed_tools, is_tool_available
from kxns_cli.tools.utils import ToolRejectedError, ToolResultBuilder, load_desc
from kxns_cli.utils.subprocess_env import get_clean_env


class Params(BaseModel):
    tool: str = Field(
        description=(
            "Kali tool name, e.g. nmap, nuclei, sqlmap, ffuf. "
            f"Structured parsers: {', '.join(sorted(KALI_ADAPTERS))}. "
            "Any other tool on PATH can be run with extra_args."
        ),
    )
    target: str = Field(description="Target URL, host, IP, or domain.")
    extra_args: str = Field(
        default="",
        description="Additional CLI arguments appended to the built command.",
    )
    timeout: int = Field(default=120, ge=10, le=600, description="Timeout in seconds.")


class RunKali(CallableTool2[Params]):
    name: str = "RunKali"
    params: type[Params] = Params

    def __init__(self, approval: Approval, runtime: Runtime):
        installed = discover_installed_tools()
        hint = ", ".join(installed[:30])
        if len(installed) > 30:
            hint += f", ... (+{len(installed) - 30} more)"
        super().__init__(
            description=load_desc(
                Path(__file__).parent / "run_kali.md",
                {"INSTALLED_TOOLS": hint or "none detected (run on Kali Linux)"},
            )
        )
        self._approval = approval
        self._runtime = runtime

    @override
    async def __call__(self, params: Params) -> ToolReturnValue:
        builder = ToolResultBuilder()
        tool = params.tool.strip().lower()
        target = params.target.strip()
        if not tool or not target:
            return builder.error("tool and target are required.", brief="Missing params")

        adapter = KALI_ADAPTERS.get(tool)
        if adapter is not None:
            command = adapter.build_command(target)
        elif is_tool_available(tool):
            command = f"{tool} {params.extra_args} {target}".strip()
        else:
            available = discover_installed_tools()
            return builder.error(
                f"Tool '{tool}' not found on PATH. "
                f"Install on Kali or pick from: {', '.join(available[:20])}",
                brief="Tool not found",
            )

        if params.extra_args and adapter is not None:
            command = f"{command} {params.extra_args}"

        if not await self._approval.request(
            self.name,
            "run kali tool",
            f"Run `{command}`",
        ):
            return ToolRejectedError()

        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=get_clean_env(),
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(params.timeout),
            )
        except TimeoutError:
            if proc is not None:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(proc.wait(), timeout=5)
            return builder.error(f"Command timed out after {params.timeout}s", brief="Timeout")

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        exit_code = proc.returncode or 0

        builder.write(f"$ {command}\n\n")
        if stdout:
            builder.write(stdout)
        if stderr:
            builder.write(f"\n[stderr]\n{stderr}")

        parsed_summary = ""
        if adapter is not None:
            parsed = adapter.parse_output(stdout, stderr, target)
            if parsed:
                parsed_summary = f"\n\n--- Parsed {len(parsed)} item(s) ---\n"
                for item in parsed[:15]:
                    parsed_summary += f"- [{item.get('severity', '?')}] {item.get('title', '?')}\n"
                if len(parsed) > 15:
                    parsed_summary += f"... and {len(parsed) - 15} more\n"
                auto = self._runtime.config.scan.auto_record_kali_findings
                if auto and self._runtime.blackboard is not None:
                    recorded = await self._auto_record(parsed, tool)
                    parsed_summary += f"\nAuto-recorded {recorded} candidate(s) on blackboard.\n"
                else:
                    parsed_summary += (
                        "\nUse ReportFinding with status=candidate for each verified issue. "
                        "Never report confirmed without reproducible POC."
                    )
                builder.write(parsed_summary)

        if exit_code == 0:
            return builder.ok(f"RunKali {tool} completed (exit 0)")
        return builder.ok(
            f"RunKali {tool} finished with exit code {exit_code}. Review output.",
            brief=f"exit {exit_code}",
        )

    async def _auto_record(self, parsed: list[dict], tool: str) -> int:
        bb = self._runtime.blackboard
        if bb is None:
            return 0
        eid = current_engagement_id.get() or self._runtime.scan_engagement_id
        if eid is None:
            return 0
        tid = current_target_id.get()
        count = 0
        for item in parsed:
            sev_raw = str(item.get("severity", "info")).lower()
            try:
                sev = FindingSeverity(sev_raw)
            except ValueError:
                sev = FindingSeverity.INFO
            # Scanner auto-record: cap to info/medium — confirmed requires manual verify
            if sev in (FindingSeverity.HIGH, FindingSeverity.CRITICAL):
                sev = FindingSeverity.MEDIUM
            elif sev == FindingSeverity.MEDIUM:
                sev = FindingSeverity.INFO
            try:
                status = FindingStatus(str(item.get("status", "candidate")).lower())
            except ValueError:
                status = FindingStatus.CANDIDATE
            await bb.upsert_finding(
                eid,
                str(item.get("title", f"{tool} finding")),
                sev,
                target_id=tid,
                status=status,
                description=str(item.get("description", ""))[:4000],
                poc=str(item.get("poc", ""))[:4000],
                metadata={"source": "RunKali", "tool": tool},
            )
            count += 1
        return count
