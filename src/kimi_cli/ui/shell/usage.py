"""This file is pure vibe-coded. If any bugs are found, let's just rewrite it..."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import aiohttp
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from kimi_cli.config import LLMModel
from kimi_cli.soul.kimisoul import KimiSoul
from kimi_cli.ui.shell.console import console
from kimi_cli.ui.shell.slash import registry
from kimi_cli.utils.aiohttp import new_client_session
from kimi_cli.utils.datetime import format_duration

if TYPE_CHECKING:
    from kimi_cli.ui.shell import Shell


@dataclass(slots=True, frozen=True)
class UsageRow:
    label: str
    used: int
    limit: int
    reset_hint: str | None = None


@registry.command
async def usage(app: Shell, args: str):
    """Display API usage and quota information"""
    assert isinstance(app.soul, KimiSoul)
    if app.soul.runtime.llm is None:
        console.print("[red]LLM not set. Please run 'kxns api add' first.[/red]")
        return

    provider = app.soul.runtime.llm.provider_config
    if provider is None:
        console.print("[red]LLM provider configuration not found.[/red]")
        return

    console.print("[yellow]API usage is only available for Kimi Code platform. Use 'kxns api add' to configure other providers.[/yellow]")
    return
