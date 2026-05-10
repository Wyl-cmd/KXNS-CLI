"""Platform stubs for kxns-cli (OAuth removed)."""

from typing import Any, NamedTuple


class ModelInfo(NamedTuple):
    """Model information."""
    name: str
    display_name: str
    max_context_size: int = 100000
    supports_thinking: bool = False
    supports_image_input: bool = False


class Platform(NamedTuple):
    """Platform information."""
    id: str
    name: str
    models: list[ModelInfo] = []


PLATFORMS: list[Platform] = [
    Platform(
        id="openai",
        name="OpenAI",
        models=[
            ModelInfo("gpt-4o", "GPT-4o", 128000, False, True),
            ModelInfo("gpt-4o-mini", "GPT-4o Mini", 128000, False, True),
            ModelInfo("gpt-4-turbo", "GPT-4 Turbo", 128000, False, True),
            ModelInfo("gpt-4", "GPT-4", 8192, False, False),
            ModelInfo("gpt-4-32k", "GPT-4 32K", 32768, False, False),
            ModelInfo("gpt-3.5-turbo", "GPT-3.5 Turbo", 16385, False, True),
            ModelInfo("o1", "O1", 200000, True, True),
            ModelInfo("o1-mini", "O1 Mini", 128000, True, True),
            ModelInfo("o1-pro", "O1 Pro", 200000, True, True),
            ModelInfo("o3-mini", "O3 Mini", 200000, True, True),
        ],
    ),
    Platform(
        id="anthropic",
        name="Anthropic",
        models=[
            ModelInfo("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", 200000, True, True),
            ModelInfo("claude-3-5-sonnet-latest", "Claude 3.5 Sonnet", 200000, True, True),
            ModelInfo("claude-sonnet-4-20250514", "Claude Sonnet 4", 200000, True, True),
            ModelInfo("claude-3-opus-20240229", "Claude 3 Opus", 200000, True, True),
            ModelInfo("claude-3-haiku-20240307", "Claude 3 Haiku", 200000, False, True),
            ModelInfo("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", 200000, True, True),
        ],
    ),
    Platform(
        id="deepseek",
        name="DeepSeek",
        models=[
            ModelInfo("deepseek-r1", "DeepSeek R1", 128000, True, False),
            ModelInfo("deepseek-reasoner", "DeepSeek Reasoner", 128000, True, False),
            ModelInfo("deepseek-chat", "DeepSeek Chat", 128000, False, False),
            ModelInfo("deepseek-v3", "DeepSeek V3", 128000, False, False),
        ],
    ),
    Platform(
        id="google",
        name="Google",
        models=[
            ModelInfo("gemini-2.5-pro", "Gemini 2.5 Pro", 1048576, True, True),
            ModelInfo("gemini-2.5-flash", "Gemini 2.5 Flash", 1048576, True, True),
            ModelInfo("gemini-2.0-flash", "Gemini 2.0 Flash", 1048576, False, True),
            ModelInfo("gemini-2.0-flash-lite", "Gemini 2.0 Flash Lite", 1048576, False, True),
            ModelInfo("gemini-1.5-pro", "Gemini 1.5 Pro", 2097152, False, True),
            ModelInfo("gemini-1.5-flash", "Gemini 1.5 Flash", 1048576, False, True),
        ],
    ),
    Platform(
        id="qwen",
        name="Qwen",
        models=[
            ModelInfo("qwen-max", "Qwen Max", 32768, False, True),
            ModelInfo("qwen-plus", "Qwen Plus", 131072, False, True),
            ModelInfo("qwen-turbo", "Qwen Turbo", 131072, False, True),
            ModelInfo("qwen-long", "Qwen Long", 10000000, False, True),
            ModelInfo("qwen3-235b-a22b", "Qwen3 235B", 131072, True, True),
            ModelInfo("qwen3-32b", "Qwen3 32B", 131072, True, True),
            ModelInfo("qwq-32b", "QwQ 32B", 131072, True, True),
        ],
    ),
    Platform(
        id="custom",
        name="Custom (OpenAI Compatible)",
        models=[],
    ),
]


def get_platform_by_id(platform_id: str) -> Platform | None:
    """Get platform by ID."""
    for platform in PLATFORMS:
        if platform.id == platform_id:
            return platform
    return None


def get_platform_by_name(name: str) -> Platform | None:
    """Get platform by name."""
    for platform in PLATFORMS:
        if platform.name == name:
            return platform
    return None


def get_platform_name_for_provider(provider_type: str) -> str:
    """Get platform name for provider type."""
    platform = get_platform_by_id(provider_type)
    return platform.name if platform else provider_type


def list_models(platform_id: str) -> list[ModelInfo]:
    """List models for a platform."""
    platform = get_platform_by_id(platform_id)
    return platform.models if platform else []


def managed_provider_key(platform_id: str) -> str:
    """Generate managed provider key."""
    return f"managed:{platform_id}"


def managed_model_key(platform_id: str, model_name: str) -> str:
    """Generate managed model key."""
    return f"managed:{platform_id}:{model_name}"


def parse_managed_provider_key(key: str) -> tuple[str, str] | None:
    """Parse managed provider key."""
    if key.startswith("managed:"):
        parts = key.split(":")
        if len(parts) >= 2:
            return (parts[1], parts[1])
    return None


def is_managed_provider_key(key: str) -> bool:
    """Check if key is a managed provider key."""
    return key.startswith("managed:")


def lookup_model_info(model_name: str) -> ModelInfo | None:
    """Look up model info by model name across all platforms.

    Performs case-insensitive matching and also supports partial matching
    (e.g., 'gpt-4o' matches 'gpt-4o-2024-05-13').
    """
    name_lower = model_name.lower().strip()

    for platform in PLATFORMS:
        for model in platform.models:
            if model.name.lower() == name_lower:
                return model

    for platform in PLATFORMS:
        for model in platform.models:
            if name_lower.startswith(model.name.lower()) or model.name.lower().startswith(name_lower):
                return model

    return None


def refresh_managed_models(*args, **kwargs) -> list[str]:
    """Refresh managed models - stub."""
    return []
