from __future__ import annotations

from uuid import UUID

from kxns_cli.blackboard.store import BlackboardStore
from kxns_cli.scan.coordinator import Coordinator
from kxns_cli.scan.models import ScanConfig, ScanJob
from kxns_cli.utils.logging import logger

_HUNT_CONTEXT_BLOCK = """
## Hunt context (from user request — follow this)
{hunt_context}
"""

WILDCARD_RECON_PROMPT = """\
Perform wildcard reconnaissance on target: {target}
{hunt_context_block}

Steps:
1. Enumerate subdomains (subfinder/amass/dig) — cap at ~30 live hosts unless user asked for full scope.
2. Probe live hosts with httpx or curl; fingerprint stack (server, framework, cookies, API paths).
3. Identify high-value entry points: /login, /api, /admin, upload, OAuth, GraphQL, swagger.
4. ReportFinding ONLY for actionable exposure (exposed admin, debug API, default creds hint) — severity info/low.
5. Record discovered live URLs as assets (severity info, title "Discovered asset").

Quality: no version-banner-only or missing-header noise. Work autonomously.
"""

WILDCARD_PROBE_PROMPT = """\
Deep probe target: {target}
{hunt_context_block}

Perform targeted testing (not blind full scan):
- Directory/file fuzzing on interesting paths (ffuf/gobuster) — focus admin, api, backup, .git
- Parameter discovery on forms and API endpoints
- Manual curl tests for auth bypass, IDOR, SQLi/XSS/SSRF on mapped params
- nuclei: use tags matching focus areas only; triage hits manually before ReportFinding

ReportFinding rules:
- candidate for tool hits pending verification
- confirmed only after reproducible HTTP/curl POC
- Do NOT mark high/critical without proof

Work autonomously. Prefer depth on one host over shallow scans on many.
"""


def _hunt_context_block(scan_config: ScanConfig) -> str:
    brief = scan_config.hunt_brief.strip()
    if not brief:
        return ""
    return _HUNT_CONTEXT_BLOCK.format(hunt_context=brief)


async def run_wildcard(
    *,
    engagement_id: UUID,
    root_url: str,
    blackboard: BlackboardStore,
    coordinator: Coordinator,
    scan_config: ScanConfig,
) -> list[UUID]:
    """Wildcard mode: subdomain enum -> sub-task tree -> parallel jobs."""
    ctx_block = _hunt_context_block(scan_config)
    root_target = await blackboard.add_target(engagement_id, root_url, kind="root", depth=0)
    targets_created = [root_target.id]

    recon_job = await blackboard.create_job(
        engagement_id,
        phase="wildcard_recon",
        prompt=WILDCARD_RECON_PROMPT.format(target=root_url, hunt_context_block=ctx_block),
        target_id=root_target.id,
    )
    await coordinator.run_jobs([recon_job], engagement_id)

    all_targets = await blackboard.list_targets(engagement_id)
    probe_jobs: list[ScanJob] = []
    for target in all_targets:
        if target.depth > scan_config.max_depth:
            continue
        if target.value == root_url:
            continue
        child = await blackboard.add_target(
            engagement_id,
            target.value,
            parent_id=root_target.id,
            kind="url",
            depth=target.depth + 1,
        )
        targets_created.append(child.id)
        probe_jobs.append(
            await blackboard.create_job(
                engagement_id,
                phase="wildcard_probe",
                prompt=WILDCARD_PROBE_PROMPT.format(
                    target=target.value,
                    hunt_context_block=ctx_block,
                ),
                target_id=child.id,
            )
        )

    if probe_jobs:
        logger.info("Wildcard: running {n} probe jobs", n=len(probe_jobs))
        await coordinator.run_jobs(probe_jobs, engagement_id)

    return targets_created
