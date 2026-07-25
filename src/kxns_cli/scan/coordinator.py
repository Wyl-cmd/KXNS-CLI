from __future__ import annotations

import asyncio
import contextlib
import time
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from kaos.path import KaosPath

from kxns_cli.agentspec import get_agents_dir
from kxns_cli.app import KxnsCLI
from kxns_cli.blackboard.store import BlackboardStore
from kxns_cli.config import Config
from kxns_cli.infra.redis import RedisRateLimiter
from kxns_cli.scan.models import FindingStatus, JobStatus, ScanJob
from kxns_cli.session import Session
from kxns_cli.soul import wire_send
from kxns_cli.utils.logging import logger
from kxns_cli.wire.types import ScanJobBegin, ScanJobEnd

SCAN_AGENT_FILE = get_agents_dir() / "scan" / "agent.yaml"
SCAN_WORKER_FILE = get_agents_dir() / "scan" / "worker.yaml"

current_engagement_id: ContextVar[UUID | None] = ContextVar("current_engagement_id", default=None)
current_target_id: ContextVar[UUID | None] = ContextVar("current_target_id", default=None)


@dataclass(slots=True)
class Coordinator:
    """Async job scheduler for scan orchestration."""

    config: Config
    blackboard: BlackboardStore
    work_dir: KaosPath
    yolo: bool = True
    max_concurrency: int = 4
    rate_limiter: RedisRateLimiter | None = None

    async def run_jobs(self, jobs: list[ScanJob], engagement_id: UUID) -> list[str]:
        if not jobs:
            return []
        sem = asyncio.Semaphore(self.max_concurrency)
        summaries: list[str] = []
        limiter = self.rate_limiter
        if limiter is None and self.config.scan.redis_enabled:
            limiter = RedisRateLimiter(
                url=self.config.scan.redis_url,
                max_slots=self.config.scan.redis_max_slots,
            )
            await limiter.connect()
            self.rate_limiter = limiter

        async def _run_one(job: ScanJob) -> None:
            async with sem:
                acquired = True
                if limiter is not None:
                    acquired = await limiter.acquire()
                try:
                    if not acquired:
                        summary = f"SKIPPED (rate limit): {job.phase}"
                        await self.blackboard.update_job(
                            job.id, status=JobStatus.FAILED, error="rate limit timeout"
                        )
                    else:
                        summary = await self._execute_job(job, engagement_id)
                finally:
                    if limiter is not None and acquired:
                        await limiter.release()
                summaries.append(summary)

        await asyncio.gather(*[_run_one(job) for job in jobs])
        return summaries

    async def _execute_job(self, job: ScanJob, engagement_id: UUID) -> str:
        await self.blackboard.update_job(job.id, status=JobStatus.RUNNING)
        wire_send(
            ScanJobBegin(
                engagement_id=str(engagement_id),
                job_id=str(job.id),
                phase=job.phase,
                target_id=str(job.target_id) if job.target_id else None,
            )
        )
        from kxns_cli.wire.types import ScanRunning

        wire_send(
            ScanRunning(
                engagement_id=str(engagement_id),
                phase=job.phase,
                target=str(job.target_id) if job.target_id else None,
            )
        )
        token_eng = current_engagement_id.set(engagement_id)
        token_tgt = current_target_id.set(job.target_id)
        try:
            summary = await self._run_soul_prompt(job.prompt, engagement_id, job)
            await self.blackboard.update_job(
                job.id, status=JobStatus.COMPLETED, result_summary=summary[:4000]
            )
            wire_send(
                ScanJobEnd(
                    engagement_id=str(engagement_id),
                    job_id=str(job.id),
                    phase=job.phase,
                    success=True,
                    summary=summary[:500],
                )
            )
            return summary
        except Exception as exc:
            logger.exception("Scan job failed: {job_id}", job_id=job.id)
            await self.blackboard.update_job(job.id, status=JobStatus.FAILED, error=str(exc))
            wire_send(
                ScanJobEnd(
                    engagement_id=str(engagement_id),
                    job_id=str(job.id),
                    phase=job.phase,
                    success=False,
                    summary=str(exc),
                )
            )
            return f"FAILED: {exc}"
        finally:
            current_engagement_id.reset(token_eng)
            current_target_id.reset(token_tgt)

    async def _enrich_prompt(self, prompt: str, engagement_id: UUID) -> str:
        if not self.config.scan.prompt_enrichment_enabled:
            return prompt
        findings = await self.blackboard.list_findings(
            engagement_id,
            statuses=[FindingStatus.CANDIDATE, FindingStatus.CONFIRMED],
        )
        if not findings:
            return prompt
        lines = ["Prior findings on blackboard (avoid duplicates, build on these):"]
        for f in findings[:8]:
            lines.append(f"- [{f.status.value}/{f.severity.value}] {f.title}")
        header = "\n\n--- Scan context ---\n" + "\n".join(lines) + "\n---\n\n"
        return header + prompt

    async def _run_soul_prompt(self, prompt: str, engagement_id: UUID, job: ScanJob) -> str:
        enriched = await self._enrich_prompt(prompt, engagement_id)
        session = await Session.create(self.work_dir)
        agent_file = SCAN_WORKER_FILE if SCAN_WORKER_FILE.exists() else SCAN_AGENT_FILE

        mcp_configs: list[dict] | None = None
        try:
            from kxns_cli.mcp_store import load_mcp_config

            raw = load_mcp_config()
            if raw.get("mcpServers"):
                mcp_configs = [raw]
        except (ValueError, OSError) as exc:
            logger.warning("Scan worker: MCP config not loaded: {e}", e=exc)

        kxns = await KxnsCLI.create(
            session,
            config=self.config,
            yolo=self.yolo,
            agent_file=agent_file,
            mcp_configs=mcp_configs,
            max_steps_per_turn=self.config.scan.scan_max_steps_per_turn,
            max_retries_per_step=min(2, self.config.loop_control.max_retries_per_step),
            llm_request_timeout=float(self.config.llm_client.scan_request_timeout_seconds),
        )
        kxns._runtime.blackboard = self.blackboard
        kxns._runtime.scan_engagement_id = current_engagement_id.get()

        cancel = asyncio.Event()
        final_text: list[str] = []
        from kxns_cli.wire.types import ScanRunning, StepBegin, TextPart, TurnEnd

        job_timeout = float(self.config.scan.job_timeout_seconds)
        stall_seconds = float(self.config.scan.job_stall_seconds)
        heartbeat_interval = float(self.config.scan.heartbeat_interval_seconds)
        last_activity = time.monotonic()
        stall_triggered = False
        step_count = 0
        started = time.monotonic()
        phase = job.phase
        target_ref = str(job.target_id) if job.target_id else None

        def _emit_heartbeat(detail: str | None = None) -> None:
            wire_send(
                ScanRunning(
                    engagement_id=str(engagement_id),
                    phase=phase,
                    target=target_ref,
                    step=step_count if step_count > 0 else None,
                    elapsed_seconds=int(time.monotonic() - started),
                    detail=detail,
                )
            )

        async def _consume_soul() -> None:
            nonlocal last_activity, step_count
            async for msg in kxns.run(enriched, cancel):
                last_activity = time.monotonic()
                if isinstance(msg, StepBegin):
                    step_count = msg.n
                    _emit_heartbeat(f"agent step {msg.n}")
                elif isinstance(msg, TextPart):
                    final_text.append(msg.text)
                elif isinstance(msg, TurnEnd):
                    break

        async def _heartbeat_loop() -> None:
            while not cancel.is_set():
                await asyncio.sleep(heartbeat_interval)
                if cancel.is_set():
                    return
                detail = (
                    f"step {step_count} in progress"
                    if step_count > 0
                    else "waiting for LLM/tools..."
                )
                _emit_heartbeat(detail)

        async def _stall_watcher() -> None:
            nonlocal stall_triggered
            while not cancel.is_set():
                await asyncio.sleep(10)
                if time.monotonic() - last_activity > stall_seconds:
                    logger.warning("Scan job stalled (no output for {s}s)", s=int(stall_seconds))
                    stall_triggered = True
                    cancel.set()
                    return

        consume_task = asyncio.create_task(_consume_soul())
        watcher_task = asyncio.create_task(_stall_watcher())
        heartbeat_task = asyncio.create_task(_heartbeat_loop())
        try:
            await asyncio.wait_for(consume_task, timeout=job_timeout)
        except TimeoutError:
            cancel.set()
            consume_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, TimeoutError):
                await asyncio.wait_for(consume_task, timeout=15)
            return f"Job timed out after {int(job_timeout)}s"
        finally:
            cancel.set()
            watcher_task.cancel()
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher_task
                await heartbeat_task

        if stall_triggered:
            return f"Job stalled (no progress for {int(stall_seconds)}s)"

        return "\n".join(final_text).strip() or "Job completed with no text output."
