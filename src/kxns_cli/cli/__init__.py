from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated, Literal

import typer

from kxns_cli.constant import VERSION

from .doctor import doctor_cli
from .info import cli as info_cli
from .mcp import cli as mcp_cli
from .scan import scan_cli
from .web import cli as web_cli


class Reload(Exception):
    """Reload configuration."""

    def __init__(self, session_id: str | None = None):
        super().__init__("reload")
        self.session_id = session_id


class SwitchToWeb(Exception):
    """Switch to web interface."""

    def __init__(self, session_id: str | None = None):
        super().__init__("switch_to_web")
        self.session_id = session_id


cli = typer.Typer(
    epilog="""\b\
Documentation:        https://github.com/Wyl-cmd/kxns-cli\n
Issues:               https://github.com/Wyl-cmd/kxns-cli/issues""",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Kxns Hunter - A penetration testing focused AI agent CLI tool.",
)

UIMode = Literal["shell", "print", "wire"]
InputFormat = Literal["text", "stream-json"]
OutputFormat = Literal["text", "stream-json"]




def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kxns, version {VERSION}")
        raise typer.Exit()


def _save_api_config(
    url: str,
    api_key: str,
    model: str,
    max_context_size: int = 128000,
    capabilities: list[str] | None = None,
    thinking: bool = False,
) -> None:
    """Save API configuration to config file via tomlkit / save_config."""
    from pydantic import SecretStr

    from kxns_cli.config import (
        Config,
        LLMModel,
        LLMProvider,
        get_config_file,
        load_config,
        save_config,
    )
    from kxns_cli.llm import ModelCapability

    config_file = get_config_file()
    if config_file.exists():
        try:
            config = load_config(config_file)
        except Exception as e:
            # 配置损坏时禁止静默清空整份文件
            raise typer.BadParameter(
                f"Existing config is invalid, refuse to overwrite: {e}\n"
                f"Fix or remove {config_file} then retry."
            ) from e
    else:
        config = Config()

    caps: set[ModelCapability] | None = None
    if capabilities:
        caps = {c for c in capabilities if c in ("image_in", "thinking", "video_in", "always_thinking")}  # type: ignore[misc]

    config.default_model = model
    if thinking:
        config.default_thinking = True
    config.models[model] = LLMModel(
        provider="custom",
        model=model,
        max_context_size=max_context_size,
        capabilities=caps,
    )
    config.providers["custom"] = LLMProvider(
        type="openai_legacy",
        base_url=url,
        api_key=SecretStr(api_key),
    )
    save_config(config, config_file)

    typer.echo(f"API configuration saved to {config_file}")
    typer.echo(f"  URL: {url}")
    typer.echo(f"  Model: {model}")
    typer.echo(f"  Max Context Size: {max_context_size}")
    if capabilities:
        typer.echo(f"  Capabilities: {', '.join(capabilities)}")
    if thinking:
        typer.echo("  Thinking Mode: enabled")


@cli.callback(invoke_without_command=True)
def kxns(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            help="Print verbose information. Default: no.",
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Log debug information. Default: no.",
        ),
    ] = False,
    api_url: Annotated[
        str | None,
        typer.Option(
            "--api-url",
            help="LLM API base URL.",
        ),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option(
            "--api-key",
            help="LLM API key.",
        ),
    ] = None,
    api_model: Annotated[
        str | None,
        typer.Option(
            "--api-model",
            help="LLM model name.",
        ),
    ] = None,
    max_context_size: Annotated[
        int,
        typer.Option(
            "--max-context",
            "-x",
            help="Maximum context size in tokens. Default: 128000",
        ),
    ] = 128000,
    local_work_dir: Annotated[
        Path | None,
        typer.Option(
            "--work-dir",
            "-w",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            writable=True,
            help="Working directory for the agent. Default: current directory.",
        ),
    ] = None,
    local_add_dirs: Annotated[
        list[Path] | None,
        typer.Option(
            "--add-dir",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=(
                "Add an additional directory to the workspace scope. "
                "Can be specified multiple times."
            ),
        ),
    ] = None,
    session_id: Annotated[
        str | None,
        typer.Option(
            "--session",
            "-S",
            help="Session ID to resume for the working directory. Default: new session.",
        ),
    ] = None,
    continue_: Annotated[
        bool,
        typer.Option(
            "--continue",
            "-C",
            help="Continue the previous session for the working directory. Default: no.",
        ),
    ] = False,
    config_string: Annotated[
        str | None,
        typer.Option(
            "--config",
            help="Config TOML/JSON string to load. Default: none.",
        ),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config-file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Config TOML/JSON file to load. Default: ~/.kxns/config.toml.",
        ),
    ] = None,
    model_name: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="LLM model to use. Default: default model set in config file.",
        ),
    ] = None,
    thinking: Annotated[
        bool | None,
        typer.Option(
            "--thinking/--no-thinking",
            help="Enable thinking mode. Default: default thinking mode set in config file.",
        ),
    ] = None,
    yolo: Annotated[
        bool,
        typer.Option(
            "--yolo",
            "--yes",
            "-y",
            "--auto-approve",
            help="Automatically approve all actions. Default: no.",
        ),
    ] = False,
    prompt: Annotated[
        str | None,
        typer.Option(
            "--prompt",
            "-p",
            "--command",
            "-c",
            help="User prompt to the agent. Default: prompt interactively.",
        ),
    ] = None,
    print_mode: Annotated[
        bool,
        typer.Option(
            "--print",
            help=(
                "Run in print mode (non-interactive). Note: print mode implicitly adds `--yolo`."
            ),
        ),
    ] = False,
    wire_mode: Annotated[
        bool,
        typer.Option(
            "--wire",
            help="Run as Wire server (experimental).",
        ),
    ] = False,
    input_format: Annotated[
        InputFormat | None,
        typer.Option(
            "--input-format",
            help=(
                "Input format to use. Must be used with `--print` "
                "and the input must be piped in via stdin. "
                "Default: text."
            ),
        ),
    ] = None,
    output_format: Annotated[
        OutputFormat | None,
        typer.Option(
            "--output-format",
            help="Output format to use. Must be used with `--print`. Default: text.",
        ),
    ] = None,
    final_message_only: Annotated[
        bool,
        typer.Option(
            "--final-message-only",
            help="Only print the final assistant message (print UI).",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            help="Alias for `--print --output-format text --final-message-only`.",
        ),
    ] = False,
    agent: Annotated[
        Literal["default", "okabe"] | None,
        typer.Option(
            "--agent",
            help="Builtin agent specification to use. Default: builtin default agent.",
        ),
    ] = None,
    agent_file: Annotated[
        Path | None,
        typer.Option(
            "--agent-file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Custom agent specification file. Default: builtin default agent.",
        ),
    ] = None,
    mcp_config_file: Annotated[
        list[Path] | None,
        typer.Option(
            "--mcp-config-file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help=(
                "MCP config file to load. Add this option multiple times to specify multiple MCP "
                "configs. Default: none."
            ),
        ),
    ] = None,
    mcp_config: Annotated[
        list[str] | None,
        typer.Option(
            "--mcp-config",
            help=(
                "MCP config JSON to load. Add this option multiple times to specify multiple MCP "
                "configs. Default: none."
            ),
        ),
    ] = None,
    no_mcp: Annotated[
        bool,
        typer.Option(
            "--no-mcp",
            help="Do not load ~/.kxns/mcp.json (skip MCP tool loading at startup).",
        ),
    ] = False,
    local_skills_dir: Annotated[
        Path | None,
        typer.Option(
            "--skills-dir",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Path to the skills directory. Overrides discovery.",
        ),
    ] = None,
    max_steps_per_turn: Annotated[
        int | None,
        typer.Option(
            "--max-steps-per-turn",
            min=1,
            help="Maximum number of steps in one turn. Default: from config.",
        ),
    ] = None,
    max_retries_per_step: Annotated[
        int | None,
        typer.Option(
            "--max-retries-per-step",
            min=1,
            help="Maximum number of retries in one step. Default: from config.",
        ),
    ] = None,
    max_ralph_iterations: Annotated[
        int | None,
        typer.Option(
            "--max-ralph-iterations",
            min=-1,
            help=(
                "Extra iterations after the first turn in Ralph mode. Use -1 for unlimited. "
                "Default: from config."
            ),
        ),
    ] = None,
):
    """Kxns Hunter - A penetration testing focused AI agent CLI tool."""
    from kxns_cli.utils.proctitle import init_process_name

    init_process_name("Kxns Hunter")

    if ctx.invoked_subcommand is not None:
        return

    del version

    if api_url or api_key or api_model:
        if not api_url:
            raise typer.BadParameter("API URL is required. Use --api-url to specify.", param_hint="--api-url")
        if not api_key:
            raise typer.BadParameter("API key is required. Use --api-key to specify.", param_hint="--api-key")
        if not api_model:
            raise typer.BadParameter("Model name is required. Use --api-model to specify.", param_hint="--api-model")
        _save_api_config(api_url, api_key, api_model, max_context_size, None, False)
        raise typer.Exit()

    from kaos.path import KaosPath

    from kxns_cli.agentspec import DEFAULT_AGENT_FILE, OKABE_AGENT_FILE
    from kxns_cli.app import KxnsCLI, enable_logging
    from kxns_cli.config import Config, load_config_from_string
    from kxns_cli.exception import ConfigError
    from kxns_cli.metadata import load_metadata, save_metadata
    from kxns_cli.session import Session
    from kxns_cli.utils.logging import logger, open_original_stderr, redirect_stderr_to_logger

    from .mcp import get_global_mcp_config_file

    enable_logging(debug, redirect_stderr=False)

    def _emit_fatal_error(message: str) -> None:
        with open_original_stderr() as stream:
            if stream is not None:
                stream.write((message.rstrip() + "\n").encode("utf-8", errors="replace"))
                stream.flush()
                return
        typer.echo(message, err=True)

    if session_id is not None:
        session_id = session_id.strip()
        if not session_id:
            raise typer.BadParameter("Session ID cannot be empty", param_hint="--session")

    if quiet:
        if wire_mode:
            raise typer.BadParameter(
                "Quiet mode cannot be combined with Wire UI",
                param_hint="--quiet",
            )
        if output_format not in (None, "text"):
            raise typer.BadParameter(
                "Quiet mode implies `--output-format text`",
                param_hint="--quiet",
            )
        print_mode = True
        output_format = "text"
        final_message_only = True

    conflict_option_sets = [
        {
            "--print": print_mode,
            "--wire": wire_mode,
        },
        {
            "--agent": agent is not None,
            "--agent-file": agent_file is not None,
        },
        {
            "--continue": continue_,
            "--session": session_id is not None,
        },
        {
            "--config": config_string is not None,
            "--config-file": config_file is not None,
        },
    ]
    for option_set in conflict_option_sets:
        active_options = [flag for flag, active in option_set.items() if active]
        if len(active_options) > 1:
            raise typer.BadParameter(
                f"Cannot combine {', '.join(active_options)}.",
                param_hint=active_options[0],
            )

    if agent is not None:
        match agent:
            case "default":
                agent_file = DEFAULT_AGENT_FILE
            case "okabe":
                agent_file = OKABE_AGENT_FILE

    ui: UIMode = "shell"
    if print_mode:
        ui = "print"
    elif wire_mode:
        ui = "wire"

    if prompt is not None:
        prompt = prompt.strip()
        if not prompt:
            raise typer.BadParameter("Prompt cannot be empty", param_hint="--prompt")

    if input_format is not None and ui != "print":
        raise typer.BadParameter(
            "Input format is only supported for print UI",
            param_hint="--input-format",
        )
    if output_format is not None and ui != "print":
        raise typer.BadParameter(
            "Output format is only supported for print UI",
            param_hint="--output-format",
        )
    if final_message_only and ui != "print":
        raise typer.BadParameter(
            "Final-message-only output is only supported for print UI",
            param_hint="--final-message-only",
        )

    config: Config | Path | None = None
    if config_string is not None:
        config_string = config_string.strip()
        if not config_string:
            raise typer.BadParameter("Config cannot be empty", param_hint="--config")
        try:
            config = load_config_from_string(config_string)
        except ConfigError as e:
            raise typer.BadParameter(str(e), param_hint="--config") from e
    elif config_file is not None:
        config = config_file

    file_configs = list(mcp_config_file or [])
    raw_mcp_config = list(mcp_config or [])

    if not file_configs and not no_mcp:
        default_mcp_file = get_global_mcp_config_file()
        if default_mcp_file.exists():
            file_configs.append(default_mcp_file)

    try:
        mcp_configs = [json.loads(conf.read_text(encoding="utf-8")) for conf in file_configs]
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid JSON: {e}", param_hint="--mcp-config-file") from e

    try:
        mcp_configs += [json.loads(conf) for conf in raw_mcp_config]
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Invalid JSON: {e}", param_hint="--mcp-config") from e

    skills_dir: KaosPath | None = None
    if local_skills_dir is not None:
        skills_dir = KaosPath.unsafe_from_local_path(local_skills_dir)

    work_dir = KaosPath.unsafe_from_local_path(local_work_dir) if local_work_dir else KaosPath.cwd()

    async def _run(session_id: str | None) -> tuple[Session, bool]:
        if session_id is not None:
            session = await Session.find(work_dir, session_id)
            if session is None:
                logger.info(
                    "Session {session_id} not found, creating new session", session_id=session_id
                )
                session = await Session.create(work_dir, session_id)
            logger.info("Switching to session: {session_id}", session_id=session.id)
        elif continue_:
            session = await Session.continue_(work_dir)
            if session is None:
                raise typer.BadParameter(
                    "No previous session found for the working directory",
                    param_hint="--continue",
                )
            logger.info("Continuing previous session: {session_id}", session_id=session.id)
        else:
            session = await Session.create(work_dir)
            logger.info("Created new session: {session_id}", session_id=session.id)

        if local_add_dirs:
            from kxns_cli.utils.path import is_within_directory

            canonical_work_dir = work_dir.canonical()
            changed = False
            for d in local_add_dirs:
                dir_path = KaosPath.unsafe_from_local_path(d).canonical()
                dir_str = str(dir_path)
                if is_within_directory(dir_path, canonical_work_dir):
                    logger.info(
                        "Skipping --add-dir {dir}: already within working directory",
                        dir=dir_str,
                    )
                    continue
                if dir_str not in session.state.additional_dirs:
                    session.state.additional_dirs.append(dir_str)
                    changed = True
            if changed:
                session.save_state()

        instance = await KxnsCLI.create(
            session,
            config=config,
            model_name=model_name,
            thinking=thinking,
            yolo=yolo or (ui == "print"),
            agent_file=agent_file,
            mcp_configs=mcp_configs,
            skills_dir=skills_dir,
            max_steps_per_turn=max_steps_per_turn,
            max_retries_per_step=max_retries_per_step,
            max_ralph_iterations=max_ralph_iterations,
        )
        redirect_stderr_to_logger()
        try:
            match ui:
                case "shell":
                    succeeded = await instance.run_shell(prompt)
                case "print":
                    succeeded = await instance.run_print(
                        input_format or "text",
                        output_format or "text",
                        prompt,
                        final_only=final_message_only,
                    )
                case "wire":
                    if prompt is not None:
                        logger.warning("Wire server ignores prompt argument")
                    await instance.run_wire_stdio()
                    succeeded = True
        except Reload as e:
            if e.session_id is None:
                raise Reload(session_id=session.id) from e
            raise

        return session, succeeded

    async def _post_run(last_session: Session, succeeded: bool) -> None:
        if not succeeded:
            return

        metadata = load_metadata()

        work_dir_meta = metadata.get_work_dir_meta(last_session.work_dir)

        if work_dir_meta is None:
            logger.warning(
                "Work dir metadata missing when marking last session, recreating: {work_dir}",
                work_dir=last_session.work_dir,
            )
            work_dir_meta = metadata.new_work_dir_meta(last_session.work_dir)

        if last_session.is_empty():
            logger.info(
                "Session {session_id} has empty context, removing it",
                session_id=last_session.id,
            )
            await last_session.delete()
            if work_dir_meta.last_session_id == last_session.id:
                work_dir_meta.last_session_id = None
        else:
            work_dir_meta.last_session_id = last_session.id

        save_metadata(metadata)

    async def _reload_loop(session_id: str | None) -> bool:
        while True:
            try:
                last_session, succeeded = await _run(session_id)
                break
            except Reload as e:
                session_id = e.session_id
                continue
            except SwitchToWeb as e:
                if e.session_id is not None:
                    session = await Session.find(work_dir, e.session_id)
                    if session is not None:
                        await _post_run(session, True)
                return True
        await _post_run(last_session, succeeded)
        return False

    try:
        switch_to_web = asyncio.run(_reload_loop(session_id))
    except (typer.BadParameter, typer.Exit):
        raise
    except Exception as exc:
        import click

        if isinstance(exc, click.ClickException):
            raise
        logger.exception("Fatal error when running CLI")
        if debug:
            import traceback

            _emit_fatal_error(traceback.format_exc())
        else:
            from kxns_cli.share import get_share_dir

            log_path = get_share_dir() / "logs" / "kxns.log"
            _emit_fatal_error(f"{exc}\nSee logs: {log_path}")
        raise typer.Exit(code=1) from exc
    if switch_to_web:
        from kxns_cli.utils.logging import restore_stderr

        restore_stderr()

        import signal

        signal.signal(signal.SIGINT, signal.default_int_handler)

        from kxns_cli.utils.term import ensure_tty_sane

        ensure_tty_sane()

        from kxns_cli.web.app import run_web_server

        run_web_server(open_browser=True)


cli.add_typer(info_cli, name="info")


@cli.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def term(
    ctx: typer.Context,
) -> None:
    """Run Toad TUI backed by Kxns Hunter CLI Wire server."""
    from .toad import run_term

    run_term(ctx)


@cli.command(name="__web-worker", hidden=True)
def web_worker(session_id: str) -> None:
    """Run web worker subprocess (internal)."""
    from uuid import UUID

    from kxns_cli.utils.proctitle import set_process_title

    set_process_title("kxns-hunter-worker")

    from kxns_cli.app import enable_logging
    from kxns_cli.web.runner.worker import run_worker

    try:
        parsed_session_id = UUID(session_id)
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid session ID: {session_id}") from exc

    enable_logging(debug=False)
    asyncio.run(run_worker(parsed_session_id))


@cli.command()
def api(
    url: str = typer.Argument(..., help="LLM API base URL"),
    api_key: str = typer.Argument(..., help="LLM API key"),
    model: str = typer.Argument(..., help="LLM model name"),
    max_context_size: int = typer.Option(
        128000,
        "--max-context",
        "-x",
        help="Maximum context size in tokens. Default: 128000",
    ),
    image_input: bool = typer.Option(
        False,
        "--image-input",
        "-i",
        help="Enable image input capability",
    ),
    thinking: bool = typer.Option(
        False,
        "--thinking",
        "-t",
        help="Enable thinking mode capability",
    ),
) -> None:
    """Configure LLM API settings.

    Example: kxns api https://api.openai.com/v1 sk-xxx gpt-4
    Example: kxns api https://api.openai.com/v1 sk-xxx gpt-4 -x 200000
    Example: kxns api https://api.openai.com/v1 sk-xxx gpt-4-vision -i -t
    """
    capabilities = []
    if image_input:
        capabilities.append("image_in")
    if thinking:
        capabilities.append("thinking")

    _save_api_config(url, api_key, model, max_context_size, capabilities if capabilities else None, thinking)


cli.add_typer(mcp_cli, name="mcp")
cli.add_typer(web_cli, name="web")
cli.add_typer(scan_cli, name="scan")
cli.add_typer(doctor_cli, name="doctor")


if __name__ == "__main__":
    if "kxns_cli.cli" not in sys.modules:
        sys.modules["kxns_cli.cli"] = sys.modules[__name__]

    sys.exit(cli())
