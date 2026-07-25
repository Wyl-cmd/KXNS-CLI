from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field

from kxns_cli.infra.kali_setup import (
    KALI_TOOL_WHITELIST,
    SetupAction,
    check_tool,
    setup_kali_tools,
)

logger = logging.getLogger(__name__)


@dataclass
class DoctorResult:
    ok: bool
    checks: dict[str, bool] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    setup_summary: str = ""
    structured_linked: list[str] = field(default_factory=list)
    catalog_linked: list[str] = field(default_factory=list)
    blocklisted_skipped: list[str] = field(default_factory=list)


def run_doctor(*, warn_only: bool = False, fix: bool = False) -> DoctorResult:
    """Check Kali/Linux environment for scan prerequisites.

    Args:
        warn_only: If True, don't mark result as failed on missing tools.
        fix: If True, auto-install missing tools via apt (hardcoded whitelist only).
            After install, clears the Kali tool registry cache so adapters
            immediately see the new tools.
    """
    result = DoctorResult(ok=True)

    # ── 1. Required system tools ─────────────────────────────
    required = {
        "python3": "python3",
        "bash": "bash",
        "rg": "ripgrep",
        "curl": "curl",
        "nmap": "nmap",
    }
    for binary, apt_name in required.items():
        ok = check_tool(binary)
        result.checks[binary] = ok
        if not ok:
            result.ok = False
            result.issues.append(f"Missing required tool: {binary}")
            result.hints.append(
                f"sudo apt install {apt_name}" if binary != "rg" else "sudo apt install ripgrep"
            )

    # ── 2. Full tool check ───────────────────────────────────
    for spec in KALI_TOOL_WHITELIST:
        result.checks[spec.binary] = check_tool(spec.binary)

    # ── 3. fix: deterministic tool setup ────────────────────
    if fix:
        setup = setup_kali_tools(fix=True)
        already = setup.already_count
        installed = setup.installed_count
        failed = setup.failed_count

        # 联动状态
        result.structured_linked = setup.structured_linked
        result.catalog_linked = setup.catalog_linked

        for r in setup.link_reports:
            if r.action == SetupAction.SKIPPED_BLOCKLIST:
                result.blocklisted_skipped.append(r.binary)

        parts = [f"已有={already}"]
        if installed:
            parts.append(f"新装={installed}")
        if result.structured_linked:
            parts.append(f"结构化联动={len(result.structured_linked)}")
        if result.catalog_linked:
            parts.append(f"目录联动={len(result.catalog_linked)}")
        if failed:
            parts.append(f"失败={failed}")
            result.ok = False
        result.setup_summary = ", ".join(parts)

        for err in setup.errors:
            result.hints.append(err)

    # ── 4. PostgreSQL hints ──────────────────────────────────
    if not result.checks.get("psql", False):
        result.hints.append("PostgreSQL not found: sudo apt install postgresql postgresql-contrib")
        result.hints.append("Or set [blackboard] backend = 'memory' in ~/.kxns/config.toml")

    if warn_only and not result.ok:
        result.ok = True

    return result


def bootstrap_postgres_kxns() -> tuple[bool, str]:
    """Attempt to create kxns database user and pgvector extension (may require sudo)."""
    script = [
        "sudo",
        "-u",
        "postgres",
        "psql",
        "-c",
        "CREATE USER kxns WITH PASSWORD 'kxns';",
        "-c",
        "CREATE DATABASE kxns_blackboard OWNER kxns;",
    ]
    try:
        proc = subprocess.run(script, capture_output=True, text=True, check=False)
        if proc.returncode != 0 and "already exists" not in (proc.stdout + proc.stderr).lower():
            return False, proc.stderr or proc.stdout or "bootstrap failed"
    except FileNotFoundError:
        return False, "psql not found — install postgresql first"

    pgvector_script = [
        "sudo",
        "-u",
        "postgres",
        "psql",
        "-d",
        "kxns_blackboard",
        "-c",
        "CREATE EXTENSION IF NOT EXISTS vector;",
    ]
    try:
        pgv = subprocess.run(pgvector_script, capture_output=True, text=True, check=False)
        if pgv.returncode == 0:
            return True, "PostgreSQL kxns user/database/pgvector ready"
        return True, (
            "PostgreSQL ready (pgvector optional, install: sudo apt install postgresql-16-pgvector)"
        )
    except FileNotFoundError:
        return True, "PostgreSQL ready (pgvector check skipped)"
