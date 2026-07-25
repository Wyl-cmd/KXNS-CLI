from pathlib import Path
from typing import override
from uuid import UUID

from kosong.tooling import CallableTool2, ToolReturnValue
from pydantic import BaseModel, Field

from kxns_cli.scan.coordinator import current_engagement_id, current_target_id
from kxns_cli.scan.models import FindingSeverity, FindingStatus
from kxns_cli.scan.validation import validate_finding_submission
from kxns_cli.soul import wire_send
from kxns_cli.soul.agent import Runtime
from kxns_cli.tools.utils import ToolResultBuilder, load_desc
from kxns_cli.wire.types import FindingDiscovered


class Params(BaseModel):
    title: str = Field(description="Short title of the vulnerability or discovery.")
    severity: str = Field(
        description="Severity: critical, high, medium, low, or info.",
    )
    description: str = Field(description="Detailed description and evidence.")
    poc: str = Field(default="", description="Proof of concept steps or commands.")
    cwe: str | None = Field(default=None, description="CWE identifier if known.")
    cvss: float | None = Field(default=None, description="CVSS score if known.")
    status: str = Field(
        default="candidate",
        description="Finding status: candidate, confirmed, or false_positive.",
    )
    finding_id: str | None = Field(
        default=None,
        description="Existing finding UUID to update (required when confirming a candidate).",
    )


class ReportFinding(CallableTool2[Params]):
    name: str = "ReportFinding"
    description: str = load_desc(Path(__file__).parent / "report_finding.md", {})
    params: type[Params] = Params

    def __init__(self, runtime: Runtime):
        super().__init__()
        self._runtime = runtime

    @override
    async def __call__(self, params: Params) -> ToolReturnValue:
        builder = ToolResultBuilder()
        blackboard = self._runtime.blackboard
        if blackboard is None:
            return builder.error(
                "Blackboard not available. ReportFinding works during scan operations only.",
                brief="No blackboard",
            )

        engagement_id = current_engagement_id.get() or self._runtime.scan_engagement_id
        if engagement_id is None:
            return builder.error(
                "No active scan engagement.",
                brief="No engagement",
            )

        try:
            severity = FindingSeverity(params.severity.lower())
            status = FindingStatus(params.status.lower())
        except ValueError as exc:
            return builder.error(f"Invalid severity or status: {exc}", brief="Invalid params")

        strict = self._runtime.config.scan.strict_finding_validation

        ok, errors = validate_finding_submission(
            title=params.title,
            severity=severity,
            description=params.description,
            poc=params.poc,
            status=status,
        )
        if strict and not ok:
            hint = "；".join(errors)
            return builder.error(
                f"Finding rejected (anti false-positive): {hint}",
                brief="Validation failed",
            )

        if (
            status == FindingStatus.CONFIRMED
            and severity in (FindingSeverity.HIGH, FindingSeverity.CRITICAL)
            and not params.poc.strip()
        ):
            return builder.error(
                "高危/严重漏洞标记 confirmed 必须提供可复现 POC（curl/请求/步骤）",
                brief="POC required",
            )

        target_id = current_target_id.get()
        fid: UUID | None = None
        if params.finding_id:
            try:
                fid = UUID(params.finding_id.strip())
            except ValueError:
                return builder.error("Invalid finding_id UUID", brief="Invalid params")

        finding = await blackboard.upsert_finding(
            engagement_id,
            params.title,
            severity,
            target_id=target_id,
            status=status,
            description=params.description,
            poc=params.poc,
            cwe=params.cwe,
            cvss=params.cvss,
            finding_id=fid,
        )
        wire_send(
            FindingDiscovered(
                engagement_id=str(engagement_id),
                finding_id=str(finding.id),
                title=finding.title,
                severity=finding.severity.value,
                status=finding.status.value,
            )
        )
        return builder.ok(
            f"Finding recorded: {finding.id} [{finding.severity.value}] {finding.title}"
        )
