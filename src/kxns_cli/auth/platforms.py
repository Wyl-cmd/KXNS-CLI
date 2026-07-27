"""平台与模型目录：对齐 kimi-cli 的 setup / list_models 接口。"""

from __future__ import annotations

from typing import Any, NamedTuple, cast

import aiohttp
from pydantic import BaseModel

from kxns_cli.llm import ModelCapability
from kxns_cli.utils.aiohttp import new_client_session
from kxns_cli.utils.logging import logger


class ModelInfo(BaseModel):
    """模型信息（API /models 或本地目录）。"""

    id: str
    context_length: int
    supports_reasoning: bool = False
    supports_image_in: bool = False
    supports_video_in: bool = False
    display_name: str | None = None

    @property
    def capabilities(self) -> set[ModelCapability]:
        caps: set[ModelCapability] = set()
        if self.supports_reasoning:
            caps.add("thinking")
        if "thinking" in self.id.lower() or "reason" in self.id.lower():
            caps.update(("thinking", "always_thinking"))
        if self.supports_image_in:
            caps.add("image_in")
        if self.supports_video_in:
            caps.add("video_in")
        return caps

    # --- Web lookup_model_info 兼容别名 ---
    @property
    def name(self) -> str:
        return self.id

    @property
    def max_context_size(self) -> int:
        return self.context_length or 128000

    @property
    def supports_thinking(self) -> bool:
        return "thinking" in self.capabilities

    @property
    def supports_image_input(self) -> bool:
        return self.supports_image_in


class Platform(NamedTuple):
    id: str
    name: str
    base_url: str
    search_url: str | None = None
    fetch_url: str | None = None
    allowed_prefixes: list[str] | None = None
    provider_type: str = "openai_legacy"


def _mi(
    model_id: str,
    display: str,
    ctx: int,
    *,
    thinking: bool = False,
    image: bool = False,
) -> ModelInfo:
    return ModelInfo(
        id=model_id,
        display_name=display,
        context_length=ctx,
        supports_reasoning=thinking,
        supports_image_in=image,
    )


# 本地目录：API 失败时回落；lookup_model_info 也用它
_CATALOG: dict[str, list[ModelInfo]] = {
    "openai": [
        _mi("gpt-4o", "GPT-4o", 128000, image=True),
        _mi("gpt-4o-mini", "GPT-4o Mini", 128000, image=True),
        _mi("gpt-4-turbo", "GPT-4 Turbo", 128000, image=True),
        _mi("gpt-4", "GPT-4", 8192),
        _mi("gpt-4-32k", "GPT-4 32K", 32768),
        _mi("gpt-3.5-turbo", "GPT-3.5 Turbo", 16385, image=True),
        _mi("o1", "O1", 200000, thinking=True, image=True),
        _mi("o1-mini", "O1 Mini", 128000, thinking=True, image=True),
        _mi("o1-pro", "O1 Pro", 200000, thinking=True, image=True),
        _mi("o3-mini", "O3 Mini", 200000, thinking=True, image=True),
    ],
    "anthropic": [
        _mi("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", 200000, thinking=True, image=True),
        _mi("claude-3-5-sonnet-latest", "Claude 3.5 Sonnet", 200000, thinking=True, image=True),
        _mi("claude-sonnet-4-20250514", "Claude Sonnet 4", 200000, thinking=True, image=True),
        _mi("claude-3-opus-20240229", "Claude 3 Opus", 200000, thinking=True, image=True),
        _mi("claude-3-haiku-20240307", "Claude 3 Haiku", 200000, image=True),
        _mi("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", 200000, thinking=True, image=True),
    ],
    "deepseek": [
        _mi("deepseek-r1", "DeepSeek R1", 128000, thinking=True),
        _mi("deepseek-reasoner", "DeepSeek Reasoner", 128000, thinking=True),
        _mi("deepseek-chat", "DeepSeek Chat", 128000),
        _mi("deepseek-v3", "DeepSeek V3", 128000),
    ],
    "google": [
        _mi("gemini-2.5-pro", "Gemini 2.5 Pro", 1048576, thinking=True, image=True),
        _mi("gemini-2.5-flash", "Gemini 2.5 Flash", 1048576, thinking=True, image=True),
        _mi("gemini-2.0-flash", "Gemini 2.0 Flash", 1048576, image=True),
        _mi("gemini-2.0-flash-lite", "Gemini 2.0 Flash Lite", 1048576, image=True),
        _mi("gemini-1.5-pro", "Gemini 1.5 Pro", 2097152, image=True),
        _mi("gemini-1.5-flash", "Gemini 1.5 Flash", 1048576, image=True),
    ],
    "qwen": [
        _mi("qwen-max", "Qwen Max", 32768, image=True),
        _mi("qwen-plus", "Qwen Plus", 131072, image=True),
        _mi("qwen-turbo", "Qwen Turbo", 131072, image=True),
        _mi("qwen-long", "Qwen Long", 10000000, image=True),
        _mi("qwen3-235b-a22b", "Qwen3 235B", 131072, thinking=True, image=True),
        _mi("qwen3-32b", "Qwen3 32B", 131072, thinking=True, image=True),
        _mi("qwq-32b", "QwQ 32B", 131072, thinking=True, image=True),
    ],
    "custom": [],
}

PLATFORMS: list[Platform] = [
    Platform(
        id="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        provider_type="openai_legacy",
    ),
    Platform(
        id="anthropic",
        name="Anthropic",
        base_url="https://api.anthropic.com/v1",
        provider_type="anthropic",
    ),
    Platform(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        provider_type="openai_legacy",
    ),
    Platform(
        id="google",
        name="Google",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        provider_type="google_genai",
    ),
    Platform(
        id="qwen",
        name="Qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        provider_type="openai_legacy",
    ),
    Platform(
        id="custom",
        name="Custom (OpenAI Compatible)",
        base_url="",  # setup 时再填写
        provider_type="openai_legacy",
    ),
]

_PLATFORM_BY_ID = {p.id: p for p in PLATFORMS}
_PLATFORM_BY_NAME = {p.name: p for p in PLATFORMS}


def get_platform_by_id(platform_id: str) -> Platform | None:
    return _PLATFORM_BY_ID.get(platform_id)


def get_platform_by_name(name: str) -> Platform | None:
    return _PLATFORM_BY_NAME.get(name)


def get_platform_name_for_provider(provider_type: str) -> str:
    """返回 provider 对应的可读平台名（OPEN-7，对齐 kimi）。

    对 `managed:<platform_id>` 格式先 unwrap 前缀再查平台，
    避免 /model 显示 `managed:openai` 而非可读名。
    """
    # 先尝试 unwrap managed: 前缀
    platform_id = parse_managed_provider_key(provider_type)
    if platform_id is not None:
        platform = get_platform_by_id(platform_id)
        return platform.name if platform else platform_id
    # 非 managed 格式：直接按 id 查
    platform = get_platform_by_id(provider_type)
    return platform.name if platform else provider_type


MANAGED_PROVIDER_PREFIX = "managed:"


def managed_provider_key(platform_id: str) -> str:
    return f"{MANAGED_PROVIDER_PREFIX}{platform_id}"


def managed_model_key(platform_id: str, model_name: str) -> str:
    return f"managed:{platform_id}:{model_name}"


def parse_managed_provider_key(key: str) -> str | None:
    """解析 `managed:<platform_id>` 格式的 key，返回 platform_id（OPEN-4，对齐 kimi）。

    旧实现返回 tuple[str, str]，与调用方期望的 str 不符，导致 /usage 等分支静默失效。
    """
    if not key.startswith(MANAGED_PROVIDER_PREFIX):
        return None
    return key.removeprefix(MANAGED_PROVIDER_PREFIX)


def is_managed_provider_key(key: str) -> bool:
    return key.startswith(MANAGED_PROVIDER_PREFIX)


def lookup_model_info(model_name: str) -> ModelInfo | None:
    """按模型名查找本地目录（大小写不敏感 / 前缀匹配）。"""
    name_lower = model_name.lower().strip()
    for models in _CATALOG.values():
        for model in models:
            if model.id.lower() == name_lower:
                return model
    for models in _CATALOG.values():
        for model in models:
            mid = model.id.lower()
            if name_lower.startswith(mid) or mid.startswith(name_lower):
                return model
    return None


def refresh_managed_models(*args: Any, **kwargs: Any) -> list[str]:
    """刷新 managed 模型 — stub（无 Moonshot 托管刷新）。"""
    return []


async def list_models(platform: Platform, api_key: str) -> list[ModelInfo]:
    """拉取平台模型列表；API 失败时回落到本地目录（对齐 setup 期望的 async 签名）。"""
    catalog = list(_CATALOG.get(platform.id, []))
    if not platform.base_url:
        if catalog:
            return catalog
        raise ValueError("Platform base_url is required (enter a custom OpenAI-compatible URL)")

    try:
        async with new_client_session() as session:
            models = await _list_models_from_api(
                session,
                base_url=platform.base_url,
                api_key=api_key,
            )
    except Exception as e:
        if catalog:
            logger.warning(
                "Failed to list models from {url}, using local catalog: {error}",
                url=platform.base_url,
                error=e,
            )
            return catalog
        raise

    if platform.allowed_prefixes is not None:
        prefixes = tuple(platform.allowed_prefixes)
        models = [m for m in models if m.id.startswith(prefixes)]

    # API 返回空时也回落目录，避免 setup 直接失败
    if not models and catalog:
        return catalog
    return models


async def _list_models_from_api(
    session: aiohttp.ClientSession,
    *,
    base_url: str,
    api_key: str,
) -> list[ModelInfo]:
    models_url = f"{base_url.rstrip('/')}/models"
    async with session.get(
        models_url,
        headers={"Authorization": f"Bearer {api_key}"},
        raise_for_status=True,
    ) as response:
        resp_json = await response.json()

    data = resp_json.get("data")
    if not isinstance(data, list):
        raise ValueError(f"Unexpected models response for {base_url}")

    result: list[ModelInfo] = []
    for item in cast(list[dict[str, Any]], data):
        model_id = item.get("id")
        if not model_id:
            continue
        raw_display_name = item.get("display_name") or item.get("name")
        display_name = str(raw_display_name) if raw_display_name else None
        result.append(
            ModelInfo(
                id=str(model_id),
                context_length=int(item.get("context_length") or item.get("max_model_len") or 0),
                supports_reasoning=bool(
                    item.get("supports_reasoning") or item.get("supports_thinking")
                ),
                supports_image_in=bool(
                    item.get("supports_image_in") or item.get("supports_image_input")
                ),
                supports_video_in=bool(item.get("supports_video_in")),
                display_name=display_name,
            )
        )
    return result
