from __future__ import annotations

from pathlib import Path

from kaos.path import KaosPath

from kxns_cli.blackboard import create_blackboard_store
from kxns_cli.blackboard.store import BlackboardStore
from kxns_cli.config import Config
from kxns_cli.infra.doctor import run_doctor
from kxns_cli.scan.coordinator import Coordinator
from kxns_cli.scan.models import (
    EngagementStatus,
    FindingStatus,
    ScanConfig,
    ScanRunResult,
)
from kxns_cli.scan.modes.guaranteed import run_guaranteed
from kxns_cli.scan.modes.phased import run_phased
from kxns_cli.scan.modes.swarm import run_swarm
from kxns_cli.scan.modes.wildcard import run_wildcard
from kxns_cli.scan.report import write_reports
from kxns_cli.soul import wire_send
from kxns_cli.utils.logging import logger
from kxns_cli.wire.types import ScanBegin, ScanEnd


class ScanManager:
    """Top-level scan orchestration entrypoint."""

    def __init__(
        self,
        config: Config,
        work_dir: KaosPath,
        *,
        blackboard: BlackboardStore | None = None,
    ) -> None:
        self._config = config
        self._work_dir = work_dir
        self._blackboard = blackboard

    async def start_scan(
        self,
        url: str,
        scan_config: ScanConfig,
        *,
        skip_precheck: bool = False,
    ) -> ScanRunResult:
        """Run scan pipeline for the given URL."""
        if self._config.scan.precheck_enabled and not skip_precheck:
            from kxns_cli.infra.precheck import format_precheck_failure, run_precheck

            pre = await run_precheck(self._config)
            if not pre.ok:
                msg = format_precheck_failure(pre)
                raise RuntimeError(msg)

        doctor = run_doctor(warn_only=True)
        if not doctor.ok:
            logger.warning("Doctor checks failed: {issues}", issues=doctor.issues)

        blackboard = self._blackboard or await create_blackboard_store(
            self._config,
            strict=self._config.blackboard.require_postgres if self._config.blackboard else True,
        )
        own_bb = self._blackboard is None

        modes: list[str] = []
        if scan_config.wildcard:
            modes.append("wildcard")
        if scan_config.guaranteed:
            modes.append("guaranteed")
        if scan_config.phased:
            modes.append("phased")
        if scan_config.swarm:
            modes.append("swarm")
        mode_str = "+".join(modes) if modes else "interactive"

        engagement = await blackboard.create_engagement(
            url,
            mode_str,
            scan_config.model_dump(mode="json"),
        )
        wire_send(
            ScanBegin(
                engagement_id=str(engagement.id),
                root_url=url,
                mode=mode_str,
            )
        )

        coordinator = Coordinator(
            config=self._config,
            blackboard=blackboard,
            work_dir=self._work_dir,
            yolo=(
                scan_config.yolo or scan_config.authorized or self._config.scan.authorized_attack
            ),
            max_concurrency=scan_config.max_concurrency,
        )

        try:
            if scan_config.wildcard:
                await run_wildcard(
                    engagement_id=engagement.id,
                    root_url=url,
                    blackboard=blackboard,
                    coordinator=coordinator,
                    scan_config=scan_config,
                )

            if scan_config.phased:
                await run_phased(
                    engagement_id=engagement.id,
                    blackboard=blackboard,
                    coordinator=coordinator,
                    work_dir=self._work_dir,
                )

            if scan_config.swarm:
                await run_swarm(
                    engagement_id=engagement.id,
                    blackboard=blackboard,
                    coordinator=coordinator,
                )

            if scan_config.guaranteed:
                await run_guaranteed(
                    engagement_id=engagement.id,
                    blackboard=blackboard,
                    coordinator=coordinator,
                    scan_config=scan_config,
                )

            report_statuses = [FindingStatus.CONFIRMED]
            if not self._config.scan.confirmed_only_reports:
                report_statuses.append(FindingStatus.CANDIDATE)

            findings = await blackboard.list_findings(
                engagement.id,
                severities=scan_config.severity_filter,
                statuses=report_statuses,
            )

            # Include candidate summary in metadata but not in main report when strict
            all_candidates = await blackboard.list_findings(
                engagement.id,
                statuses=[FindingStatus.CANDIDATE],
            )
            if self._config.scan.confirmed_only_reports and all_candidates:
                logger.info(
                    "Report excludes {n} candidate finding(s); run guaranteed mode to confirm",
                    n=len(all_candidates),
                )

            report_dir = Path(self._work_dir.unsafe_to_local_path()) / "scans" / str(engagement.id)
            json_path, md_path = write_reports(
                report_dir,
                engagement,
                findings,
                export_platforms=["butian", "wecom", "src"],
            )

            await blackboard.update_engagement_status(engagement.id, EngagementStatus.COMPLETED)
            wire_send(
                ScanEnd(
                    engagement_id=str(engagement.id),
                    root_url=url,
                    success=True,
                    finding_count=len(findings),
                )
            )

            return ScanRunResult(
                engagement_id=engagement.id,
                root_url=url,
                status=EngagementStatus.COMPLETED,
                findings=findings,
                report_json_path=str(json_path),
                report_md_path=str(md_path),
            )
        except Exception as exc:
            logger.exception("Scan failed")
            await blackboard.update_engagement_status(engagement.id, EngagementStatus.FAILED)
            wire_send(
                ScanEnd(
                    engagement_id=str(engagement.id),
                    root_url=url,
                    success=False,
                    finding_count=0,
                )
            )
            raise exc
        finally:
            if own_bb:
                await blackboard.close()
