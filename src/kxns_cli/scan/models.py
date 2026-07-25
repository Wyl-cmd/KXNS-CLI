from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ScanMode(StrEnum):
    INTERACTIVE = "interactive"
    WILDCARD = "wildcard"
    GUARANTEED = "guaranteed"
    PHASED = "phased"
    SWARM = "swarm"


class FindingSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingStatus(StrEnum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"


class EngagementStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScanConfig(BaseModel):
    wildcard: bool = False
    guaranteed: bool = False
    phased: bool = False
    swarm: bool = False
    yolo: bool = True
    authorized: bool = Field(
        default=True,
        description="Authorized pentest: auto-approve tools, attack without confirmation prompts",
    )
    auth_ticket: str = Field(default="", description="Authorization ticket / 工单号 (audit only)")
    scope: str = Field(default="", description="Authorized scope description (audit only)")
    max_concurrency: int = Field(default=4, ge=1, le=32)
    max_depth: int = Field(default=2, ge=0, le=10)
    severity_filter: list[FindingSeverity] = Field(
        default_factory=lambda: [FindingSeverity.HIGH, FindingSeverity.CRITICAL]
    )
    hunt_brief: str = Field(
        default="",
        description="Optimized scan brief derived from user intent",
    )
    user_intent: str = Field(
        default="",
        description="Original natural-language hunt request",
    )


class Engagement(BaseModel):
    id: UUID
    root_url: str
    mode: str
    status: EngagementStatus = EngagementStatus.RUNNING
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class Target(BaseModel):
    id: UUID
    engagement_id: UUID
    parent_id: UUID | None = None
    value: str
    kind: str = "url"
    depth: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    id: UUID
    engagement_id: UUID
    target_id: UUID | None = None
    title: str
    severity: FindingSeverity
    status: FindingStatus = FindingStatus.CANDIDATE
    cwe: str | None = None
    cvss: float | None = None
    description: str = ""
    poc: str = ""
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScanJob(BaseModel):
    id: UUID
    engagement_id: UUID
    target_id: UUID | None = None
    phase: str
    status: JobStatus = JobStatus.PENDING
    prompt: str = ""
    result_summary: str | None = None
    error: str | None = None


class ScanRunResult(BaseModel):
    engagement_id: UUID
    root_url: str
    status: EngagementStatus
    findings: list[Finding] = Field(default_factory=list)
    report_json_path: str | None = None
    report_md_path: str | None = None
