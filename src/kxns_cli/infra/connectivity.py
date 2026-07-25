"""Connectivity probes with actionable fix hints for Web UI and CLI."""

from __future__ import annotations

import asyncio
import shutil
import socket
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from kxns_cli.config import Config

# PortSwigger Burp Suite MCP extension defaults (SSE at root URL)
BURP_MCP_HOST = "127.0.0.1"
BURP_MCP_PORT = 9876
BURP_MCP_URL = f"http://{BURP_MCP_HOST}:{BURP_MCP_PORT}"
BURP_MCP_TRANSPORT = "sse"


def burp_mcp_server_config() -> dict[str, str]:
    """Canonical mcp.json entry for the official Burp MCP extension."""
    return {"url": BURP_MCP_URL, "transport": BURP_MCP_TRANSPORT}


def normalize_mcp_server_config(name: str, server: dict[str, Any]) -> dict[str, Any]:
    """Apply transport defaults for known remote MCP servers (e.g. Burp SSE)."""
    normalized = dict(server)
    if "url" not in normalized:
        return normalized
    url = str(normalized["url"]).rstrip("/")
    is_burp = "burp" in name.lower() or url.startswith(BURP_MCP_URL.rstrip("/"))
    if is_burp and normalized.get("transport") is None:
        normalized["transport"] = BURP_MCP_TRANSPORT
        if not normalized.get("url"):
            normalized["url"] = BURP_MCP_URL
    return normalized


class DiagnosticResult(BaseModel):
    ok: bool
    name: str
    message: str = ""
    fix_hints: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


@dataclass
class _ToolSpec:
    required: bool
    package: str
    fix: str


_KALI_TOOLS: dict[str, _ToolSpec] = {
    "python3": _ToolSpec(True, "python3", "sudo apt install python3 python3-venv"),
    "bash": _ToolSpec(True, "bash", "sudo apt install bash"),
    "rg": _ToolSpec(True, "ripgrep", "sudo apt install ripgrep"),
    "curl": _ToolSpec(True, "curl", "sudo apt install curl"),
    "nmap": _ToolSpec(True, "nmap", "sudo apt install nmap"),
    "subfinder": _ToolSpec(False, "subfinder", "sudo apt install subfinder 或 go install"),
    "httpx": _ToolSpec(False, "httpx-toolkit", "sudo apt install httpx-toolkit"),
    "ffuf": _ToolSpec(False, "ffuf", "sudo apt install ffuf"),
    "nuclei": _ToolSpec(False, "nuclei", "sudo apt install nuclei"),
    "sqlmap": _ToolSpec(False, "sqlmap", "sudo apt install sqlmap"),
    "psql": _ToolSpec(False, "postgresql", "sudo apt install postgresql postgresql-contrib"),
    "redis-cli": _ToolSpec(False, "redis-server", "sudo apt install redis-server"),
}


def _hint_auth_error(exc: Exception) -> list[str]:
    msg = str(exc).lower()
    if "401" in msg or "unauthorized" in msg or "invalid api key" in msg:
        return [
            "API Key 无效或过期，请在设置中更新 Key",
            "确认 Key 对应正确的服务商（OpenAI/DeepSeek/等）",
            "如使用代理网关，确认网关账户有余额",
        ]
    if "404" in msg or "not found" in msg:
        return [
            "模型名称或 API URL 可能错误",
            "OpenAI 兼容接口 URL 应为 https://xxx/v1（不要带 /chat/completions）",
            "检查模型 ID 是否与服务商文档一致",
        ]
    if "connection" in msg or "timeout" in msg or "connect" in msg:
        return [
            "网络无法访问 API 地址，检查代理/VPN/防火墙",
            "在 Kali 上运行: curl -I <你的API_URL>",
            "如在内网，确认 DNS 与出站 443 端口可用",
        ]
    return ["查看完整错误信息；运行 kxns doctor 检查环境"]


def _looks_masked(key: str) -> bool:
    return not key or key == "****" or ("..." in key and len(key) <= 20)


async def probe_llm(
    *,
    model_key: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model_id: str | None = None,
    provider_type: str | None = None,
) -> DiagnosticResult:
    from kosong._generate import generate
    from kosong.message import Message, TextPart
    from pydantic import SecretStr

    from kxns_cli.config import LLMModel, LLMProvider, load_config
    from kxns_cli.llm import create_llm

    config = load_config()
    key = model_key or config.default_model

    if base_url and api_key and model_id and not _looks_masked(api_key):
        provider = LLMProvider(
            type=provider_type or "openai_legacy",  # type: ignore[arg-type]
            base_url=base_url.rstrip("/"),
            api_key=SecretStr(api_key),
        )
        model = LLMModel(provider=key or model_id, model=model_id, max_context_size=128000)
    elif key and key in config.models:
        model = config.models[key].model_copy(deep=True)
        provider_cfg = config.providers.get(model.provider)
        if provider_cfg is None:
            return DiagnosticResult(
                ok=False,
                name=f"llm:{key}",
                message=f"Provider '{model.provider}' 未配置",
                fix_hints=[
                    "在设置中填写 API URL 与 Key 后保存",
                    "或运行: kxns api <url> <key> <model>",
                ],
            )
        provider = provider_cfg.model_copy(deep=True)
        if base_url:
            provider.base_url = base_url.rstrip("/")
        if model_id:
            model.model = model_id
        if api_key and not _looks_masked(api_key):
            provider.api_key = SecretStr(api_key)
    elif base_url and model_id and (api_key is None or _looks_masked(api_key)):
        return DiagnosticResult(
            ok=False,
            name="llm",
            message="新建模型需要填写 API Key",
            fix_hints=["在设置中输入完整 API Key 后保存", "不能仅使用掩码占位符创建新模型"],
        )
    else:
        return DiagnosticResult(
            ok=False,
            name="llm",
            message="未配置大模型",
            fix_hints=[
                "Web 设置 → 大模型 → 填写 API URL / Key / 模型名 → 保存",
                "CLI: kxns api https://api.openai.com/v1 sk-xxx gpt-4o",
            ],
        )

    llm = create_llm(provider, model)
    if llm is None:
        return DiagnosticResult(
            ok=False,
            name=f"llm:{key}",
            message="LLM 配置不完整（缺少 base_url 或 model）",
            fix_hints=["填写 API Base URL 和模型名称", "URL 示例: https://api.openai.com/v1"],
        )

    try:
        result = await asyncio.wait_for(
            generate(
                llm.chat_provider,
                "You are a connectivity test.",
                [],
                [Message(role="user", content=[TextPart(text="Reply with exactly: OK")])],
            ),
            timeout=45.0,
        )
        text = ""
        if result.message.content:
            for part in result.message.content:
                if hasattr(part, "text"):
                    text += part.text
        return DiagnosticResult(
            ok=True,
            name=f"llm:{llm.model_name}",
            message="连接成功，模型响应正常",
            details={"response_preview": (text or "")[:120], "model": llm.model_name},
        )
    except Exception as exc:
        return DiagnosticResult(
            ok=False,
            name=f"llm:{llm.model_name}",
            message=f"连接失败: {type(exc).__name__}: {exc}",
            fix_hints=_hint_auth_error(exc),
        )


async def probe_mcp_config(name: str, server: dict[str, Any]) -> DiagnosticResult:
    """Test MCP server config without persisting to mcp.json."""
    import fastmcp

    server = normalize_mcp_server_config(name, server)
    try:
        client = fastmcp.Client({"mcpServers": {name: server}})

        async def _connect() -> list:
            async with client:
                return await client.list_tools()

        tools = await asyncio.wait_for(_connect(), timeout=30.0)
        return DiagnosticResult(
            ok=True,
            name=f"mcp:{name}",
            message=f"连接成功，{len(tools)} 个工具可用",
            details={"tools": [t.name for t in tools[:20]]},
        )
    except TimeoutError:
        return DiagnosticResult(
            ok=False,
            name=f"mcp:{name}",
            message="连接超时（30s）",
            fix_hints=_mcp_fix_hints(name, server),
        )
    except Exception as exc:
        return DiagnosticResult(
            ok=False,
            name=f"mcp:{name}",
            message=f"连接失败: {type(exc).__name__}: {exc}",
            fix_hints=_mcp_fix_hints(name, server),
        )


def _mcp_fix_hints(name: str, server: dict[str, Any]) -> list[str]:
    hints = [
        "stdio: 在终端手动运行 command 检查是否报错",
        "HTTP: curl -I <mcp_url> 检查可达性",
    ]
    if "burp" in name.lower() or BURP_MCP_URL in str(server.get("url", "")).rstrip("/"):
        hints.extend(
            [
                f"确认 Burp MCP 扩展已启动并监听 {BURP_MCP_URL}",
                (
                    "mcp.json 需含 transport="
                    f"{BURP_MCP_TRANSPORT!r}（Burp 用 SSE，非 Streamable HTTP）"
                ),
                "Web 设置 → MCP → 使用 burp 预设（端口 9876）",
                "Burp → Extensions → MCP Server → 启用 Server",
            ]
        )
    return hints


async def probe_mcp_server(name: str) -> DiagnosticResult:
    from kxns_cli.mcp_store import get_mcp_server

    try:
        server = get_mcp_server(name)
    except KeyError:
        return DiagnosticResult(
            ok=False,
            name=f"mcp:{name}",
            message=f"MCP '{name}' 不存在",
            fix_hints=["在 MCP 设置中添加服务器", "CLI: kxns mcp add ..."],
        )
    return await probe_mcp_config(name, server)


def probe_kali_tool(tool: str) -> DiagnosticResult:
    spec = _KALI_TOOLS.get(tool)
    if spec is None:
        found = shutil.which(tool) is not None
        return DiagnosticResult(
            ok=found,
            name=f"tool:{tool}",
            message="可用" if found else "未找到",
            fix_hints=[] if found else [f"sudo apt install {tool}"],
        )
    found = shutil.which(tool) is not None
    if found:
        return DiagnosticResult(ok=True, name=f"tool:{tool}", message=f"{tool} 已安装")
    return DiagnosticResult(
        ok=not spec.required,
        name=f"tool:{tool}",
        message=f"{'必需' if spec.required else '可选'}工具缺失: {tool}",
        fix_hints=[spec.fix],
    )


def probe_all_kali_tools() -> list[DiagnosticResult]:
    return [probe_kali_tool(name) for name in _KALI_TOOLS]


async def probe_blackboard(config: Config | None = None) -> DiagnosticResult:
    from kxns_cli.blackboard import create_blackboard_store
    from kxns_cli.config import load_config

    config = config or load_config()
    bb = config.blackboard
    if bb is None or not bb.enabled:
        return DiagnosticResult(ok=True, name="blackboard", message="Blackboard 已禁用（内存模式）")

    if bb.backend == "memory":
        return DiagnosticResult(
            ok=True,
            name="blackboard",
            message="使用内存 Blackboard（无需 PostgreSQL）",
        )

    store = await create_blackboard_store(config)
    try:
        await store.connect()
        return DiagnosticResult(
            ok=True,
            name="blackboard",
            message=f"PostgreSQL 连接成功 ({bb.host}:{bb.port}/{bb.database})",
        )
    except Exception as exc:
        return DiagnosticResult(
            ok=False,
            name="blackboard",
            message=f"PostgreSQL 连接失败: {exc}",
            fix_hints=[
                "sudo systemctl start postgresql",
                "kxns doctor --fix  初始化 kxns 用户/库",
                '或在 config.toml 设置 [blackboard] backend = "memory"',
            ],
        )
    finally:
        await store.close()


async def probe_redis() -> DiagnosticResult:
    from kxns_cli.config import load_config
    from kxns_cli.infra.redis import RedisRateLimiter

    config = load_config()
    if not config.scan.redis_enabled:
        return DiagnosticResult(ok=True, name="redis", message="Redis 限流已禁用")

    limiter = RedisRateLimiter(url=config.scan.redis_url)
    await limiter.connect()
    if limiter._client is None:
        return DiagnosticResult(
            ok=False,
            name="redis",
            message="无法连接 Redis",
            fix_hints=[
                "sudo systemctl start redis-server",
                f"检查 {config.scan.redis_url}",
                "或在 config.toml 设置 scan.redis_enabled = false",
            ],
        )
    await limiter.close()
    return DiagnosticResult(ok=True, name="redis", message="Redis 连接正常")


def probe_burp_mcp(host: str = BURP_MCP_HOST, port: int = BURP_MCP_PORT) -> DiagnosticResult:
    """Probe Burp MCP HTTP port (default 9876)."""
    return probe_port_open(host, port, label="burp-mcp")


def probe_burp_rest(host: str = "127.0.0.1", port: int = 1337) -> DiagnosticResult:
    url = f"http://{host}:{port}/"
    try:
        with urlopen(Request(url, method="GET"), timeout=3) as resp:
            ok = resp.status < 500
        return DiagnosticResult(
            ok=ok,
            name="burp-rest",
            message=f"Burp REST API 可达 ({url})" if ok else "Burp 响应异常",
            fix_hints=[] if ok else ["在 Burp 中启用 REST API 扩展", "默认端口 1337"],
        )
    except (URLError, TimeoutError, OSError) as exc:
        return DiagnosticResult(
            ok=False,
            name="burp-rest",
            message=f"Burp REST 不可达: {exc}",
            fix_hints=[
                "启动 Burp Suite Professional",
                "Extensions → REST API → 启用监听 127.0.0.1:1337",
                "或通过 MCP 方式接入 Burp（设置 → MCP → 添加 burp）",
            ],
        )


def probe_port_open(host: str, port: int, *, label: str) -> DiagnosticResult:
    try:
        with socket.create_connection((host, port), timeout=3):
            return DiagnosticResult(ok=True, name=label, message=f"{host}:{port} 可达")
    except OSError as exc:
        return DiagnosticResult(
            ok=False,
            name=label,
            message=f"{host}:{port} 不可达: {exc}",
            fix_hints=[f"确认 {label} 服务已启动并监听 {port}"],
        )


def probe_kali_catalog() -> DiagnosticResult:
    from kxns_cli.tools.kali.registry import discover_installed_tools, list_all_tool_names

    installed = discover_installed_tools()
    catalog = len(list_all_tool_names())
    ok = len(installed) >= 5
    return DiagnosticResult(
        ok=ok,
        name="kali-catalog",
        message=f"已发现 {len(installed)}/{catalog} 个 Kali 工具在 PATH",
        details={"installed": installed[:40], "total_installed": len(installed)},
        fix_hints=[] if ok else ["在 Kali Linux 上运行: sudo apt update && kxns doctor"],
    )


def probe_builtin_runtime() -> DiagnosticResult:
    """Shell / Python runtime used by built-in tools."""
    missing = [t for t in ("python3", "bash", "curl") if shutil.which(t) is None]
    if missing:
        return DiagnosticResult(
            ok=False,
            name="builtin-runtime",
            message=f"内置工具依赖缺失: {', '.join(missing)}",
            fix_hints=[f"sudo apt install {' '.join(missing)}"],
        )
    return DiagnosticResult(
        ok=True,
        name="builtin-runtime",
        message="内置运行时就绪 (python3/bash/curl)",
    )


async def run_full_diagnostics(config: Config | None = None) -> list[DiagnosticResult]:
    results: list[DiagnosticResult] = []
    results.append(probe_builtin_runtime())
    results.extend(probe_all_kali_tools())
    results.append(probe_kali_catalog())
    results.append(await probe_blackboard(config))
    results.append(await probe_redis())
    results.append(probe_burp_mcp())
    results.append(probe_burp_rest())
    results.append(probe_port_open("127.0.0.1", 5432, label="postgresql"))

    config_llm = await probe_llm()
    results.append(config_llm)

    from kxns_cli.mcp_store import list_mcp_servers

    for name in list_mcp_servers():
        results.append(await probe_mcp_server(name))

    return results
