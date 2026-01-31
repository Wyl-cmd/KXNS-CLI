from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, NamedTuple

from prompt_toolkit import PromptSession
from prompt_toolkit.shortcuts.choice_input import ChoiceInput
from pydantic import SecretStr

from kimi_cli.config import (
    LLMModel,
    LLMProvider,
    load_config,
    save_config,
)
from kimi_cli.ui.shell.console import console
from kimi_cli.ui.shell.slash import registry

if TYPE_CHECKING:
    from kimi_cli.ui.shell import Shell


class _Platform(NamedTuple):
    id: str
    name: str
    base_url: str


_PLATFORMS: list[_Platform] = [
    _Platform(
        id="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
    ),
    _Platform(
        id="anthropic",
        name="Anthropic",
        base_url="https://api.anthropic.com",
    ),
    _Platform(
        id="google_genai",
        name="Google GenAI",
        base_url="https://generativelanguage.googleapis.com/v1beta",
    ),
]


@registry.command
async def setup(app: Shell, args: str):
    """Setup KXNS CLI with API key"""
    result = await _setup()
    if not result:
        # error message already printed
        return

    config = load_config()
    provider_key = result.platform.id
    model_key = f"{provider_key}/{result.model}"
    config.providers[provider_key] = LLMProvider(
        type="openai_legacy",
        base_url=result.platform.base_url,
        api_key=result.api_key,
    )
    config.models[model_key] = LLMModel(
        provider=provider_key,
        model=result.model,
        max_context_size=128000,
    )
    config.default_model = model_key

    save_config(config)
    console.print("[green]✓[/green] KXNS CLI has been setup! Reloading...")
    await asyncio.sleep(1)
    console.clear()

    from kimi_cli.cli import Reload

    raise Reload


class _SetupResult(NamedTuple):
    platform: _Platform
    api_key: SecretStr
    model: str


async def _setup() -> _SetupResult | None:
    # select the API platform
    platform_name = await _prompt_choice(
        header="Select a platform (↑↓ navigate, Enter select, Ctrl+C cancel):",
        choices=[platform.name for platform in _PLATFORMS],
    )
    if not platform_name:
        console.print("[red]No platform selected[/red]")
        return None

    platform = next((p for p in _PLATFORMS if p.name == platform_name), None)
    if platform is None:
        console.print("[red]Unknown platform[/red]")
        return None

    # enter the API key
    api_key = await _prompt_text("Enter your API key", is_password=True)
    if not api_key:
        return None

    # enter model name
    model = await _prompt_text("Enter model name (e.g., gpt-4, claude-3-5-sonnet-20241022)")
    if not model:
        return None

    return _SetupResult(
        platform=platform,
        api_key=SecretStr(api_key),
        model=model,
    )


async def _prompt_choice(*, header: str, choices: list[str]) -> str | None:
    if not choices:
        return None

    try:
        return await ChoiceInput(
            message=header,
            options=[(choice, choice) for choice in choices],
            default=choices[0],
        ).prompt_async()
    except (EOFError, KeyboardInterrupt):
        return None


async def _prompt_text(prompt: str, *, is_password: bool = False) -> str | None:
    session = PromptSession[str]()
    try:
        return str(
            await session.prompt_async(
                f" {prompt}: ",
                is_password=is_password,
            )
        ).strip()
    except (EOFError, KeyboardInterrupt):
        return None


@registry.command
def reload(app: Shell, args: str):
    """Reload configuration"""
    from kimi_cli.cli import Reload

    raise Reload
