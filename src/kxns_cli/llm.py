from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast, get_args

from kosong.chat_provider import ChatProvider
from pydantic import SecretStr

from kxns_cli.constant import USER_AGENT

if TYPE_CHECKING:
    from kxns_cli.auth.oauth import OAuthManager
    from kxns_cli.config import LLMModel, LLMProvider

type ProviderType = Literal[
    "openai_legacy",
    "openai_responses",
    "anthropic",
    "google_genai",
    "gemini",
    "vertexai",
    "_echo",
    "_scripted_echo",
    "_chaos",
]

type ModelCapability = Literal["image_in", "video_in", "thinking", "always_thinking"]
ALL_MODEL_CAPABILITIES: set[ModelCapability] = set(get_args(ModelCapability.__value__))


@dataclass(slots=True)
class LLM:
    chat_provider: ChatProvider
    max_context_size: int
    capabilities: set[ModelCapability]
    model_config: LLMModel | None = None
    provider_config: LLMProvider | None = None

    @property
    def model_name(self) -> str:
        return self.chat_provider.model_name


def model_display_name(model_name: str | None) -> str:
    if not model_name:
        return ""
    return model_name


def augment_provider_with_env_vars(provider: LLMProvider, model: LLMModel) -> dict[str, str]:
    """Override provider/model settings from environment variables.

    Returns:
        Mapping of environment variables that were applied.
    """
    applied: dict[str, str] = {}

    match provider.type:
        case "openai_legacy" | "openai_responses":
            if base_url := os.getenv("OPENAI_BASE_URL"):
                provider.base_url = base_url
            if api_key := os.getenv("OPENAI_API_KEY"):
                provider.api_key = SecretStr(api_key)
        case _:
            pass

    if max_context_size := os.getenv("KXNS_MODEL_MAX_CONTEXT_SIZE"):
        model.max_context_size = int(max_context_size)
        applied["KXNS_MODEL_MAX_CONTEXT_SIZE"] = max_context_size
    if capabilities := os.getenv("KXNS_MODEL_CAPABILITIES"):
        caps_lower = (cap.strip().lower() for cap in capabilities.split(",") if cap.strip())
        model.capabilities = set(
            cast(ModelCapability, cap)
            for cap in caps_lower
            if cap in get_args(ModelCapability.__value__)
        )
        applied["KXNS_MODEL_CAPABILITIES"] = capabilities

    return applied


def _kxns_default_headers(provider: LLMProvider, oauth: OAuthManager | None) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    if oauth:
        headers.update(oauth.common_headers())
    if provider.custom_headers:
        headers.update(provider.custom_headers)
    return headers


def create_llm(
    provider: LLMProvider,
    model: LLMModel,
    *,
    thinking: bool | None = None,
    session_id: str | None = None,
    oauth: OAuthManager | None = None,
) -> LLM | None:
    if provider.type not in {"_echo", "_scripted_echo"} and (
        not provider.base_url or not model.model
    ):
        return None

    resolved_api_key = (
        oauth.resolve_api_key(provider.api_key, provider.oauth)
        if oauth and provider.oauth
        else provider.api_key.get_secret_value()
    )

    match provider.type:
        case "openai_legacy":
            from kosong.contrib.chat_provider.openai_legacy import OpenAILegacy

            reasoning_key = provider.reasoning_key
            if not reasoning_key:
                if "deepseek" in model.model.lower():
                    reasoning_key = "reasoning_content"
                elif model.capabilities and "thinking" in (model.capabilities or set()):
                    reasoning_key = "reasoning_content"

            chat_provider = OpenAILegacy(
                model=model.model,
                base_url=provider.base_url,
                api_key=resolved_api_key,
                reasoning_key=reasoning_key,
            )
        case "openai_responses":
            from kosong.contrib.chat_provider.openai_responses import OpenAIResponses

            chat_provider = OpenAIResponses(
                model=model.model,
                base_url=provider.base_url,
                api_key=resolved_api_key,
            )
        case "anthropic":
            from kosong.contrib.chat_provider.anthropic import Anthropic

            chat_provider = Anthropic(
                model=model.model,
                base_url=provider.base_url,
                api_key=resolved_api_key,
                default_max_tokens=50000,
                metadata={"user_id": session_id} if session_id else None,
            )
        case "google_genai" | "gemini":
            from kosong.contrib.chat_provider.google_genai import GoogleGenAI

            chat_provider = GoogleGenAI(
                model=model.model,
                base_url=provider.base_url,
                api_key=resolved_api_key,
            )
        case "vertexai":
            from kosong.contrib.chat_provider.google_genai import GoogleGenAI

            os.environ.update(provider.env or {})
            chat_provider = GoogleGenAI(
                model=model.model,
                base_url=provider.base_url,
                api_key=resolved_api_key,
                vertexai=True,
            )
        case "_echo":
            from kosong.chat_provider.echo import EchoChatProvider

            chat_provider = EchoChatProvider()
        case "_scripted_echo":
            from kosong.chat_provider.echo import ScriptedEchoChatProvider

            if provider.env:
                os.environ.update(provider.env)
            scripts = _load_scripted_echo_scripts()
            trace_value = os.getenv("KXNS_SCRIPTED_ECHO_TRACE", "")
            trace = trace_value.strip().lower() in {"1", "true", "yes", "on"}
            chat_provider = ScriptedEchoChatProvider(scripts, trace=trace)
        case "_chaos":
            from kosong.chat_provider.chaos import ChaosChatProvider, ChaosConfig
            from kosong.contrib.chat_provider.openai_legacy import OpenAILegacy

            chat_provider = ChaosChatProvider(
                provider=OpenAILegacy(
                    model=model.model,
                    base_url=provider.base_url,
                    api_key=resolved_api_key,
                ),
                chaos_config=ChaosConfig(
                    error_probability=0.8,
                    error_types=[429, 500, 503],
                ),
            )

    capabilities = derive_model_capabilities(model)

    # Apply thinking if specified or if model always requires thinking
    if thinking is False:
        chat_provider = chat_provider.with_thinking("off")
    elif "always_thinking" in capabilities or (thinking is True and "thinking" in capabilities):
        chat_provider = chat_provider.with_thinking("high")
    # If thinking is None and model doesn't always think, leave as-is (default behavior)

    return LLM(
        chat_provider=chat_provider,
        max_context_size=model.max_context_size,
        capabilities=capabilities,
        model_config=model,
        provider_config=provider,
    )


def derive_model_capabilities(model: LLMModel) -> set[ModelCapability]:
    capabilities = set(model.capabilities or ())
    if "thinking" in model.model.lower() or "reason" in model.model.lower():
        capabilities.add("thinking")
    return capabilities


def _load_scripted_echo_scripts() -> list[str]:
    script_path = os.getenv("KXNS_SCRIPTED_ECHO_SCRIPTS")
    if not script_path:
        raise ValueError("KXNS_SCRIPTED_ECHO_SCRIPTS is required for _scripted_echo.")
    path = Path(script_path).expanduser()
    if not path.exists():
        raise ValueError(f"Scripted echo file not found: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        data: object = json.loads(text)
    except json.JSONDecodeError:
        scripts = [chunk.strip() for chunk in text.split("\n---\n") if chunk.strip()]
        if scripts:
            return scripts
        raise ValueError(
            "Scripted echo file must be a JSON array of strings or a text file "
            "split by '\\n---\\n'."
        ) from None
    if isinstance(data, list):
        data_list = cast(list[object], data)
        if all(isinstance(item, str) for item in data_list):
            return cast(list[str], data_list)
    raise ValueError("Scripted echo JSON must be an array of strings.")
