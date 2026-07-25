from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

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


class BlackboardStore(ABC):
    """Shared knowledge store for scan orchestration."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def create_engagement(
        self, root_url: str, mode: str, config: dict[str, Any]
    ) -> Engagement: ...

    @abstractmethod
    async def update_engagement_status(
        self, engagement_id: UUID, status: EngagementStatus
    ) -> None: ...

    @abstractmethod
    async def add_target(
        self,
        engagement_id: UUID,
        value: str,
        *,
        parent_id: UUID | None = None,
        kind: str = "url",
        depth: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Target: ...

    @abstractmethod
    async def list_targets(self, engagement_id: UUID) -> list[Target]: ...

    @abstractmethod
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
    ) -> Finding: ...

    @abstractmethod
    async def list_findings(
        self,
        engagement_id: UUID,
        *,
        severities: list[FindingSeverity] | None = None,
        statuses: list[FindingStatus] | None = None,
    ) -> list[Finding]: ...

    @abstractmethod
    async def create_job(
        self,
        engagement_id: UUID,
        phase: str,
        prompt: str,
        *,
        target_id: UUID | None = None,
    ) -> ScanJob: ...

    @abstractmethod
    async def update_job(
        self,
        job_id: UUID,
        *,
        status: JobStatus | None = None,
        result_summary: str | None = None,
        error: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def add_artifact(
        self,
        engagement_id: UUID,
        kind: str,
        *,
        finding_id: UUID | None = None,
        path: str | None = None,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UUID: ...
