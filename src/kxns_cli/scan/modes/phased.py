from __future__ import annotations

from pathlib import Path
from uuid import UUID

import yaml
from kaos.path import KaosPath

from kxns_cli.blackboard.store import BlackboardStore
from kxns_cli.scan.coordinator import Coordinator
from kxns_cli.utils.logging import logger

_PHASES_DIR = Path(__file__).parent.parent / "phases"


async def run_phased(
    *,
    engagement_id: UUID,
    blackboard: BlackboardStore,
    coordinator: Coordinator,
    work_dir: KaosPath,
) -> int:
    """Run 22-phase pentest pipeline from YAML definitions."""
    phases_file = _PHASES_DIR / "phases.yaml"
    if not phases_file.exists():
        logger.warning("Phased mode: phases.yaml not found at {path}", path=phases_file)
        return 0

    data = yaml.safe_load(phases_file.read_text(encoding="utf-8")) or {}
    phases = data.get("phases", [])
    jobs_run = 0

    for phase in phases:
        name = phase.get("name", "unknown")
        prompt_template = phase.get("prompt", "")
        prompt = prompt_template.format(engagement_id=str(engagement_id))
        job = await blackboard.create_job(engagement_id, phase=f"phased_{name}", prompt=prompt)
        await coordinator.run_jobs([job], engagement_id)
        jobs_run += 1

    return jobs_run
