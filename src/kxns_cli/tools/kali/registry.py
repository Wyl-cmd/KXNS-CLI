"""Kali Linux tool registry — discover and run pentest tools."""

from __future__ import annotations

import shutil
from functools import lru_cache

# Core adapters with structured parsers (see tools/kali/base.py)
STRUCTURED_TOOLS: frozenset[str] = frozenset(
    {
        "nmap",
        "httpx",
        "nuclei",
        "subfinder",
        "gobuster",
        "ffuf",
        "sqlmap",
        "nikto",
        "wpscan",
        "hydra",
        "dirb",
        "masscan",
        "amass",
        "wafw00f",
        "whatweb",
        "feroxbuster",
        "commix",
        "wfuzz",
        "enum4linux",
        "dnsenum",
        "searchsploit",
        "responder",
    }
)

# Common Kali / pentest binaries the agent may invoke via RunKali or Shell
KALI_TOOL_CATALOG: tuple[str, ...] = (
    # Recon
    "nmap",
    "masscan",
    "rustscan",
    "subfinder",
    "amass",
    "assetfinder",
    "dnsenum",
    "dnsrecon",
    "fierce",
    "theHarvester",
    "httpx",
    "whatweb",
    "wafw00f",
    # Web
    "ffuf",
    "gobuster",
    "feroxbuster",
    "dirb",
    "dirsearch",
    "nikto",
    "nuclei",
    "wpscan",
    "sqlmap",
    "commix",
    "wfuzz",
    "curl",
    "wget",
    # Network
    "netcat",
    "nc",
    "socat",
    "tcpdump",
    "tshark",
    "enum4linux",
    "smbclient",
    "rpcclient",
    "nbtscan",
    # Exploit / post
    "msfconsole",
    "searchsploit",
    "john",
    "hashcat",
    "hydra",
    "medusa",
    "responder",
    "impacket-smbclient",
    # Wireless / misc
    "aircrack-ng",
    "reaver",
    "binwalk",
    "strings",
    "file",
    "xxd",
    "openssl",
    "gpg",
    "python3",
    "perl",
    "ruby",
)


@lru_cache(maxsize=1)
def discover_installed_tools() -> list[str]:
    """Return catalog tools found on PATH (Kali)."""
    found: list[str] = []
    seen: set[str] = set()
    for name in KALI_TOOL_CATALOG:
        if name in seen:
            continue
        if shutil.which(name):
            found.append(name)
            seen.add(name)
    return sorted(found)


def is_tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def list_all_tool_names() -> list[str]:
    """Structured + catalog names (deduplicated)."""
    names = set(KALI_TOOL_CATALOG) | STRUCTURED_TOOLS
    return sorted(names)
