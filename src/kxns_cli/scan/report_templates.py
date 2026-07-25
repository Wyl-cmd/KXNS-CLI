"""Bounty / SRC report templates with attack-chain diagrams."""

from __future__ import annotations

from kxns_cli.scan.models import Engagement, Finding


def build_attack_chain_mermaid(finding: Finding, root_url: str = "") -> str:
    """Generate a simple attack-chain mermaid from finding metadata."""
    target_label = (root_url or "Target").replace('"', "'")[:40]
    title = finding.title.replace('"', "'")[:60]
    return f"""```mermaid
flowchart LR
  recon["Recon: {target_label}"] --> exploit["{title}"]
  exploit --> poc["PoC Verification"]
  poc --> impact["Impact / Exfil"]
  style exploit fill:#f96,stroke:#333
```"""


def export_bounty_report(
    findings: list[Finding],
    platform: str = "generic",
    *,
    engagement: Engagement | None = None,
    include_mermaid: bool = True,
) -> str:
    """Export confirmed findings in platform-specific markdown."""
    headers = {
        "hackerone": "# HackerOne Submission Draft",
        "bugcrowd": "# Bugcrowd Submission Draft",
        "butian": "# 补天漏洞报告",
        "wecom": "# 企业微信 / 内部 SRC 漏洞通报",
        "src": "# 企业 SRC 漏洞报告",
        "generic": "# Vulnerability Report",
    }
    root = engagement.root_url if engagement else ""
    auth = (engagement.config if engagement else {}) or {}
    ticket = auth.get("auth_ticket") or auth.get("ticket") or "N/A"
    scope = auth.get("scope") or "Authorized engagement"

    parts = [headers.get(platform, headers["generic"]), ""]
    if engagement:
        parts.extend(
            [
                f"- **目标**: {root}",
                f"- **授权工单**: {ticket}",
                f"- **授权范围**: {scope}",
                f"- **Engagement**: `{engagement.id}`",
                "",
            ]
        )

    confirmed = [f for f in findings if f.status.value == "confirmed"]
    if not confirmed:
        parts.append("_No confirmed findings._")
        return "\n".join(parts)

    for f in confirmed:
        parts.extend(
            [
                f"## {f.title}",
                "",
                f"**Severity:** {f.severity.value.upper()}",
                f"**CWE:** {f.cwe or 'N/A'}",
                f"**CVSS:** {f.cvss if f.cvss is not None else 'N/A'}",
                "",
            ]
        )
        if platform in ("butian", "wecom", "src"):
            parts.extend(
                [
                    "### 漏洞概述",
                    f.description or "",
                    "",
                    "### 攻击路径",
                ]
            )
            if include_mermaid:
                parts.append(build_attack_chain_mermaid(f, root))
                parts.append("")
            parts.extend(
                [
                    "### 复现步骤",
                    f.poc or "_无 POC_",
                    "",
                    "### 修复建议",
                    "请根据漏洞类型限制输入、加强鉴权、升级组件版本并增加 WAF/监控规则。",
                    "",
                    "---",
                    "",
                ]
            )
        else:
            parts.extend(
                [
                    "### Summary",
                    f.description or "",
                    "",
                    "### Steps to Reproduce",
                    f.poc or "_No POC_",
                    "",
                ]
            )
            if include_mermaid:
                parts.append("### Attack Chain")
                parts.append(build_attack_chain_mermaid(f, root))
                parts.append("")
            parts.extend(
                [
                    "### Remediation",
                    "Apply vendor patches and validate with re-test.",
                    "",
                    "---",
                    "",
                ]
            )

    return "\n".join(parts)
