from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from kxns_cli.blackboard.store import BlackboardStore
from kxns_cli.config import BlackboardConfig
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

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class PostgresBlackboardStore(BlackboardStore):
    """PostgreSQL-backed blackboard store."""

    def __init__(self, config: BlackboardConfig) -> None:
        self._config = config
        self._pool: Any = None

    async def connect(self) -> None:
        import asyncpg

        self._pool = await asyncpg.create_pool(
            host=self._config.host,
            port=self._config.port,
            user=self._config.user,
            password=self._config.password.get_secret_value(),
            database=self._config.database,
            min_size=1,
            max_size=self._config.pool_size,
        )
        await self._ensure_schema()

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def _ensure_schema(self) -> None:
        assert self._pool is not None
        schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        async with self._pool.acquire() as conn:
            await conn.execute(schema_sql)

    async def create_engagement(
        self, root_url: str, mode: str, config: dict[str, Any]
    ) -> Engagement:
        assert self._pool is not None
        eid = uuid4()
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO engagements (id, root_url, mode, status, config)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                """,
                eid,
                root_url,
                mode,
                EngagementStatus.RUNNING.value,
                json.dumps(config),
            )
        return Engagement(
            id=eid,
            root_url=root_url,
            mode=mode,
            status=EngagementStatus.RUNNING,
            config=config,
            created_at=datetime.now(UTC),
        )

    async def update_engagement_status(self, engagement_id: UUID, status: EngagementStatus) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE engagements SET status = $1, updated_at = NOW() WHERE id = $2",
                status.value,
                engagement_id,
            )

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
        assert self._pool is not None
        tid = uuid4()
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO targets (id, engagement_id, parent_id, value, kind, depth, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                """,
                tid,
                engagement_id,
                parent_id,
                value,
                kind,
                depth,
                json.dumps(metadata or {}),
            )
        return Target(
            id=tid,
            engagement_id=engagement_id,
            parent_id=parent_id,
            value=value,
            kind=kind,
            depth=depth,
            metadata=metadata or {},
        )

    async def list_targets(self, engagement_id: UUID) -> list[Target]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, engagement_id, parent_id, value, kind, depth, metadata
                FROM targets WHERE engagement_id = $1
                """,
                engagement_id,
            )
        return [
            Target(
                id=r["id"],
                engagement_id=r["engagement_id"],
                parent_id=r["parent_id"],
                value=r["value"],
                kind=r["kind"],
                depth=r["depth"],
                metadata=json.loads(r["metadata"])
                if isinstance(r["metadata"], str)
                else r["metadata"],
            )
            for r in rows
        ]

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
        assert self._pool is not None
        fid = finding_id
        if fid is None:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id FROM findings WHERE engagement_id = $1 AND title = $2 LIMIT 1",
                    engagement_id,
                    title,
                )
                if row is not None:
                    fid = row["id"]
        if fid is None:
            fid = uuid4()
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO findings (
                    id, engagement_id, target_id, title, severity, status,
                    cwe, cvss, description, poc, confidence, metadata
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    severity = EXCLUDED.severity,
                    status = EXCLUDED.status,
                    description = EXCLUDED.description,
                    poc = EXCLUDED.poc,
                    confidence = EXCLUDED.confidence,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                """,
                fid,
                engagement_id,
                target_id,
                title,
                severity.value,
                status.value,
                cwe,
                cvss,
                description,
                poc,
                confidence,
                json.dumps(metadata or {}),
            )
        return Finding(
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

    async def list_findings(
        self,
        engagement_id: UUID,
        *,
        severities: list[FindingSeverity] | None = None,
        statuses: list[FindingStatus] | None = None,
    ) -> list[Finding]:
        assert self._pool is not None
        query = """
            SELECT id, engagement_id, target_id, title, severity, status,
                   cwe, cvss, description, poc, confidence, metadata
            FROM findings WHERE engagement_id = $1
        """
        params: list[Any] = [engagement_id]
        if severities:
            query += f" AND severity = ANY(${len(params) + 1})"
            params.append([s.value for s in severities])
        if statuses:
            query += f" AND status = ANY(${len(params) + 1})"
            params.append([s.value for s in statuses])
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return [
            Finding(
                id=r["id"],
                engagement_id=r["engagement_id"],
                target_id=r["target_id"],
                title=r["title"],
                severity=FindingSeverity(r["severity"]),
                status=FindingStatus(r["status"]),
                cwe=r["cwe"],
                cvss=r["cvss"],
                description=r["description"] or "",
                poc=r["poc"] or "",
                confidence=r["confidence"],
                metadata=json.loads(r["metadata"])
                if isinstance(r["metadata"], str)
                else r["metadata"],
            )
            for r in rows
        ]

    async def create_job(
        self,
        engagement_id: UUID,
        phase: str,
        prompt: str,
        *,
        target_id: UUID | None = None,
    ) -> ScanJob:
        assert self._pool is not None
        jid = uuid4()
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO scan_jobs (id, engagement_id, target_id, phase, status, prompt)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                jid,
                engagement_id,
                target_id,
                phase,
                JobStatus.PENDING.value,
                prompt,
            )
        return ScanJob(
            id=jid,
            engagement_id=engagement_id,
            target_id=target_id,
            phase=phase,
            status=JobStatus.PENDING,
            prompt=prompt,
        )

    async def update_job(
        self,
        job_id: UUID,
        *,
        status: JobStatus | None = None,
        result_summary: str | None = None,
        error: str | None = None,
    ) -> None:
        assert self._pool is not None
        parts: list[str] = ["updated_at = NOW()"]
        params: list[Any] = []
        if status is not None:
            params.append(status.value)
            parts.append(f"status = ${len(params)}")
        if result_summary is not None:
            params.append(result_summary)
            parts.append(f"result_summary = ${len(params)}")
        if error is not None:
            params.append(error)
            parts.append(f"error = ${len(params)}")
        params.append(job_id)
        query = f"UPDATE scan_jobs SET {', '.join(parts)} WHERE id = ${len(params)}"
        async with self._pool.acquire() as conn:
            await conn.execute(query, *params)

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
        assert self._pool is not None
        aid = uuid4()
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO artifacts (id, engagement_id, finding_id, kind, path, content, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                """,
                aid,
                engagement_id,
                finding_id,
                kind,
                path,
                content,
                json.dumps(metadata or {}),
            )
        return aid
