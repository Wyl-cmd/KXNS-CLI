Run a Kali Linux pentest tool against a target.

**Installed on this host:** ${INSTALLED_TOOLS}

## Usage

- Prefer structured tools with parsers: nmap, httpx, nuclei, subfinder, gobuster, ffuf, sqlmap
- For other Kali tools (nikto, wpscan, hydra, etc.), set `tool` to the binary name and use `extra_args`

## Rules (mandatory)

1. Output is evidence only — call **ReportFinding** separately for each real issue
2. Default status is `candidate`; use `confirmed` only after you reproduced the issue
3. **Never fabricate vulnerabilities** — if output is inconclusive, use severity=info
4. High/critical findings require reproducible curl/command POC in ReportFinding
