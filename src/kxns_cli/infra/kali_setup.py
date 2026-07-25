"""Deterministic Kali Linux tool setup — check → skip → install → register.

Key principle: ALL tool → package → adapter mappings are HARDCODED.
  已存在 → 跳过并联动适配器
  不存在 → 自动安装并联动适配器
  blocklisted → 只提示，不自动操作

No AI/LLM decisions. No runtime guessing.
The agent MUST NOT modify this module; changes require human review and version control.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from importlib import invalidate_caches as _invalidate_import_caches

logger = logging.getLogger(__name__)


# =============================================================================
#  Enum / dataclass
# =============================================================================


class SetupAction(StrEnum):
    ALREADY_INSTALLED = "already_installed"
    INSTALLED = "installed"
    FAILED = "failed"
    SKIPPED_BLOCKLIST = "skipped_blocklist"


class AdapterStatus(StrEnum):
    """Per-tool adapter linkage status after setup."""

    STRUCTURED = "structured"
    """KXNS has a dedicated adapter (KALI_ADAPTERS in base.py → Finding outputs)."""
    CATALOG = "catalog"
    """Listed in KALI_TOOL_CATALOG → RunKali / Shell raw invocation."""
    NONE = "none"
    """No adapter linkage — only raw shell available."""


@dataclass(slots=True)
class ToolSpec:
    binary: str
    apt_package: str
    category: str = "recon"
    blocklisted: bool = False
    adapter: AdapterStatus = AdapterStatus.NONE
    """Linkage status with KXNS adapter system (hardcoded per tool)."""


@dataclass(slots=True)
class LinkReport:
    """Per-tool linkage summary emitted after setup."""

    binary: str
    action: SetupAction
    adapter: AdapterStatus
    note: str = ""

    @property
    def link_badge(self) -> str:
        match self.adapter:
            case AdapterStatus.STRUCTURED:
                return "STRATEGIC"  # 结构化适配器 → 自动产生 Findings
            case AdapterStatus.CATALOG:
                return "CATALOG"
            case _:
                return "RAW"


@dataclass(slots=True)
class SetupResult:
    ok: bool = True
    actions: dict[str, SetupAction] = field(default_factory=dict)
    link_reports: list[LinkReport] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def installed_count(self) -> int:
        return sum(1 for a in self.actions.values() if a == SetupAction.INSTALLED)

    @property
    def already_count(self) -> int:
        return sum(1 for a in self.actions.values() if a == SetupAction.ALREADY_INSTALLED)

    @property
    def failed_count(self) -> int:
        return sum(1 for a in self.actions.values() if a == SetupAction.FAILED)

    @property
    def structured_linked(self) -> list[str]:
        """Tools with STRUCTURED adapter that are now installed."""
        return [
            r.binary
            for r in self.link_reports
            if r.adapter == AdapterStatus.STRUCTURED
            and r.action in (SetupAction.ALREADY_INSTALLED, SetupAction.INSTALLED)
        ]

    @property
    def catalog_linked(self) -> list[str]:
        """Tools with CATALOG linkage that are now installed."""
        return [
            r.binary
            for r in self.link_reports
            if r.adapter == AdapterStatus.CATALOG
            and r.action in (SetupAction.ALREADY_INSTALLED, SetupAction.INSTALLED)
        ]


# =============================================================================
#  HARDCODED TOOL WHITELIST — DO NOT MODIFY WITHOUT HUMAN REVIEW
# =============================================================================
#  adapter field:
#    STRUCTURED → 安装后 RunKali 自动调用 build_command/parse_output → Findings
#    CATALOG    → 安装后 RunKali 可执行原始命令，无结构化解析
#    NONE       → 仅 shell 执行，不联动 KXNS 适配器
#
#  blocklisted=True → NEVER auto-install (hydra, msfconsole, john, etc.)
# =============================================================================

KALI_TOOL_WHITELIST: list[ToolSpec] = [
    # ── Recon ────────────────────────────────────────────────
    ToolSpec("nmap", "nmap", "recon", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("masscan", "masscan", "recon", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("subfinder", "subfinder", "recon", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("amass", "amass", "recon", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("dnsenum", "dnsenum", "recon", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("dnsrecon", "dnsrecon", "recon", adapter=AdapterStatus.CATALOG),
    ToolSpec("theHarvester", "theharvester", "recon", adapter=AdapterStatus.CATALOG),
    ToolSpec("assetfinder", "assetfinder", "recon", adapter=AdapterStatus.CATALOG),
    ToolSpec("fierce", "fierce", "recon", adapter=AdapterStatus.CATALOG),
    # ── Web / HTTP ───────────────────────────────────────────
    ToolSpec("httpx", "httpx-toolkit", "web", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("whatweb", "whatweb", "web", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("wafw00f", "wafw00f", "web", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("gobuster", "gobuster", "web", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("ffuf", "ffuf", "web", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("feroxbuster", "feroxbuster", "web", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("dirb", "dirb", "web", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("dirsearch", "dirsearch", "web", adapter=AdapterStatus.CATALOG),
    ToolSpec("wfuzz", "wfuzz", "web", adapter=AdapterStatus.STRUCTURED),
    # ── Vulnerability scanners ────────────────────────────────
    ToolSpec("nuclei", "nuclei", "web", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("nikto", "nikto", "web", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("wpscan", "wpscan", "web", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("sqlmap", "sqlmap", "web", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("commix", "commix", "web", adapter=AdapterStatus.STRUCTURED),
    # ── Network / SMB ────────────────────────────────────────
    ToolSpec("enum4linux", "enum4linux", "network", adapter=AdapterStatus.STRUCTURED),
    ToolSpec("smbclient", "smbclient", "network", adapter=AdapterStatus.CATALOG),
    ToolSpec("rpcclient", "rpcclient", "network", adapter=AdapterStatus.CATALOG),
    ToolSpec("nbtscan", "nbtscan", "network", adapter=AdapterStatus.CATALOG),
    ToolSpec("netcat", "netcat-openbsd", "network", adapter=AdapterStatus.CATALOG),
    ToolSpec("socat", "socat", "network", adapter=AdapterStatus.CATALOG),
    # ── Exploit / Post-exploit ────────────────────────────────
    ToolSpec("hydra", "hydra", "exploit", blocklisted=True, adapter=AdapterStatus.STRUCTURED),
    ToolSpec("medusa", "medusa", "exploit", blocklisted=True, adapter=AdapterStatus.CATALOG),
    ToolSpec("john", "john", "crypto", blocklisted=True, adapter=AdapterStatus.CATALOG),
    ToolSpec("hashcat", "hashcat", "crypto", blocklisted=True, adapter=AdapterStatus.CATALOG),
    ToolSpec(
        "msfconsole",
        "metasploit-framework",
        "exploit",
        blocklisted=True,
        adapter=AdapterStatus.CATALOG,
    ),
    ToolSpec(
        "responder", "responder", "exploit", blocklisted=True, adapter=AdapterStatus.STRUCTURED
    ),
    ToolSpec("searchsploit", "exploitdb", "exploit", adapter=AdapterStatus.STRUCTURED),
    # ── Infrastructure ────────────────────────────────────────
    ToolSpec("psql", "postgresql-client", "infra"),
    ToolSpec("redis-cli", "redis-tools", "infra"),
    ToolSpec("rg", "ripgrep", "misc"),
    ToolSpec("curl", "curl", "misc"),
    ToolSpec("wget", "wget", "misc"),
    # ── Misc / Analysis ───────────────────────────────────────
    ToolSpec("strings", "binutils", "misc", adapter=AdapterStatus.CATALOG),
    ToolSpec("xxd", "xxd", "misc", adapter=AdapterStatus.CATALOG),
    ToolSpec("openssl", "openssl", "crypto", adapter=AdapterStatus.CATALOG),
    ToolSpec("tcpdump", "tcpdump", "network", adapter=AdapterStatus.CATALOG),
    ToolSpec("tshark", "tshark", "network", adapter=AdapterStatus.CATALOG),
    ToolSpec("aircrack-ng", "aircrack-ng", "wireless", adapter=AdapterStatus.CATALOG),
    ToolSpec("binwalk", "binwalk", "misc", adapter=AdapterStatus.CATALOG),
    ToolSpec("impacket-smbclient", "impacket-scripts", "network", adapter=AdapterStatus.CATALOG),
]


# =============================================================================
#  Public API
# =============================================================================


def check_tool(binary: str) -> bool:
    return shutil.which(binary) is not None


def check_all_tools() -> dict[str, bool]:
    return {spec.binary: check_tool(spec.binary) for spec in KALI_TOOL_WHITELIST}


def get_missing_tools() -> list[ToolSpec]:
    missing: list[ToolSpec] = []
    for spec in KALI_TOOL_WHITELIST:
        if not check_tool(spec.binary):
            missing.append(spec)
    return sorted(missing, key=lambda s: (s.category, s.binary))


def _apt_install(packages: list[str]) -> tuple[bool, str]:
    if not packages:
        return True, ""
    cmd = ["sudo", "apt", "install", "-y", *packages]
    logger.info("apt install: %s", " ".join(packages))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=300)
        ok = proc.returncode == 0
        output = (proc.stdout + proc.stderr)[-2000:]
        return ok, output
    except subprocess.TimeoutExpired:
        return False, "apt install timed out after 300s"
    except FileNotFoundError:
        return False, "sudo or apt not found"


def clear_kali_tool_cache() -> None:
    """Call AFTER installing new tools to invalidate discover_installed_tools() LRU."""
    try:
        from kxns_cli.tools.kali.registry import discover_installed_tools

        discover_installed_tools.cache_clear()
        logger.info("Kali tool registry cache cleared → new tools visible")
    except ImportError:
        pass


def setup_kali_tools(*, fix: bool = False, dry_run: bool = False) -> SetupResult:
    """Deterministic: check → skip/install → clear cache → report linkage.

    After install, clears the @lru_cache on discover_installed_tools()
    so newly installed tools are immediately visible to KXNS adapters.

    Returns:
        SetupResult with per-tool actions and adapter linkage reports.
    """
    result = SetupResult()
    any_installed = False

    for spec in KALI_TOOL_WHITELIST:
        if check_tool(spec.binary):
            result.actions[spec.binary] = SetupAction.ALREADY_INSTALLED
            result.link_reports.append(
                LinkReport(spec.binary, SetupAction.ALREADY_INSTALLED, spec.adapter)
            )
            continue

        if spec.blocklisted:
            result.actions[spec.binary] = SetupAction.SKIPPED_BLOCKLIST
            result.link_reports.append(
                LinkReport(
                    spec.binary,
                    SetupAction.SKIPPED_BLOCKLIST,
                    spec.adapter,
                    f"手动安装: sudo apt install {spec.apt_package}",
                )
            )
            continue

        if not spec.apt_package:
            result.actions[spec.binary] = SetupAction.SKIPPED_BLOCKLIST
            continue

        if not fix:
            result.actions[spec.binary] = SetupAction.FAILED
            result.errors.append(f"{spec.binary}: 未安装 (apt: {spec.apt_package})")
            continue

        if dry_run:
            result.actions[spec.binary] = SetupAction.FAILED
            continue

        # ── INSTALL + LINK ───────────────────────────────────
        ok, output = _apt_install([spec.apt_package])
        if ok and check_tool(spec.binary):
            result.actions[spec.binary] = SetupAction.INSTALLED
            result.link_reports.append(LinkReport(spec.binary, SetupAction.INSTALLED, spec.adapter))
            any_installed = True
        else:
            result.actions[spec.binary] = SetupAction.FAILED
            result.errors.append(
                f"{spec.binary}: apt install {spec.apt_package} 失败: {output[:200]}"
            )
            result.ok = False

    # ── 联动适配器（清缓存，使新装工具对 KXNS 立即可见）──
    if any_installed:
        clear_kali_tool_cache()

        # 模块级 import 缓存也刷新一次
        from contextlib import suppress

        with suppress(Exception):
            _invalidate_import_caches()

    return result


def setup_minimal_tools(*, fix: bool = False) -> SetupResult:
    """Setup only the minimal tools (postgres, redis, rg, curl, python3, bash).

    Does NOT install pentest tools — safe for initial bootstrap.
    """
    minimal = [
        ToolSpec("python3", "python3", "infra"),
        ToolSpec("psql", "postgresql-client", "infra"),
        ToolSpec("redis-cli", "redis-tools", "infra"),
        ToolSpec("rg", "ripgrep", "misc"),
        ToolSpec("curl", "curl", "misc"),
        ToolSpec("bash", "bash", "misc"),
    ]
    result = SetupResult()
    for spec in minimal:
        if check_tool(spec.binary):
            result.actions[spec.binary] = SetupAction.ALREADY_INSTALLED
            result.link_reports.append(
                LinkReport(spec.binary, SetupAction.ALREADY_INSTALLED, AdapterStatus.NONE)
            )
            continue
        if not fix:
            result.actions[spec.binary] = SetupAction.FAILED
            continue
        ok, _ = _apt_install([spec.apt_package])
        if ok and check_tool(spec.binary):
            result.actions[spec.binary] = SetupAction.INSTALLED
        else:
            result.actions[spec.binary] = SetupAction.FAILED
            result.errors.append(f"{spec.binary}: apt install 失败")
            result.ok = False
    return result
