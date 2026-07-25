from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from kxns_cli.blackboard.store import BlackboardStore
from kxns_cli.scan.models import (
    Engagement,
    EngagementStatus,
    Finding,
    FindingSeverity,
    FindingStatus,
    JobStatus,
    ScanJob,
    Target,
)


class MemoryBlackboardStore(BlackboardStore):
    """In-process blackboard for development and fallback."""

    def __init__(self) -> None:
        self._engagements: dict[UUID, Engagement] = {}
        self._targets: dict[UUID, Target] = {}
        self._findings: dict[UUID, Finding] = {}
        self._jobs: dict[UUID, ScanJob] = {}
        self._artifacts: list[dict[str, Any]] = []

    async def connect(self) -> None:
        return

    async def close(self) -> None:
        return

    async def create_engagement(
        self, root_url: str, mode: str, config: dict[str, Any]
    ) -> Engagement:
        engagement = Engagement(
            id=uuid4(),
            root_url=root_url,
            mode=mode,
            status=EngagementStatus.RUNNING,
            config=config,
            created_at=datetime.now(UTC),
        )
        self._engagements[engagement.id] = engagement
        return engagement

    async def update_engagement_status(self, engagement_id: UUID, status: EngagementStatus) -> None:
        engagement = self._engagements[engagement_id]
        self._engagements[engagement_id] = engagement.model_copy(update={"status": status})

    async def add_target(
        self,
        engagement_id: UUID,
        value: str,
        *,
        parent_id: UUID | None = None,
        kind: str = "url",
        depth: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Target:
        target = Target(
            id=uuid4(),
            engagement_id=engagement_id,
            parent_id=parent_id,
            value=value,
            kind=kind,
            depth=depth,
            metadata=metadata or {},
        )
        self._targets[target.id] = target
        return target

    async def list_targets(self, engagement_id: UUID) -> list[Target]:
        return [t for t in self._targets.values() if t.engagement_id == engagement_id]

    async def upsert_finding(
        self,
        engagement_id: UUID,
        title: str,
        severity: FindingSeverity,
        *,
        target_id: UUID | None = None,
        status: FindingStatus = FindingStatus.CANDIDATE,
        description: str = "",
        poc: str = "",
        cwe: str | None = None,
        cvss: float | None = None,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
        finding_id: UUID | None = None,
    ) -> Finding:
        fid = finding_id
        if fid is None:
            for existing in self._findings.values():
                if existing.engagement_id == engagement_id and existing.title == title:
                    fid = existing.id
                    break
        if fid is None:
            fid = uuid4()
        finding = Finding(
            id=fid,
            engagement_id=engagement_id,
            target_id=target_id,
            title=title,
            severity=severity,
            status=status,
            cwe=cwe,
            cvss=cvss,
            description=description,
            poc=poc,
            confidence=confidence,
            metadata=metadata or {},
        )
        self._findings[fid] = finding
        return finding

    async def list_findings(
        self,
        engagement_id: UUID,
        *,
        severities: list[FindingSeverity] | None = None,
        statuses: list[FindingStatus] | None = None,
    ) -> list[Finding]:
        items = [f for f in self._findings.values() if f.engagement_id == engagement_id]
        if severities:
            items = [f for f in items if f.severity in severities]
        if statuses:
            items = [f for f in items if f.status in statuses]
        return items

    async def create_job(
        self,
        engagement_id: UUID,
        phase: str,
        prompt: str,
        *,
        target_id: UUID | None = None,
    ) -> ScanJob:
        job = ScanJob(
            id=uuid4(),
            engagement_id=engagement_id,
            target_id=target_id,
            phase=phase,
            status=JobStatus.PENDING,
            prompt=prompt,
        )
        self._jobs[job.id] = job
        return job

    async def update_job(
        self,
        job_id: UUID,
        *,
        status: JobStatus | None = None,
        result_summary: str | None = None,
        error: str | None = None,
    ) -> None:
        job = self._jobs[job_id]
        updates: dict[str, Any] = {}
        if status is not None:
            updates["status"] = status
        if result_summary is not None:
            updates["result_summary"] = result_summary
        if error is not None:
            updates["error"] = error
        self._jobs[job_id] = job.model_copy(update=updates)

    async def add_artifact(
        self,
        engagement_id: UUID,
        kind: str,
        *,
        finding_id: UUID | None = None,
        path: str | None = None,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        artifact_id = uuid4()
        self._artifacts.append(
            {
                "id": artifact_id,
                "engagement_id": engagement_id,
                "finding_id": finding_id,
                "kind": kind,
                "path": path,
                "content": content,
                "metadata": metadata or {},
            }
        )
        return artifact_id

    def dump_json(self) -> str:
        return json.dumps(
            {
                "engagements": [e.model_dump(mode="json") for e in self._engagements.values()],
                "targets": [t.model_dump(mode="json") for t in self._targets.values()],
                "findings": [f.model_dump(mode="json") for f in self._findings.values()],
            },
            ensure_ascii=False,
            indent=2,
        )
