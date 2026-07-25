#!/usr/bin/env bash
# KXNS Hunter CLI — Kali Linux 一键安装（硬编码，确定性）
# 已装工具跳过，未装工具通过 apt 白名单安装，blocklisted 工具仅提示不自动装
set -euo pipefail

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

log()   { echo -e "${CYAN}== $*${NC}"; }
warn()  { echo -e "${YELLOW}!! $*${NC}"; }
ok()    { echo -e "${GREEN}OK $*${NC}"; }
err()   { echo -e "${RED}ERR $*${NC}" >&2; }

echo -e "${GREEN}KXNS Hunter CLI — Kali 一键安装${NC}"

if [[ ! -f /etc/os-release ]] || ! grep -qi 'kali' /etc/os-release; then
    warn "未检测到 Kali Linux，部分工具安装可能不兼容。"
fi

# =============================================================================
# install_uv — 安装 uv 包管理器
# =============================================================================
install_uv() {
    if command -v uv >/dev/null 2>&1; then return 0; fi
    log "安装 uv..."
    curl -fsSL https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
    command -v uv >/dev/null 2>&1 || {
        err "uv 安装失败。手动执行: export PATH=\"\$HOME/.local/bin:\$PATH\""
        exit 1
    }
}

# =============================================================================
# ensure_venv — 创建 Python 虚拟环境
# =============================================================================
ensure_venv() {
    if [[ -d .venv ]] && [[ ! -f .venv/bin/activate ]]; then
        warn "检测到无效 .venv，正在重建..."
        rm -rf .venv
    fi
    install_uv
    log "同步 Python 依赖 (uv sync)..."
    uv sync
}

run_kxns() { uv run kxns "$@"; }

# =============================================================================
# [1/4] 系统基础设施（Python + ripgrep + curl + PostgreSQL + Redis）
# =============================================================================
log "[1/4] 系统基础设施"
sudo apt update -qq

INFRA_PKGS=(
    python3 python3-venv python3-dev
    ripgrep curl git bash
    postgresql postgresql-client postgresql-contrib
    redis-server redis-tools
    build-essential
)
for pkg in "${INFRA_PKGS[@]}"; do
    if dpkg -s "$pkg" &>/dev/null; then
        ok "已安装: $pkg"
    else
        log "安装: $pkg"
        sudo apt install -y "$pkg"
    fi
done

# =============================================================================
# [2/4] Kali 渗透工具（硬编码白名单）
# =============================================================================
log "[2/4] Kali 渗透工具"

# 白名单：APT_PACKAGE=BINARY（等号左是包名，右是检查的二进制）
# 已存在 → 跳过；不存在 → apt install
declare -A TOOLS=(
    # Recon
    ["nmap"]="nmap"
    ["masscan"]="masscan"
    ["subfinder"]="subfinder"
    ["amass"]="amass"
    ["dnsenum"]="dnsenum"
    ["dnsrecon"]="dnsrecon"
    ["theharvester"]="theHarvester"
    # Web / HTTP
    ["httpx-toolkit"]="httpx"
    ["whatweb"]="whatweb"
    ["wafw00f"]="wafw00f"
    ["gobuster"]="gobuster"
    ["ffuf"]="ffuf"
    ["feroxbuster"]="feroxbuster"
    ["dirb"]="dirb"
    ["dirsearch"]="dirsearch"
    ["wfuzz"]="wfuzz"
    # 漏洞扫描
    ["nuclei"]="nuclei"
    ["nikto"]="nikto"
    ["wpscan"]="wpscan"
    ["sqlmap"]="sqlmap"
    ["commix"]="commix"
    # Network
    ["enum4linux"]="enum4linux"
    ["smbclient"]="smbclient"
    ["netcat-openbsd"]="netcat"
    ["socat"]="socat"
    ["tcpdump"]="tcpdump"
    ["tshark"]="tshark"
    # CVE 搜索
    ["exploitdb"]="searchsploit"
    # 杂项
    ["openssl"]="openssl"
    ["xxd"]="xxd"
    ["binutils"]="strings"
)

INSTALLED_COUNT=0
SKIPPED_COUNT=0
FAILED_COUNT=0

for pkg in "${!TOOLS[@]}"; do
    bin="${TOOLS[$pkg]}"
    if command -v "$bin" &>/dev/null; then
        ((SKIPPED_COUNT++)) || true
        ok "已装: $bin"
        continue
    fi
    log "安装: $pkg → $bin"
    if sudo apt install -y "$pkg" 2>/dev/null; then
        if command -v "$bin" &>/dev/null; then
            ((INSTALLED_COUNT++)) || true
            ok "装毕: $bin"
        else
            ((FAILED_COUNT++)) || true
            warn "已 apt install $pkg 但 $bin 仍不在 PATH"
        fi
    else
        ((FAILED_COUNT++)) || true
        warn "安装失败: $pkg（非阻断，可手动安装）"
    fi
done

echo ""
echo -e "  工具统计: ${GREEN}已有=${SKIPPED_COUNT}${NC}  ${CYAN}新装=${INSTALLED_COUNT}${NC}  ${RED}失败=${FAILED_COUNT}${NC}"

# =============================================================================
# [2b/4] BLOCKLISTED 工具 — 仅提示，不自动安装
# =============================================================================
echo ""
log "以下工具需要手动安装（涉及密码爆破/漏洞利用，不自动装）："
echo "  hydra      → sudo apt install hydra"
echo "  medusa     → sudo apt install medusa"
echo "  john       → sudo apt install john"
echo "  hashcat    → sudo apt install hashcat"
echo "  metasploit → sudo apt install metasploit-framework"
echo "  responder  → sudo apt install responder"

# =============================================================================
# [3/4] Python 环境
# =============================================================================
log "[3/4] Python 环境"
ensure_venv
source .venv/bin/activate

# =============================================================================
# [4/4] 数据库 & 服务启动
# =============================================================================
log "[4/4] 数据库服务"
sudo systemctl enable --now postgresql 2>/dev/null || warn "PostgreSQL 服务启动失败"
sudo systemctl enable --now redis-server 2>/dev/null || warn "Redis 服务启动失败"

# PostgreSQL 初始化
if run_kxns doctor --fix 2>/dev/null; then
    ok "PostgreSQL + pgvector 初始化完成"
else
    warn "PostgreSQL 初始化未完成，可稍后: uv run kxns doctor --fix"
    warn "或使用内存存储: [blackboard] backend = \"memory\""
fi

# kxns doctor 诊断（含工具状态）
run_kxns doctor 2>/dev/null || true

# =============================================================================
# 完成
# =============================================================================
echo ""
ok "=== 安装完成 ==="
echo ""
echo "快速开始："
echo -e "  ${CYAN}source .venv/bin/activate${NC}"
echo -e "  ${CYAN}kxns api https://your-api.com/v1 sk-xxx gpt-4o${NC}"
echo -e "  ${CYAN}kxns${NC}"
echo ""
run_kxns --version 2>/dev/null || warn "kxns --version 失败，请检查 uv sync 输出"
