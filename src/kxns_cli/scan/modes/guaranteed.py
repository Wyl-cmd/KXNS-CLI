"""Guaranteed pipeline: evaluate -> confirm -> POC."""

from __future__ import annotations

from uuid import UUID

from kxns_cli.blackboard.store import BlackboardStore
from kxns_cli.scan.coordinator import Coordinator
from kxns_cli.scan.models import FindingStatus, ScanConfig, ScanJob
from kxns_cli.scan.validation import parse_evaluate_confidence

EVALUATE_PROMPT = """\
Evaluate this candidate vulnerability finding:

Title: {title}
Severity: {severity}
Description: {description}
POC: {poc}

Reject (CONFIDENCE: 0.0) if:
- Only scanner template match without unique impact on this target
- Missing security headers, version disclosure, or generic info leaks
- Cannot explain concrete attacker impact (data access, auth bypass, RCE, etc.)

Accept only if evidence suggests real exploitable issue. Respond CONFIDENCE: <0.0-1.0> and reasoning.
"""

CONFIRM_PROMPT = """\
Confirm vulnerability with minimal reproducible POC for:

Title: {title}
Target context: {description}

Steps:
1. Re-run the exact curl/HTTP request that proves the issue (include method, URL, headers, body).
2. If not reproducible, mark false positive — do NOT call ReportFinding confirmed.
3. If confirmed, ReportFinding status=confirmed, finding_id="{finding_id}", with full POC in tool call.

No destructive payloads. No brute-force unless clearly in scope.
"""

POC_REPORT_PROMPT = """\
Generate bounty-ready POC report section for confirmed finding:

Title: {title}
Severity: {severity}
Description: {description}

Output: Impact, Steps to Reproduce, Remediation (markdown). Keep factual; do not exaggerate.
"""


async def run_guaranteed(
    *,
    engagement_id: UUID,
    blackboard: BlackboardStore,
    coordinator: Coordinator,
    scan_config: ScanConfig,
) -> int:
    """Guaranteed pipeline: evaluate -> confirm -> POC."""
    candidates = await blackboard.list_findings(
        engagement_id,
        severities=scan_config.severity_filter,
        statuses=[FindingStatus.CANDIDATE],
    )
    if not candidates:
        return 0

    confirmed_count = 0
    jobs: list[ScanJob] = []
    confidence_min = coordinator.config.scan.evaluate_confidence_min

    for finding in candidates:
        jobs.append(
            await blackboard.create_job(
                engagement_id,
                phase="guaranteed_evaluate",
                prompt=EVALUATE_PROMPT.format(
                    title=finding.title,
                    severity=finding.severity.value,
                    description=finding.description,
                    poc=finding.poc,
                ),
            )
        )

    evaluate_summaries = await coordinator.run_jobs(jobs, engagement_id)

    for finding, summary in zip(candidates, evaluate_summaries, strict=False):
        confidence = parse_evaluate_confidence(summary)
        if confidence is not None and confidence < confidence_min:
            await blackboard.upsert_finding(
                engagement_id,
                finding.title,
                finding.severity,
                finding_id=finding.id,
                status=FindingStatus.FALSE_POSITIVE,
                description=f"{finding.description}\n\n[evaluate confidence={confidence:.2f}]",
                poc=finding.poc,
                confidence=confidence,
            )
            continue

        confirm_job = await blackboard.create_job(
            engagement_id,
            phase="guaranteed_confirm",
            prompt=CONFIRM_PROMPT.format(
                title=finding.title,
                description=finding.description,
                finding_id=str(finding.id),
            ),
        )
        await coordinator.run_jobs([confirm_job], engagement_id)

        updated = await blackboard.list_findings(engagement_id, statuses=[FindingStatus.CONFIRMED])
        is_confirmed = any(u.id == finding.id for u in updated)
        if not is_confirmed and finding.severity in scan_config.severity_filter:
            await blackboard.upsert_finding(
                engagement_id,
                finding.title,
                finding.severity,
                finding_id=finding.id,
                status=FindingStatus.FALSE_POSITIVE,
                description=finding.description,
                poc=finding.poc,
            )
            continue

        if is_confirmed:
            confirmed_count += 1
            poc_job = await blackboard.create_job(
                engagement_id,
                phase="guaranteed_poc",
                prompt=POC_REPORT_PROMPT.format(
                    title=finding.title,
                    severity=finding.severity.value,
                    description=finding.description,
                ),
            )
            await coordinator.run_jobs([poc_job], engagement_id)

    return confirmed_count
