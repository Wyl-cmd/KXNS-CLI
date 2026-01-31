from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import ValidationError

from kimi_cli.config import (
    Config,
    LLMModel,
    LLMProvider,
    load_config,
    save_config,
    get_config_file,
)
from kimi_cli.exception import ConfigError
from kimi_cli.llm import create_llm, ModelCapability
from kimi_cli.utils.logging import logger

cli = typer.Typer(help="Manage AI API providers and models.")


def _parse_key_value_pairs(
    items: list[str], option_name: str, *, separator: str = "=", strip_whitespace: bool = False
) -> dict[str, str]:
    """Parse key/value pairs from CLI options."""
    parsed: dict[str, str] = {}
    for item in items:
        if separator not in item:
            typer.echo(
                f"Invalid {option_name} format: {item} (expected KEY{separator}VALUE).",
                err=True,
            )
            raise typer.Exit(code=1)
        key, value = item.split(separator, 1)
        if strip_whitespace:
            key, value = key.strip(), value.strip()
        if not key:
            typer.echo(f"Invalid {option_name} format: {item} (empty key).", err=True)
            raise typer.Exit(code=1)
        parsed[key] = value
    return parsed


def _parse_capabilities(capabilities_str: str | None) -> set[str] | None:
    """Parse capabilities string into set of ModelCapability."""
    if not capabilities_str:
        return None
    
    valid_capabilities = {
        "thinking",
        "always_thinking",
        "image_in",
        "video_in",
    }
    
    capabilities: set[str] = set()
    for cap in capabilities_str.split(","):
        cap = cap.strip().lower()
        if cap in valid_capabilities:
            capabilities.add(cap)
        else:
            typer.echo(
                f"Invalid capability: {cap}. Valid options: thinking, always_thinking, image_in, video_in",
                err=True,
            )
            raise typer.Exit(code=1)
    
    return capabilities if capabilities else None


@cli.command("add")
def config_add(
    provider: Annotated[
        str,
        typer.Option(
            "--provider",
            "-p",
            help="Provider name (e.g., openai, anthropic, gemini).",
        ),
    ],
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model name.",
        ),
    ] = None,
    base_url: Annotated[
        str,
        typer.Option(
            "--base-url",
            "-u",
            help="API base URL.",
        ),
    ] = None,
    api_key: Annotated[
        str,
        typer.Option(
            "--api-key",
            "-k",
            help="API key.",
        ),
    ] = None,
    max_context: Annotated[
        int,
        typer.Option(
            "--max-context",
            "-C",
            help="Maximum context size (tokens).",
        ),
    ] = None,
    capabilities: Annotated[
        str,
        typer.Option(
            "--capabilities",
            "-c",
            help="Model capabilities (comma-separated: thinking, always_thinking, image_in, video_in).",
        ),
    ] = None,
    headers: Annotated[
        list[str],
        typer.Option(
            "--headers",
            "-H",
            help="Custom headers in KEY:VALUE format (can be specified multiple times).",
        ),
    ] = None,
    set_as_default: bool = typer.Option(
        False,
        "--default",
        "-d",
        help="Set as default model.",
    ),
):
    """Add an API configuration (provider + model)."""
    config = load_config()
    
    if not provider:
        typer.echo("--provider is required.", err=True)
        raise typer.Exit(code=1)
    
    if not model:
        typer.echo("--model is required.", err=True)
        raise typer.Exit(code=1)
    
    if not api_key:
        typer.echo("--api-key is required.", err=True)
        raise typer.Exit(code=1)
    
    parsed_capabilities = _parse_capabilities(capabilities)
    
    provider_config = config.providers.get(provider)
    if not provider_config:
        provider_config = LLMProvider(
            type="openai_legacy",
            base_url=base_url or "https://api.openai.com/v1",
            api_key=api_key,
            env=None,
            custom_headers=_parse_key_value_pairs(headers, "header") if headers else None,
            oauth=None,
        )
        config.providers[provider] = provider_config
    
    model_config = config.models.get(model)
    if not model_config:
        model_config = LLMModel(
            provider=provider,
            model=model,
            max_context_size=max_context or 128000,
            capabilities=parsed_capabilities,
        )
        config.models[model] = model_config
    
    if set_as_default:
        config.default_model = model
    
    save_config(config)
    
    typer.echo(f"Added API configuration: {provider}/{model}")
    if config.default_model == model:
        typer.echo(f"Set as default model.")


@cli.command("list")
def config_list():
    """List all API configurations."""
    config = load_config()
    
    typer.echo(f"Config file: {get_config_file()}")
    
    if not config.providers:
        typer.echo("No API providers configured.")
        return
    
    for provider_name, provider_config in config.providers.items():
        typer.echo(f"\n{provider_name}:")
        typer.echo(f"  Base URL: {provider_config.base_url}")
        typer.echo(f"  API Key: {'********' if provider_config.api_key else 'Not set'}")
        
        provider_models = {
            model_name: model_config
            for model_name, model_config in config.models.items()
            if model_config.provider == provider_name
        }
        
        if provider_models:
            for model_name, model_config in provider_models.items():
                is_default = " (default)" if config.default_model == model_name else ""
                capabilities_str = ""
                if model_config.capabilities:
                    capabilities_str = f" [{', '.join(model_config.capabilities)}]"
                typer.echo(f"    - {model_name}{is_default}{capabilities_str}")
        else:
            typer.echo(f"    (no models configured)")
    
    if config.default_model:
        typer.echo(f"\nDefault model: {config.default_model}")


@cli.command("remove")
def config_remove(
    provider: Annotated[
        str,
        typer.Option(
            "--provider",
            "-p",
            help="Provider name.",
        ),
    ] = None,
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model name.",
        ),
    ] = None,
    all_config: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Remove all configurations.",
    ),
):
    """Remove an API configuration."""
    config = load_config()
    
    if all_config:
        config.providers.clear()
        config.models.clear()
        config.default_model = ""
        save_config(config)
        typer.echo("Removed all API configurations.")
        return
    
    if not provider and not model:
        typer.echo("Either --provider or --model must be specified.", err=True)
        raise typer.Exit(code=1)
    
    if provider:
        if provider not in config.providers:
            typer.echo(f"Provider '{provider}' not found.", err=True)
            raise typer.Exit(code=1)
        
        if model:
            model_key = f"{provider}/{model}"
            if model_key not in config.models:
                typer.echo(f"Model '{model}' not found in provider '{provider}'.", err=True)
                raise typer.Exit(code=1)
            
            del config.models[model_key]
            
            if config.default_model == model_key:
                config.default_model = ""
        else:
            if provider not in config.providers:
                typer.echo(f"Provider '{provider}' not found.", err=True)
                raise typer.Exit(code=1)
            
            del config.providers[provider]
            
            if config.default_model == provider:
                config.default_model = ""
    
    save_config(config)
    
    if provider and model:
        typer.echo(f"Removed API configuration: {provider}/{model}")
    else:
        typer.echo(f"Removed provider: {provider}")


@cli.command("set-default")
def config_set_default(
    model: Annotated[
        str,
        typer.Argument(help="Model name to set as default."),
    ],
):
    """Set default model."""
    config = load_config()
    
    if not model:
        typer.echo("Model name is required.", err=True)
        raise typer.Exit(code=1)
    
    if model not in config.models:
        typer.echo(f"Model '{model}' not found.", err=True)
        raise typer.Exit(code=1)
    
    config.default_model = model
    save_config(config)
    
    typer.echo(f"Default model set to: {model}")


@cli.command("test")
def config_test(
    provider: Annotated[
        str,
        typer.Option(
            "--provider",
            "-p",
            help="Provider name (uses default if not specified).",
        ),
    ] = None,
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model name (uses default if not specified).",
        ),
    ] = None,
):
    """Test API connection."""
    config = load_config()
    
    if not provider:
        provider = config.default_model.split("/")[0] if config.default_model else None
        if not provider:
            typer.echo("No default model set. Use --provider to specify.", err=True)
            raise typer.Exit(code=1)
    
    if provider not in config.providers:
        typer.echo(f"Provider '{provider}' not found.", err=True)
        raise typer.Exit(code=1)
    
    provider_config = config.providers[provider]
    
    if model:
        model_key = f"{provider}/{model}"
        if model_key not in config.models:
            typer.echo(f"Model '{model}' not found in provider '{provider}'.", err=True)
            raise typer.Exit(code=1)
        model_config = config.models[model_key]
    else:
        provider_models = {
            model_name: model_config
            for model_name, model_config in config.models.items()
            if model_config.provider == provider
        }
        if provider_models:
            model_config = list(provider_models.values())[0]
        else:
            typer.echo(f"No models configured for provider '{provider}'.", err=True)
            raise typer.Exit(code=1)
    
    typer.echo(f"Testing API connection to: {provider}/{model_config.model if model else 'default'}")
    
    async def _test_connection():
        try:
            llm = create_llm(provider_config, model_config, config)
            typer.echo("  Testing API key...")
            
            test_messages = [{"role": "user", "content": "Hello"}]
            async for _ in llm.astream_messages(test_messages):
                if _:
                    typer.echo("  ✓ API key is valid")
                    typer.echo(f"  ✓ Model: {model_config.model}")
                    typer.echo(f"  ✓ Capabilities: {', '.join([c.value for c in model_config.capabilities]) if model_config.capabilities else 'none'}")
                    return
                await asyncio.sleep(0.1)
        except Exception as e:
            typer.echo(f"  ✗ Connection failed: {type(e).__name__}: {e}", err=True)
            raise typer.Exit(code=1)
    
    asyncio.run(_test_connection())
