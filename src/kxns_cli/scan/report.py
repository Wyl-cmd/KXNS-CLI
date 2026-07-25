from __future__ import annotations

import json
from pathlib import Path

from kxns_cli.scan.models import Engagement, Finding
from kxns_cli.scan.report_templates import export_bounty_report as render_bounty_report


def write_reports(
    report_dir: Path,
    engagement: Engagement,
    findings: list[Finding],
    *,
    export_platforms: list[str] | None = None,
) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "engagement_id": str(engagement.id),
        "root_url": engagement.root_url,
        "mode": engagement.mode,
        "status": engagement.status.value,
        "config": engagement.config,
        "findings": [f.model_dump(mode="json") for f in findings],
    }
    json_path = report_dir / "report.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Scan Report: {engagement.root_url}",
        "",
        f"- Engagement: `{engagement.id}`",
        f"- Mode: {engagement.mode}",
        f"- Status: {engagement.status.value}",
    ]
    cfg = engagement.config or {}
    if cfg.get("auth_ticket") or cfg.get("scope"):
        lines.extend(
            [
                f"- Auth ticket: {cfg.get('auth_ticket') or 'N/A'}",
                f"- Scope: {cfg.get('scope') or 'N/A'}",
            ]
        )
    lines.extend(["", "## Findings", ""])
    if not findings:
        lines.append("_No findings recorded._")
    else:
        for f in findings:
            lines.extend(
                [
                    f"### [{f.severity.value.upper()}] {f.title}",
                    "",
                    f"- Status: {f.status.value}",
                    f"- CWE: {f.cwe or 'N/A'}",
                    f"- CVSS: {f.cvss if f.cvss is not None else 'N/A'}",
                    "",
                    f.description or "_No description_",
                    "",
                    "**Proof of Concept**",
                    "",
                    f.poc or "_No POC provided_",
                    "",
                    "---",
                    "",
                ]
            )

    md_path = report_dir / "report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    for platform in export_platforms or []:
        bounty_md = render_bounty_report(
            findings,
            platform=platform,
            engagement=engagement,
            include_mermaid=True,
        )
        (report_dir / f"bounty_{platform}.md").write_text(bounty_md, encoding="utf-8")

    return json_path, md_path


def export_bounty_report(findings: list[Finding], platform: str = "generic") -> str:
    """Export findings in bounty-platform-friendly markdown."""
    return render_bounty_report(findings, platform=platform, engagement=None, include_mermaid=True)
