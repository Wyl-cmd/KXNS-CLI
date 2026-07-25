from __future__ import annotations

from uuid import UUID

from kxns_cli.blackboard.store import BlackboardStore
from kxns_cli.scan.coordinator import Coordinator
from kxns_cli.scan.mcp import SWARM_ADAPTERS
from kxns_cli.utils.logging import logger


async def run_swarm(
    *,
    engagement_id: UUID,
    blackboard: BlackboardStore,
    coordinator: Coordinator,
) -> int:
    """Swarm mode: delegate to Burp/ZAP/MSF agents via MCP (Phase 3)."""
    jobs = []
    for agent, adapter in SWARM_ADAPTERS.items():
        hint = ""
        if hasattr(adapter, "scan_url"):
            hint = await adapter.scan_url(str(engagement_id))  # type: ignore[attr-defined]
        elif hasattr(adapter, "run_resource"):
            hint = await adapter.run_resource(f"scan_{engagement_id}")  # type: ignore[attr-defined]
        prompt = (
            f"Swarm agent '{agent}': scan engagement {engagement_id}. "
            f"Adapter status: {hint}. "
            "If MCP tools for this agent are configured, use them. "
            "Otherwise report that the agent is not available and suggest MCP setup."
        )
        jobs.append(
            await blackboard.create_job(engagement_id, phase=f"swarm_{agent}", prompt=prompt)
        )
    if jobs:
        await coordinator.run_jobs(jobs, engagement_id)
    logger.info("Swarm mode: dispatched {n} agent jobs", n=len(jobs))
    return len(jobs)
