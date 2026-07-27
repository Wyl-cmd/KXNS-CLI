"""create_llm 必须传入 default_headers（对齐 kimi）。"""

from __future__ import annotations

from pydantic import SecretStr

from kxns_cli.config import LLMModel, LLMProvider
from kxns_cli.llm import create_llm


def test_create_llm_passes_custom_headers():
    provider = LLMProvider(
        type="openai_legacy",
        base_url="https://example.com/v1",
        api_key=SecretStr("sk-test"),
        custom_headers={"X-Custom": "yes"},
    )
    model = LLMModel(provider="custom", model="gpt-test", max_context_size=8192)
    llm = create_llm(provider, model)
    assert llm is not None
    client_kwargs = getattr(llm.chat_provider, "_client_kwargs", {}) or {}
    headers = client_kwargs.get("default_headers") or {}
    assert headers.get("X-Custom") == "yes"
    assert "User-Agent" in headers


def test_create_llm_missing_base_url_returns_none():
    provider = LLMProvider(
        type="openai_legacy",
        base_url="",
        api_key=SecretStr("sk-test"),
    )
    model = LLMModel(provider="custom", model="gpt-test", max_context_size=8192)
    assert create_llm(provider, model) is None
