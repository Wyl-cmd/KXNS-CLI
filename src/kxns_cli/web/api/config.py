"""Config API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from loguru import logger
from pydantic import BaseModel, Field

from kxns_cli.config import get_config_file, load_config, load_config_from_string
from kxns_cli.llm import ProviderType, derive_model_capabilities
from kxns_cli.auth.platforms import lookup_model_info

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigModel(BaseModel):
    """Model configuration for frontend."""

    name: str = Field(description="Model key in kxns-cli config")
    provider: str = Field(description="Provider name")
    provider_type: ProviderType = Field(description="Provider type")
    model: str = Field(description="Model identifier")
    max_context_size: int = Field(description="Maximum context size")
    capabilities: set[str] | None = Field(default=None, description="Model capabilities")
    base_url: str = Field(default="", description="API base URL")
    api_key: str = Field(default="", description="API key (masked)")
    reasoning_key: str = Field(default="", description="Reasoning key")


class GlobalConfig(BaseModel):
    """Global configuration snapshot for frontend."""

    default_model: str = Field(description="Current default model key")
    default_thinking: bool = Field(description="Current default thinking mode")
    models: list[ConfigModel] = Field(description="All configured models")


class ConfigToml(BaseModel):
    """Raw config.toml content."""

    content: str = Field(description="Raw TOML content")
    path: str = Field(description="Path to config file")


class UpdateConfigTomlRequest(BaseModel):
    """Request to update config.toml."""

    content: str = Field(description="New TOML content")


class UpdateConfigTomlResponse(BaseModel):
    """Response after updating config.toml."""

    success: bool = Field(description="Whether the update was successful")
    error: str | None = Field(default=None, description="Error message if failed")


class UpdateGlobalConfigRequest(BaseModel):
    """Request to update global config."""

    default_model: str | None = Field(default=None, description="New default model")
    default_thinking: bool | None = Field(default=None, description="New default thinking mode")
    restart_running_sessions: bool = Field(default=False, description="Whether to restart running sessions")
    force_restart_busy_sessions: bool = Field(default=False, description="Whether to force restart busy sessions")


class UpdateGlobalConfigResponse(BaseModel):
    """Response after updating global config."""

    config: GlobalConfig = Field(description="Updated global config")
    restarted_sessions: list[str] = Field(default_factory=list, description="IDs of restarted sessions")


class UpdateApiConfigRequest(BaseModel):
    """Request to update API configuration (provider + model)."""

    base_url: str | None = Field(default=None, description="API base URL")
    api_key: str | None = Field(default=None, description="API key")
    model: str | None = Field(default=None, description="Model name")
    max_context_size: int | None = Field(default=None, description="Max context size")
    image_input: bool | None = Field(default=None, description="Enable image input capability")
    thinking: bool | None = Field(default=None, description="Enable thinking capability")
    default_thinking: bool | None = Field(default=None, description="Enable default thinking mode")
    reasoning_key: str | None = Field(default=None, description="Key name for reasoning content in API response")
    restart_running_sessions: bool = Field(default=True, description="Whether to restart running sessions")


class UpdateApiConfigResponse(BaseModel):
    """Response after updating API configuration."""

    config: GlobalConfig = Field(description="Updated global config")
    restarted_sessions: list[str] = Field(default_factory=list, description="IDs of restarted sessions")


def _build_global_config() -> GlobalConfig:
    """Build GlobalConfig from kxns-cli config."""
    config = load_config()

    models: list[ConfigModel] = []
    for model_name, model in config.models.items():
        provider = config.providers.get(model.provider)
        if provider is None:
            continue

        derived_caps = derive_model_capabilities(model)
        capabilities = derived_caps or None

        models.append(
            ConfigModel(
                name=model_name,
                model=model.model,
                provider=model.provider,
                provider_type=provider.type,
                max_context_size=model.max_context_size,
                capabilities=capabilities,
                base_url=provider.base_url or "",
                api_key=provider.api_key.get_secret_value() if provider.api_key else "",
                reasoning_key=provider.reasoning_key or "",
            )
        )

    if config.default_model and config.default_model not in config.models:
        provider = config.providers.get("custom")
        models.append(
            ConfigModel(
                name=config.default_model,
                model=config.default_model,
                provider="custom",
                provider_type=provider.type if provider else "openai_legacy",
                max_context_size=128000,
                capabilities=None,
                base_url=provider.base_url or "" if provider else "",
                api_key=provider.api_key.get_secret_value() if provider and provider.api_key else "",
                reasoning_key=provider.reasoning_key or "" if provider else "",
            )
        )

    return GlobalConfig(
        default_model=config.default_model,
        default_thinking=config.default_thinking,
        models=models,
    )


@router.get("", summary="Get global config snapshot")
async def get_global_config() -> GlobalConfig:
    """Get global config snapshot."""
    return _build_global_config()


@router.get("/toml", summary="Get config.toml content")
async def get_config_toml() -> ConfigToml:
    """Get config.toml content."""
    config_file = get_config_file()
    if not config_file.exists():
        return ConfigToml(content="", path=str(config_file))
    return ConfigToml(content=config_file.read_text(encoding="utf-8"), path=str(config_file))


@router.put("/toml", summary="Update config.toml")
async def update_config_toml(request: UpdateConfigTomlRequest) -> UpdateConfigTomlResponse:
    """Update config.toml."""
    try:
        load_config_from_string(request.content)

        config_file = get_config_file()
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(request.content, encoding="utf-8")

        return UpdateConfigTomlResponse(success=True)
    except Exception as e:
        logger.warning(f"Failed to update config.toml: {e}")
        return UpdateConfigTomlResponse(success=False, error=str(e))


@router.patch("", summary="Update global config")
async def update_global_config(
    request: UpdateGlobalConfigRequest,
    http_request: Request,
) -> UpdateGlobalConfigResponse:
    """Update global config (default_model, default_thinking)."""
    import tomlkit

    config_file = get_config_file()
    if config_file.exists():
        content = config_file.read_text(encoding="utf-8")
        doc = tomlkit.parse(content)
    else:
        doc = tomlkit.document()

    if request.default_model is not None:
        doc["default_model"] = request.default_model

    if request.default_thinking is not None:
        doc["default_thinking"] = request.default_thinking

    content = tomlkit.dumps(doc)

    try:
        load_config_from_string(content)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to update global config: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    restarted_session_ids: list[str] = []

    if request.restart_running_sessions:
        from kxns_cli.web.runner.process import KxnsRunner

        runner: KxnsRunner | None = getattr(http_request.app.state, "runner", None)
        if runner is not None:
            result = await runner.restart_running_workers(
                reason="config_update",
                force=request.force_restart_busy_sessions,
            )
            restarted_session_ids = [str(sid) for sid in result.restarted_session_ids]

    return UpdateGlobalConfigResponse(
        config=_build_global_config(),
        restarted_sessions=restarted_session_ids,
    )


@router.patch("/api-settings", summary="Update API configuration")
async def update_api_config(
    request: UpdateApiConfigRequest,
    http_request: Request,
) -> UpdateApiConfigResponse:
    """Update API configuration (base_url, api_key, model) using tomlkit."""
    import tomlkit

    config_file = get_config_file()
    if config_file.exists():
        content = config_file.read_text(encoding="utf-8")
        doc = tomlkit.parse(content)
    else:
        doc = tomlkit.document()

    model_name = request.model or doc.get("default_model", "")
    if not model_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model name is required",
        )

    doc["default_model"] = model_name

    if request.default_thinking is not None:
        doc["default_thinking"] = request.default_thinking

    if "models" not in doc:
        doc["models"] = tomlkit.table()
    if model_name not in doc["models"]:
        doc["models"][model_name] = tomlkit.table()
    model_table = doc["models"][model_name]

    old_provider_name = model_table.get("provider")
    provider_name = model_name
    model_table["provider"] = provider_name
    model_table["model"] = model_name
    model_table["max_context_size"] = request.max_context_size or model_table.get("max_context_size", 128000)

    if old_provider_name and isinstance(old_provider_name, str) and old_provider_name != provider_name:
        if "providers" in doc and old_provider_name in doc["providers"]:
            old_provider = doc["providers"][old_provider_name]
            if provider_name not in doc["providers"]:
                doc["providers"][provider_name] = tomlkit.table()
            new_provider = doc["providers"][provider_name]
            for key in ("type", "base_url", "api_key", "reasoning_key"):
                if key in old_provider and key not in new_provider:
                    new_provider[key] = old_provider[key]
            other_models_using_old = any(
                k != model_name
                and isinstance(doc["models"].get(k), dict)
                and doc["models"][k].get("provider") == old_provider_name
                for k in doc["models"]
            )
            if not other_models_using_old:
                del doc["providers"][old_provider_name]

    if request.image_input is not None or request.thinking is not None:
        existing_caps = model_table.get("capabilities")
        if isinstance(existing_caps, list):
            caps = list(existing_caps)
        else:
            caps = []
        if request.image_input is not None:
            if request.image_input:
                if "image_in" not in caps:
                    caps.append("image_in")
            else:
                caps = [c for c in caps if c != "image_in"]
        if request.thinking is not None:
            if request.thinking:
                if "thinking" not in caps:
                    caps.append("thinking")
            else:
                caps = [c for c in caps if c not in ("thinking", "always_thinking")]
        if caps:
            model_table["capabilities"] = caps
        elif "capabilities" in model_table:
            del model_table["capabilities"]

    if "providers" not in doc:
        doc["providers"] = tomlkit.table()
    if provider_name not in doc["providers"]:
        doc["providers"][provider_name] = tomlkit.table()
    provider_table = doc["providers"][provider_name]
    if "type" not in provider_table:
        provider_table["type"] = "openai_legacy"
    if request.base_url is not None:
        provider_table["base_url"] = request.base_url
    if request.api_key is not None:
        provider_table["api_key"] = request.api_key
    if request.reasoning_key is not None:
        if request.reasoning_key:
            provider_table["reasoning_key"] = request.reasoning_key
        elif "reasoning_key" in provider_table:
            del provider_table["reasoning_key"]

    content = tomlkit.dumps(doc)

    try:
        load_config_from_string(content)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to update API config: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    restarted_session_ids: list[str] = []

    if request.restart_running_sessions:
        from kxns_cli.web.runner.process import KxnsRunner

        runner: KxnsRunner | None = getattr(http_request.app.state, "runner", None)
        if runner is not None:
            result = await runner.restart_running_workers(
                reason="api_config_update",
                force=True,
            )
            restarted_session_ids = [str(sid) for sid in result.restarted_session_ids]

    return UpdateApiConfigResponse(
        config=_build_global_config(),
        restarted_sessions=restarted_session_ids,
    )


class ModelInfoResponse(BaseModel):
    """Response for model info lookup."""

    found: bool = Field(description="Whether the model was found in the registry")
    name: str = Field(default="", description="Model identifier")
    display_name: str = Field(default="", description="Human-readable model name")
    max_context_size: int = Field(default=128000, description="Maximum context size in tokens")
    supports_thinking: bool = Field(default=False, description="Whether the model supports thinking/reasoning")
    supports_image_input: bool = Field(default=False, description="Whether the model supports image input")


@router.get("/model-info", summary="Look up model info from registry")
async def get_model_info(model_name: str = "") -> ModelInfoResponse:
    """Look up model information from the built-in model registry.

    Returns max_context_size, thinking support, and image input support
    for known models. Used by the frontend to auto-fill configuration.
    """
    if not model_name:
        return ModelInfoResponse(found=False)

    info = lookup_model_info(model_name)
    if info is None:
        return ModelInfoResponse(found=False)

    return ModelInfoResponse(
        found=True,
        name=info.name,
        display_name=info.display_name,
        max_context_size=info.max_context_size,
        supports_thinking=info.supports_thinking,
        supports_image_input=info.supports_image_input,
    )


class DeleteModelResponse(BaseModel):
    """Response after deleting a model."""

    config: GlobalConfig = Field(description="Updated global config")
    restarted_sessions: list[str] = Field(default_factory=list, description="IDs of restarted sessions")


@router.delete("/models/{model_name}", summary="Delete a model configuration")
async def delete_model(
    model_name: str,
    http_request: Request,
) -> DeleteModelResponse:
    """Delete a model and its provider (if no other models use it) from config."""
    import tomlkit

    config = load_config()

    if model_name not in config.models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' not found",
        )

    config_file = get_config_file()
    if not config_file.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Config file not found",
        )

    content = config_file.read_text(encoding="utf-8")
    doc = tomlkit.parse(content)

    model_cfg = config.models[model_name]
    provider_name = model_cfg.provider

    if "models" in doc and model_name in doc["models"]:
        del doc["models"][model_name]

    if config.default_model == model_name:
        remaining = [k for k in config.models if k != model_name]
        doc["default_model"] = remaining[0] if remaining else ""

    if provider_name:
        other_models_using_provider = any(
            m.provider == provider_name and k != model_name
            for k, m in config.models.items()
        )
        if not other_models_using_provider and "providers" in doc and provider_name in doc["providers"]:
            del doc["providers"][provider_name]

    content = tomlkit.dumps(doc)

    try:
        load_config_from_string(content)
        config_file.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to delete model: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    restarted_session_ids: list[str] = []
    from kxns_cli.web.runner.process import KxnsRunner

    runner: KxnsRunner | None = getattr(http_request.app.state, "runner", None)
    if runner is not None:
        result = await runner.restart_running_workers(
            reason="model_deleted",
            force=True,
        )
        restarted_session_ids = [str(sid) for sid in result.restarted_session_ids]

    return DeleteModelResponse(
        config=_build_global_config(),
        restarted_sessions=restarted_session_ids,
    )
