from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from kaos.path import KaosPath

scan_cli = typer.Typer(help="Run automated penetration scan orchestration.")


@scan_cli.command("run")
def scan_run(
    url: Annotated[str, typer.Argument(help="Target URL or domain.")],
    wildcard: Annotated[
        bool, typer.Option("--wildcard", help="Enable wildcard recon pipeline.")
    ] = False,
    guaranteed: Annotated[
        bool, typer.Option("--guaranteed", help="Run evaluate/confirm/POC pipeline.")
    ] = False,
    phased: Annotated[bool, typer.Option("--phased", help="Run 22-phase pipeline.")] = False,
    swarm: Annotated[bool, typer.Option("--swarm", help="Run swarm agent dispatch.")] = False,
    yolo: Annotated[bool, typer.Option("--yolo/--no-yolo", help="Auto-approve tools.")] = True,
    authorized: Annotated[
        bool,
        typer.Option(
            "--authorized/--no-authorized",
            help="Authorized pentest: attack without confirmation (audit via --ticket/--scope).",
        ),
    ] = True,
    ticket: Annotated[
        str, typer.Option("--ticket", help="Authorization ticket (audit only).")
    ] = "",
    scope: Annotated[str, typer.Option("--scope", help="Authorized scope (audit only).")] = "",
    print_mode: Annotated[bool, typer.Option("--print", help="Print mode output.")] = True,
    severity: Annotated[
        str,
        typer.Option("--severity", help="Comma-separated severities to include."),
    ] = "high,critical",
    work_dir: Annotated[
        str | None,
        typer.Option("--work-dir", "-w", help="Working directory."),
    ] = None,
    skip_precheck: Annotated[
        bool,
        typer.Option("--skip-precheck", help="Skip environment precheck before scan."),
    ] = False,
) -> None:
    """Start scan orchestration for a target URL."""
    from kxns_cli.config import load_config
    from kxns_cli.scan.manager import ScanManager
    from kxns_cli.scan.models import FindingSeverity, ScanConfig

    if not any([wildcard, guaranteed, phased, swarm]):
        wildcard = True
        guaranteed = True

    sev_filter = []
    for part in severity.split(","):
        part = part.strip().lower()
        if part:
            sev_filter.append(FindingSeverity(part))

    scan_config = ScanConfig(
        wildcard=wildcard,
        guaranteed=guaranteed,
        phased=phased,
        swarm=swarm,
        yolo=yolo or authorized,
        authorized=authorized,
        auth_ticket=ticket,
        scope=scope,
        severity_filter=sev_filter or [FindingSeverity.HIGH, FindingSeverity.CRITICAL],
    )

    config = load_config()
    wd = KaosPath.unsafe_from_local_path(work_dir) if work_dir else KaosPath.cwd()

    async def _run() -> None:
        manager = ScanManager(config, wd)
        result = await manager.start_scan(url, scan_config, skip_precheck=skip_precheck)
        if print_mode:
            typer.echo(f"Engagement: {result.engagement_id}")
            typer.echo(f"Status: {result.status.value}")
            typer.echo(f"Findings: {len(result.findings)}")
            if result.report_json_path:
                typer.echo(f"Report JSON: {result.report_json_path}")
            if result.report_md_path:
                typer.echo(f"Report MD: {result.report_md_path}")

    asyncio.run(_run())


@scan_cli.command("bounty-export")
def bounty_export(
    report_json: Annotated[str, typer.Argument(help="Path to report.json.")],
    platform: Annotated[
        str,
        typer.Option(
            "--platform",
            help="hackerone, bugcrowd, butian, wecom, src, generic",
        ),
    ] = "generic",
    output: Annotated[str | None, typer.Option("-o", help="Output file path.")] = None,
) -> None:
    """Export confirmed findings to bounty platform markdown."""
    import json
    from pathlib import Path

    from kxns_cli.scan.models import Finding
    from kxns_cli.scan.report import export_bounty_report

    data = json.loads(Path(report_json).read_text(encoding="utf-8"))
    findings = [Finding.model_validate(f) for f in data.get("findings", [])]
    md = export_bounty_report(findings, platform=platform)
    if output:
        Path(output).write_text(md, encoding="utf-8")
        typer.echo(f"Wrote {output}")
    else:
        typer.echo(md)
