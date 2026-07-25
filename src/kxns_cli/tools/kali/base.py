from __future__ import annotations

import json
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from kxns_cli.scan.models import Finding, FindingSeverity, FindingStatus


@dataclass
class KaliToolResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    findings: list[Finding] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.findings is None:
            self.findings = []


class KaliToolAdapter(ABC):
    name: str
    command_template: str
    default_timeout: int = 120

    @abstractmethod
    def build_command(self, target: str, **kwargs: Any) -> str:
        raise NotImplementedError

    @abstractmethod
    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def to_findings(self, parsed: list[dict[str, Any]], engagement_id: Any) -> list[dict[str, Any]]:
        return parsed


class NmapAdapter(KaliToolAdapter):
    name = "nmap"
    command_template = "nmap -sV -T4 {target}"

    def build_command(self, target: str, **kwargs: Any) -> str:
        ports = kwargs.get("ports", "")
        if ports:
            return f"nmap -sV -T4 -p {shlex.quote(str(ports))} {shlex.quote(target)}"
        return f"nmap -sV -T4 {shlex.quote(target)}"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in stdout.splitlines():
            if "/tcp" in line and "open" in line:
                findings.append(
                    {
                        "title": f"Open port on {target}",
                        "severity": FindingSeverity.INFO.value,
                        "description": line.strip(),
                        "status": FindingStatus.CANDIDATE.value,
                    }
                )
        return findings


class HttpxAdapter(KaliToolAdapter):
    name = "httpx"
    command_template = "httpx -silent -status-code -title -tech-detect"

    def build_command(self, target: str, **kwargs: Any) -> str:
        return f"echo {shlex.quote(target)} | httpx -silent -status-code -title -tech-detect"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in stdout.splitlines():
            if line.strip():
                findings.append(
                    {
                        "title": "Live HTTP service",
                        "severity": FindingSeverity.INFO.value,
                        "description": line.strip(),
                        "status": FindingStatus.CANDIDATE.value,
                    }
                )
        return findings


class NucleiAdapter(KaliToolAdapter):
    name = "nuclei"
    command_template = "nuclei -u {target} -silent -jsonl"

    def build_command(self, target: str, **kwargs: Any) -> str:
        severity = kwargs.get("severity", "high,critical")
        return f"nuclei -u {shlex.quote(target)} -silent -jsonl -severity {shlex.quote(severity)}"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONError:
                continue
            sev = str(item.get("info", {}).get("severity", "medium")).lower()
            findings.append(
                {
                    "title": item.get("info", {}).get("name", "nuclei finding"),
                    "severity": sev,
                    "description": item.get("matched-at", target),
                    "poc": line,
                    "status": FindingStatus.CANDIDATE.value,
                }
            )
        return findings


class SubfinderAdapter(KaliToolAdapter):
    name = "subfinder"
    command_template = "subfinder -d {target} -silent"

    def build_command(self, target: str, **kwargs: Any) -> str:
        domain = target.replace("https://", "").replace("http://", "").split("/")[0]
        return f"subfinder -d {shlex.quote(domain)} -silent"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        return [
            {
                "title": "Discovered subdomain",
                "severity": FindingSeverity.INFO.value,
                "description": line.strip(),
                "status": FindingStatus.CANDIDATE.value,
            }
            for line in stdout.splitlines()
            if line.strip()
        ]


class GobusterAdapter(KaliToolAdapter):
    name = "gobuster"
    command_template = "gobuster dir -u {target} -w /usr/share/wordlists/dirb/common.txt -q"

    def build_command(self, target: str, **kwargs: Any) -> str:
        wordlist = kwargs.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        return f"gobuster dir -u {shlex.quote(target)} -w {shlex.quote(wordlist)} -q -b 404,403"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in stdout.splitlines():
            if line.strip().startswith("/"):
                findings.append(
                    {
                        "title": "Discovered path",
                        "severity": FindingSeverity.INFO.value,
                        "description": f"{target}{line.strip()}",
                        "status": FindingStatus.CANDIDATE.value,
                    }
                )
        return findings


class FfufAdapter(KaliToolAdapter):
    name = "ffuf"
    command_template = "ffuf -u {target}/FUZZ -w wordlist.txt -mc 200,301,302 -s"

    def build_command(self, target: str, **kwargs: Any) -> str:
        wordlist = kwargs.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        return (
            f"ffuf -u {shlex.quote(target.rstrip('/') + '/FUZZ')} "
            f"-w {shlex.quote(wordlist)} -mc 200,301,302,403 -s -json"
        )

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        try:
            data = json.loads(stdout)
            for result in data.get("results", []):
                url = result.get("url", target)
                findings.append(
                    {
                        "title": "FFuf match",
                        "severity": FindingSeverity.INFO.value,
                        "description": url,
                        "status": FindingStatus.CANDIDATE.value,
                    }
                )
        except json.JSONDecodeError:
            pass
        return findings


class SqlmapAdapter(KaliToolAdapter):
    name = "sqlmap"
    command_template = "sqlmap -u {target} --batch --level=1 --risk=1"

    def build_command(self, target: str, **kwargs: Any) -> str:
        return f"sqlmap -u {shlex.quote(target)} --batch --level=1 --risk=1 --forms"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        combined = stdout + stderr
        if "is vulnerable" in combined.lower() or "sql injection" in combined.lower():
            findings.append(
                {
                    "title": "SQL injection (sqlmap)",
                    "severity": FindingSeverity.HIGH.value,
                    "description": combined[-2000:],
                    "status": FindingStatus.CANDIDATE.value,
                }
            )
        return findings


KALI_ADAPTERS: dict[str, KaliToolAdapter] = {
    "nmap": NmapAdapter(),
    "httpx": HttpxAdapter(),
    "nuclei": NucleiAdapter(),
    "subfinder": SubfinderAdapter(),
    "gobuster": GobusterAdapter(),
    "ffuf": FfufAdapter(),
    "sqlmap": SqlmapAdapter(),
}


class NiktoAdapter(KaliToolAdapter):
    name = "nikto"
    command_template = "nikto -h {target} -Format txt"

    def build_command(self, target: str, **kwargs: Any) -> str:
        host = target.replace("https://", "").replace("http://", "").split("/")[0]
        return f"nikto -h {shlex.quote(host)} -Format txt -nointeractive"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in (stdout + stderr).splitlines():
            low = line.lower()
            if "+ " in line or "osvdb" in low or "vulnerability" in low:
                sev = FindingSeverity.MEDIUM.value
                if "critical" in low or "rce" in low:
                    sev = FindingSeverity.HIGH.value
                findings.append(
                    {
                        "title": f"Nikto: {line.strip()[:120]}",
                        "severity": sev,
                        "description": line.strip(),
                        "status": FindingStatus.CANDIDATE.value,
                    }
                )
        return findings


class WpscanAdapter(KaliToolAdapter):
    name = "wpscan"
    command_template = "wpscan --url {target} --enumerate vp,vt,u"

    def build_command(self, target: str, **kwargs: Any) -> str:
        return f"wpscan --url {shlex.quote(target)} --enumerate vp,vt,u --no-update -f json"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return findings
        for vuln in data.get("version", {}).get("vulnerabilities", []):
            findings.append(
                {
                    "title": f"WPScan: {vuln.get('title', 'WordPress vuln')}",
                    "severity": FindingSeverity.HIGH.value,
                    "description": str(vuln),
                    "status": FindingStatus.CANDIDATE.value,
                }
            )
        for plugin in data.get("plugins", {}).values():
            for vuln in plugin.get("vulnerabilities", []):
                findings.append(
                    {
                        "title": f"WPScan plugin: {vuln.get('title', 'plugin vuln')}",
                        "severity": FindingSeverity.MEDIUM.value,
                        "description": str(vuln),
                        "status": FindingStatus.CANDIDATE.value,
                    }
                )
        return findings


class HydraAdapter(KaliToolAdapter):
    name = "hydra"
    command_template = "hydra -L users.txt -P pass.txt {target} ssh"

    def build_command(self, target: str, **kwargs: Any) -> str:
        service = kwargs.get("service", "ssh")
        user = kwargs.get("user", "root")
        wordlist = kwargs.get("wordlist", "/usr/share/wordlists/rockyou.txt")
        host = target.replace("https://", "").replace("http://", "").split("/")[0]
        return (
            f"hydra -l {shlex.quote(str(user))} -P {shlex.quote(wordlist)} "
            f"{shlex.quote(host)} {shlex.quote(str(service))} -t 4 -f"
        )

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        combined = stdout + stderr
        for line in combined.splitlines():
            if "login:" in line.lower() or "password:" in line.lower():
                findings.append(
                    {
                        "title": "Hydra credential found",
                        "severity": FindingSeverity.HIGH.value,
                        "description": line.strip(),
                        "poc": line.strip(),
                        "status": FindingStatus.CANDIDATE.value,
                    }
                )
        return findings


class DirbAdapter(KaliToolAdapter):
    name = "dirb"
    command_template = "dirb {target}"

    def build_command(self, target: str, **kwargs: Any) -> str:
        wordlist = kwargs.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        return f"dirb {shlex.quote(target)} {shlex.quote(wordlist)} -S -r"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in (stdout + stderr).splitlines():
            if "+ " in line and "http" in line.lower():
                findings.append(
                    {
                        "title": f"Dirb: {line.strip()[:100]}",
                        "severity": FindingSeverity.INFO.value,
                        "description": line.strip(),
                        "status": FindingStatus.CANDIDATE.value,
                    }
                )
        return findings


class MasscanAdapter(KaliToolAdapter):
    name = "masscan"
    command_template = "masscan {target} -p1-65535 --rate 1000"

    def build_command(self, target: str, **kwargs: Any) -> str:
        host = target.replace("https://", "").replace("http://", "").split("/")[0]
        ports = kwargs.get("ports", "1-65535")
        rate = kwargs.get("rate", "1000")
        return f"masscan {shlex.quote(host)} -p{ports} --rate {rate}"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in (stdout + stderr).splitlines():
            if "Discovered open port" in line:
                findings.append(
                    {
                        "title": f"Masscan: {line.strip()[:100]}",
                        "severity": FindingSeverity.INFO.value,
                        "description": line.strip(),
                        "status": FindingStatus.CANDIDATE.value,
                    }
                )
        return findings


KALI_ADAPTERS.update(
    {
        "nikto": NiktoAdapter(),
        "wpscan": WpscanAdapter(),
        "hydra": HydraAdapter(),
        "dirb": DirbAdapter(),
        "masscan": MasscanAdapter(),
    }
)


class AmassAdapter(KaliToolAdapter):
    name = "amass"
    command_template = "amass enum -d {target}"

    def build_command(self, target: str, **kwargs: Any) -> str:
        domain = target.replace("https://", "").replace("http://", "").split("/")[0]
        return f"amass enum -d {shlex.quote(domain)} -silent"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        return [
            {
                "title": f"Amass: {line.strip()[:120]}",
                "severity": FindingSeverity.INFO.value,
                "description": line.strip(),
                "status": FindingStatus.CANDIDATE.value,
            }
            for line in stdout.splitlines()
            if line.strip() and not line.startswith("[")
        ]


class Wafw00fAdapter(KaliToolAdapter):
    name = "wafw00f"
    command_template = "wafw00f {target}"

    def build_command(self, target: str, **kwargs: Any) -> str:
        return f"wafw00f {shlex.quote(target)}"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in (stdout + stderr).splitlines():
            low = line.lower()
            if "is behind" in low or "waf" in low or "firewall" in low:
                findings.append(
                    {
                        "title": f"WAF detected: {line.strip()[:120]}",
                        "severity": FindingSeverity.INFO.value,
                        "description": line.strip(),
                        "status": FindingStatus.CANDIDATE.value,
                    }
                )
        return findings


class WhatwebAdapter(KaliToolAdapter):
    name = "whatweb"
    command_template = "whatweb {target}"

    def build_command(self, target: str, **kwargs: Any) -> str:
        return f"whatweb {shlex.quote(target)}"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in (stdout + stderr).splitlines():
            if line.strip():
                findings.append(
                    {
                        "title": f"WhatWeb: {line.strip()[:120]}",
                        "severity": FindingSeverity.INFO.value,
                        "description": line.strip(),
                        "status": FindingStatus.CANDIDATE.value,
                    }
                )
        return findings


class FeroxbusterAdapter(KaliToolAdapter):
    name = "feroxbuster"
    command_template = "feroxbuster -u {target}"

    def build_command(self, target: str, **kwargs: Any) -> str:
        wordlist = kwargs.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        return f"feroxbuster -u {shlex.quote(target)} -w {shlex.quote(wordlist)} --silent --json"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            findings.append(
                {
                    "title": f"Feroxbuster: {item.get('url', target)[:120]}",
                    "severity": FindingSeverity.INFO.value,
                    "description": item.get("url", target),
                    "status": FindingStatus.CANDIDATE.value,
                }
            )
        return findings


class CommixAdapter(KaliToolAdapter):
    name = "commix"
    command_template = "commix --url {target} --batch"

    def build_command(self, target: str, **kwargs: Any) -> str:
        return f"commix --url {shlex.quote(target)} --batch"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        combined = stdout + stderr
        if "vulnerable" in combined.lower() or "command injection" in combined.lower():
            findings.append(
                {
                    "title": "Command injection (commix)",
                    "severity": FindingSeverity.HIGH.value,
                    "description": combined[-2000:],
                    "status": FindingStatus.CANDIDATE.value,
                }
            )
        return findings


class WfuzzAdapter(KaliToolAdapter):
    name = "wfuzz"
    command_template = "wfuzz -c -z file,wordlist.txt --hc 404 {target}/FUZZ"

    def build_command(self, target: str, **kwargs: Any) -> str:
        wordlist = kwargs.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        return (
            f"wfuzz -c -z file,{shlex.quote(wordlist)} "
            f"--hc 404 {shlex.quote(target.rstrip('/') + '/FUZZ')}"
        )

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in stderr.splitlines():
            if line.startswith("*") or line.startswith("0") and "C=" in line:
                continue
            if "C=" in line and "W=" in line:
                findings.append(
                    {
                        "title": f"Wfuzz: {line.strip()[:120]}",
                        "severity": FindingSeverity.INFO.value,
                        "description": line.strip(),
                        "status": FindingStatus.CANDIDATE.value,
                    }
                )
        return findings


class Enum4linuxAdapter(KaliToolAdapter):
    name = "enum4linux"
    command_template = "enum4linux {target}"

    def build_command(self, target: str, **kwargs: Any) -> str:
        host = target.replace("https://", "").replace("http://", "").split("/")[0]
        return f"enum4linux {shlex.quote(host)}"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        combined = stdout + stderr
        # Look for key enum4linux findings
        for keyword in ["sharename", "User:", "Group:", "SID:", "OS:Workgroup"]:
            for line in combined.splitlines():
                if keyword.lower() in line.lower():
                    findings.append(
                        {
                            "title": f"enum4linux {keyword}: {line.strip()[:120]}",
                            "severity": FindingSeverity.INFO.value,
                            "description": line.strip(),
                            "status": FindingStatus.CANDIDATE.value,
                        }
                    )
                    break
        return findings


class DnsenumAdapter(KaliToolAdapter):
    name = "dnsenum"
    command_template = "dnsenum {target}"

    def build_command(self, target: str, **kwargs: Any) -> str:
        domain = target.replace("https://", "").replace("http://", "").split("/")[0]
        return f"dnsenum {shlex.quote(domain)}"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        return [
            {
                "title": f"dnsenum: {line.strip()[:120]}",
                "severity": FindingSeverity.INFO.value,
                "description": line.strip(),
                "status": FindingStatus.CANDIDATE.value,
            }
            for line in stdout.splitlines()
            if line.strip() and not line.startswith("dnsenum")
        ][:50]


class SearchsploitAdapter(KaliToolAdapter):
    name = "searchsploit"
    command_template = "searchsploit {query}"

    def build_command(self, target: str, **kwargs: Any) -> str:
        query = kwargs.get("query", target)
        return f"searchsploit {shlex.quote(str(query))}"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in stdout.splitlines():
            line = line.strip()
            if " | " in line and ".py" not in line and ".rb" not in line:
                findings.append(
                    {
                        "title": f"searchsploit: {line[:120]}",
                        "severity": FindingSeverity.INFO.value,
                        "description": line,
                        "status": FindingStatus.CANDIDATE.value,
                    }
                )
        return findings


class ResponderAdapter(KaliToolAdapter):
    name = "responder"
    command_template = "responder -I {interface}"

    def build_command(self, target: str, **kwargs: Any) -> str:
        iface = kwargs.get("interface", "eth0")
        return f"responder -I {shlex.quote(str(iface))} -A -w"

    def parse_output(self, stdout: str, stderr: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        combined = stdout + stderr
        for line in combined.splitlines():
            low = line.lower()
            if any(k in low for k in ["hash", "ntlm", "captured", "cleartext", "basic auth"]):
                findings.append(
                    {
                        "title": f"Responder: {line.strip()[:120]}",
                        "severity": FindingSeverity.HIGH.value,
                        "description": line.strip(),
                        "poc": line.strip(),
                        "status": FindingStatus.CANDIDATE.value,
                    }
                )
        return findings


KALI_ADAPTERS.update(
    {
        "amass": AmassAdapter(),
        "wafw00f": Wafw00fAdapter(),
        "whatweb": WhatwebAdapter(),
        "feroxbuster": FeroxbusterAdapter(),
        "commix": CommixAdapter(),
        "wfuzz": WfuzzAdapter(),
        "enum4linux": Enum4linuxAdapter(),
        "dnsenum": DnsenumAdapter(),
        "searchsploit": SearchsploitAdapter(),
        "responder": ResponderAdapter(),
    }
)
