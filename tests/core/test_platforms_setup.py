"""platforms 须满足 /setup 的 async list_models 接口。"""

from __future__ import annotations

import inspect

import pytest

from kxns_cli.auth.platforms import (
    PLATFORMS,
    ModelInfo,
    get_platform_by_id,
    list_models,
    lookup_model_info,
)


def test_list_models_is_async_and_accepts_platform():
    sig = inspect.signature(list_models)
    params = list(sig.parameters)
    assert params[:2] == ["platform", "api_key"]
    assert inspect.iscoroutinefunction(list_models)


def test_platform_has_base_url_and_provider_type():
    openai = get_platform_by_id("openai")
    assert openai is not None
    assert openai.base_url.startswith("https://")
    assert openai.provider_type == "openai_legacy"
    custom = get_platform_by_id("custom")
    assert custom is not None
    assert custom.base_url == ""


@pytest.mark.asyncio
async def test_list_models_falls_back_to_catalog_without_network():
    platform = get_platform_by_id("openai")
    assert platform is not None
    # 故意用坏 key / 真实网络可能失败；有本地目录时应回落而不是炸
    models = await list_models(platform, "sk-invalid-for-test")
    assert models
    assert all(isinstance(m, ModelInfo) for m in models)
    assert models[0].id
    assert hasattr(models[0], "capabilities")
    assert models[0].context_length > 0


def test_lookup_model_info_compat_fields():
    info = lookup_model_info("gpt-4o")
    assert info is not None
    assert info.max_context_size == 128000
    assert info.supports_image_input is True
    assert info.name == "gpt-4o"


def test_all_platforms_have_required_fields():
    for p in PLATFORMS:
        assert p.id and p.name
        assert hasattr(p, "base_url")
        assert hasattr(p, "search_url")
        assert hasattr(p, "fetch_url")
