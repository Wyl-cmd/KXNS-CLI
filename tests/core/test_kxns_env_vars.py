"""回归：KXNS_* 环境变量须覆盖 provider/model。"""

from __future__ import annotations

from pydantic import SecretStr

from kxns_cli.config import LLMModel, LLMProvider
from kxns_cli.llm import augment_provider_with_env_vars


def test_kxns_env_overrides_openai_legacy(monkeypatch):
    provider = LLMProvider(
        type="openai_legacy",
        base_url="https://old.example/v1",
        api_key=SecretStr("old-key"),
    )
    model = LLMModel(provider="custom", model="old-model", max_context_size=1000)

    monkeypatch.setenv("KXNS_API_URL", "https://new.example/v1")
    monkeypatch.setenv("KXNS_API_KEY", "new-key")
    monkeypatch.setenv("KXNS_MODEL_NAME", "new-model")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    applied = augment_provider_with_env_vars(provider, model)

    assert provider.base_url == "https://new.example/v1"
    assert provider.api_key.get_secret_value() == "new-key"
    assert model.model == "new-model"
    assert applied.get("KXNS_API_URL") == "https://new.example/v1"
    assert applied.get("KXNS_API_KEY")
    assert applied.get("KXNS_MODEL_NAME") == "new-model"


def test_strict_default_model_must_exist_in_models():
    from kxns_cli.config import Config
    from kxns_cli.exception import ConfigError
    import pytest

    with pytest.raises((ConfigError, ValueError)):
        Config.model_validate(
            {
                "default_model": "missing-model",
                "models": {},
                "providers": {},
            }
        )
