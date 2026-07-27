from __future__ import annotations

import asyncio
import contextlib
import warnings
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import kaos
from kaos.path import KaosPath
from pydantic import SecretStr

from kxns_cli.agentspec import DEFAULT_AGENT_FILE
from kxns_cli.auth.oauth import OAuthManager
from kxns_cli.cli import InputFormat, OutputFormat
from kxns_cli.config import Config, LLMModel, LLMProvider, load_config
from kxns_cli.llm import augment_provider_with_env_vars, create_llm, model_display_name
from kxns_cli.session import Session
from kxns_cli.share import get_share_dir
from kxns_cli.soul import run_soul
from kxns_cli.soul.agent import Runtime, load_agent
from kxns_cli.soul.context import Context
from kxns_cli.soul.kxnssoul import KxnsSoul
from kxns_cli.utils.aioqueue import QueueShutDown
from kxns_cli.utils.logging import logger, redirect_stderr_to_logger
from kxns_cli.utils.path import shorten_home
from kxns_cli.wire import Wire, WireUISide
from kxns_cli.wire.types import ContentPart, WireMessage

if TYPE_CHECKING:
    from fastmcp.mcp_config import MCPConfig


def enable_logging(debug: bool = False, *, redirect_stderr: bool = True) -> None:
    logger.remove()
    logger.enable("kxns_cli")
    if debug:
        logger.enable("kosong")
    logger.add(
        get_share_dir() / "logs" / "kxns.log",
        level="TRACE" if debug else "INFO",
        rotation="00:00",
        retention="10 days",
    )
    if redirect_stderr:
        redirect_stderr_to_logger()


class KxnsCLI:
    @staticmethod
    async def create(
        session: Session,
        *,
        config: Config | Path | None = None,
        model_name: str | None = None,
        thinking: bool | None = None,
        yolo: bool | None = None,
        agent_file: Path | None = None,
        mcp_configs: list[MCPConfig] | list[dict[str, Any]] | None = None,
        skills_dir: KaosPath | None = None,
        max_steps_per_turn: int | None = None,
        max_retries_per_step: int | None = None,
        max_ralph_iterations: int | None = None,
        llm_request_timeout: float | None = None,
    ) -> KxnsCLI:
        config = config if isinstance(config, Config) else load_config(config)
        if max_steps_per_turn is not None:
            config.loop_control.max_steps_per_turn = max_steps_per_turn
        if max_retries_per_step is not None:
            config.loop_control.max_retries_per_step = max_retries_per_step
        if max_ralph_iterations is not None:
            config.loop_control.max_ralph_iterations = max_ralph_iterations
        logger.info("Loaded config: {config}", config=config)

        model: LLMModel | None = None
        provider: LLMProvider | None = None
        oauth = OAuthManager(config)

        if not model_name and config.default_model:
            # 严格校验保证 default_model ∈ models
            model = config.models[config.default_model]
            provider = config.providers[model.provider]
        if model_name and model_name in config.models:
            model = config.models[model_name]
            provider = config.providers[model.provider]
        elif model_name:
            # CLI --model 指定了配置中不存在的名字：仅作显式覆盖，不伪装已配置
            model = LLMModel(
                provider="custom" if "custom" in config.providers else "",
                model=model_name,
                max_context_size=128_000,
            )
            provider = config.providers.get("custom") or next(
                iter(config.providers.values()), None
            )

        if not model:
            model = LLMModel(provider="", model="", max_context_size=128_000)
            provider = LLMProvider(type="openai_legacy", base_url="", api_key=SecretStr(""))

        if provider is None:
            provider = LLMProvider(type="openai_legacy", base_url="", api_key=SecretStr(""))
            logger.warning("No provider found for model {model}, using empty provider", model=model)
        assert model is not None
        model = model.model_copy(deep=True)
        provider = provider.model_copy(deep=True)
        env_overrides = augment_provider_with_env_vars(provider, model)

        thinking = config.default_thinking if thinking is None else thinking
        yolo = config.default_yolo if yolo is None else yolo

        llm = create_llm(
            provider,
            model,
            thinking=thinking,
            session_id=session.id,
            oauth=oauth,
            request_timeout=(
                llm_request_timeout
                if llm_request_timeout is not None
                else float(config.llm_client.request_timeout_seconds)
            ),
        )
        if llm is not None:
            logger.info("Using LLM provider: {provider}", provider=provider)
            logger.info("Using LLM model: {model}", model=model)
            logger.info("Thinking mode: {thinking}", thinking=thinking)
        else:
            logger.warning(
                "Failed to create LLM: provider={provider}, model={model}. "
                "Check that base_url and model name are configured correctly.",
                provider=provider,
                model=model,
            )

        runtime = await Runtime.create(config, oauth, llm, session, yolo, skills_dir)
        if agent_file is None:
            agent_file = DEFAULT_AGENT_FILE
        agent = await load_agent(agent_file, runtime, mcp_configs=mcp_configs or [])
        context = Context(session.context_file)
        await context.restore()

        soul = KxnsSoul(agent, context=context)
        return KxnsCLI(soul, runtime, env_overrides)

    def __init__(
        self,
        _soul: KxnsSoul,
        _runtime: Runtime,
        _env_overrides: dict[str, str],
    ) -> None:
        self._soul = _soul
        self._runtime = _runtime
        self._env_overrides = _env_overrides

    @property
    def soul(self) -> KxnsSoul:
        return self._soul

    @property
    def session(self) -> Session:
        return self._runtime.session

    @contextlib.asynccontextmanager
    async def _env(self) -> AsyncGenerator[None]:
        original_cwd = KaosPath.cwd()
        await kaos.chdir(self._runtime.session.work_dir)
        try:
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            yield
        finally:
            await kaos.chdir(original_cwd)

    async def run(
        self,
        user_input: str | list[ContentPart],
        cancel_event: asyncio.Event,
        merge_wire_messages: bool = False,
    ) -> AsyncGenerator[WireMessage]:
        async with self._env():
            wire_future = asyncio.Future[WireUISide]()
            stop_ui_loop = asyncio.Event()

            async def _ui_loop_fn(wire: Wire) -> None:
                wire_future.set_result(wire.ui_side(merge=merge_wire_messages))
                await stop_ui_loop.wait()

            soul_task = asyncio.create_task(
                run_soul(self._soul, user_input, _ui_loop_fn, cancel_event)
            )
            try:
                wire_ui = await wire_future
                while True:
                    msg = await wire_ui.receive()
                    yield msg
            except QueueShutDown:
                pass
            finally:
                stop_ui_loop.set()
                await soul_task

    async def run_shell(self, command: str | None = None) -> bool:
        from kxns_cli.ui.shell import Shell, WelcomeInfoItem

        welcome_info = [
            WelcomeInfoItem(
                name="Directory", value=str(shorten_home(self._runtime.session.work_dir))
            ),
            WelcomeInfoItem(name="Session", value=self._runtime.session.id),
        ]

        if base_url := self._env_overrides.get("KXNS_API_URL"):
            welcome_info.append(
                WelcomeInfoItem(
                    name="API URL",
                    value=f"{base_url} (from KXNS_API_URL)",
                    level=WelcomeInfoItem.Level.WARN,
                )
            )

        if self._env_overrides.get("KXNS_API_KEY"):
            welcome_info.append(
                WelcomeInfoItem(
                    name="API Key",
                    value="****** (from KXNS_API_KEY)",
                    level=WelcomeInfoItem.Level.WARN,
                )
            )

        if not self._runtime.llm:
            welcome_info.append(
                WelcomeInfoItem(
                    name="Model",
                    value="not set, use --api-url, --api-key, and --api-model",
                    level=WelcomeInfoItem.Level.WARN,
                )
            )
        elif "KXNS_MODEL_NAME" in self._env_overrides:
            welcome_info.append(
                WelcomeInfoItem(
                    name="Model",
                    value=f"{self._soul.model_name} (from KXNS_MODEL_NAME)",
                    level=WelcomeInfoItem.Level.WARN,
                )
            )
        else:
            welcome_info.append(
                WelcomeInfoItem(
                    name="Model",
                    value=model_display_name(self._soul.model_name),
                    level=WelcomeInfoItem.Level.INFO,
                )
            )

        welcome_info.append(
            WelcomeInfoItem(
                name="\nTip",
                value=(
                    "Kxns Hunter CLI - A penetration testing focused AI agent.\n"
                    "Type /web for Web UI, /hunt <url> for auto vuln scan, or run `kxns web` / `kxns scan`."
                ),
                level=WelcomeInfoItem.Level.INFO,
            ),
        )

        async with self._env():
            shell = Shell(self._soul, welcome_info=welcome_info)
            return await shell.run(command)

    async def run_print(
        self,
        input_format: InputFormat,
        output_format: OutputFormat,
        command: str | None = None,
        *,
        final_only: bool = False,
    ) -> bool:
        from kxns_cli.ui.print import Print

        async with self._env():
            print_ = Print(
                self._soul,
                input_format,
                output_format,
                self._runtime.session.context_file,
                final_only=final_only,
            )
            return await print_.run(command)

    async def run_wire_stdio(self) -> None:
        from kxns_cli.wire.server import WireServer

        async with self._env():
            server = WireServer(self._soul)
            await server.serve()
