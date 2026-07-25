#!/usr/bin/env bash
# KXNS Hunter CLI — Kali 三遍验收脚本
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# 优先 uv run；若 .venv 可用则 activate
if [[ -f .venv/bin/activate ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

run_kxns() {
    uv run kxns "$@"
}

pass=0
fail=0

run_check() {
    local name="$1"
    shift
    echo ""
    echo "=== $name ==="
    if "$@"; then
        echo "[PASS] $name"
        pass=$((pass + 1))
    else
        echo "[FAIL] $name"
        fail=$((fail + 1))
    fi
}

round1() {
    run_kxns --version
    run_kxns doctor
    run_kxns scan --help
    uv run pytest \
        tests/test_scan_blackboard.py \
        tests/test_batch_fixes.py \
        tests/test_connectivity.py \
        tests/test_precheck_bundle.py \
        -q
}

round2() {
    uv run ruff check src/kxns_cli/scan src/kxns_cli/blackboard src/kxns_cli/infra
    uv run python -c "
from kxns_cli.scan.manager import ScanManager
from kxns_cli.tools.kali.base import KALI_ADAPTERS
assert len(KALI_ADAPTERS) >= 10
print('imports ok')
"
}

round3() {
    uv run pytest \
        tests/test_scan_blackboard.py \
        tests/test_batch_fixes.py \
        tests/test_finding_validation.py \
        tests/test_connectivity.py \
        tests/test_precheck_bundle.py \
        -q
    run_kxns scan bounty-export --help >/dev/null
    uv run python <<'PY'
import asyncio
import tempfile
from pathlib import Path

from kaos.path import KaosPath

from kxns_cli.config import Config
from kxns_cli.scan.manager import ScanManager
from kxns_cli.scan.models import ScanConfig


async def main() -> None:
    d = tempfile.mkdtemp()
    manager = ScanManager(Config(), KaosPath.unsafe_from_local_path(d))
    result = await manager.start_scan(
        "https://example.com",
        ScanConfig(wildcard=False, guaranteed=False, phased=False, swarm=False),
        skip_precheck=True,
    )
    assert result.status.value == "completed"
    assert Path(result.report_json_path or "").is_file()
    print("scan smoke ok")


asyncio.run(main())
PY
}

run_check "Round 1: CLI + doctor + scan tests" round1
run_check "Round 2: lint + module imports" round2
run_check "Round 3: integration smoke" round3

echo ""
echo "验收汇总: ${pass} 通过, ${fail} 失败"
if [[ "$fail" -gt 0 ]]; then
    exit 1
fi
echo "三遍验收全部通过。"
