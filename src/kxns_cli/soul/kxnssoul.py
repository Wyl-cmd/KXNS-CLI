from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, Literal

import kosong
import tenacity
from kosong import StepResult
from kosong.chat_provider import (
    APIConnectionError,
    APIEmptyResponseError,
    APIStatusError,
    APITimeoutError,
    RetryableChatProvider,
)
from kosong.message import Message, TextPart, ToolCall
from tenacity import RetryCallState, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from kxns_cli.llm import ModelCapability
from kxns_cli.skill import Skill, read_skill_text
from kxns_cli.skill.flow import Flow, FlowEdge, FlowNode, parse_choice
from kxns_cli.soul import (
    LLMNotSet,
    LLMNotSupported,
    MaxStepsReached,
    Soul,
    StatusSnapshot,
    wire_send,
)
from kxns_cli.soul.agent import Agent, Runtime
from kxns_cli.soul.compaction import CompactionResult, SimpleCompaction, should_auto_compact
from kxns_cli.soul.context import Context
from kxns_cli.soul.message import check_message, system, tool_result_to_message
from kxns_cli.soul.slash import registry as soul_slash_registry
from kxns_cli.soul.toolset import KxnsToolset
from kxns_cli.tools.dmail import NAME as SendDMail_NAME
from kxns_cli.tools.utils import ToolRejectedError
from kxns_cli.utils.logging import logger
from kxns_cli.utils.slashcmd import SlashCommand, parse_slash_command_call
from kxns_cli.wire.file import WireFile
from kxns_cli.wire.types import (
    ApprovalRequest,
    ApprovalResponse,
    CompactionBegin,
    CompactionEnd,
    ContentPart,
    MCPLoadingBegin,
    MCPLoadingEnd,
    StatusUpdate,
    StepBegin,
    StepInterrupted,
    TextPart,
    ToolResult,
    TurnBegin,
    TurnEnd,
)

if TYPE_CHECKING:

    def type_check(soul: KxnsSoul):
        _: Soul = soul


SKILL_COMMAND_PREFIX = "skill:"
FLOW_COMMAND_PREFIX = "flow:"
DEFAULT_MAX_FLOW_MOVES = 1000


type StepStopReason = Literal["no_tool_calls", "tool_rejected"]


@dataclass(frozen=True, slots=True)
class StepOutcome:
    stop_reason: StepStopReason
    assistant_message: Message


type TurnStopReason = StepStopReason


@dataclass(frozen=True, slots=True)
class TurnOutcome:
    stop_reason: TurnStopReason
    final_message: Message | None
    step_count: int


class KxnsSoul:
    """The soul of KXNS Hunter CLI."""

    def __init__(
        self,
        agent: Agent,
        *,
        context: Context,
    ):
        """
        Initialize the soul.

        Args:
            agent (Agent): The agent to run.
            context (Context): The context of the agent.
        """
        self._agent = agent
        self._runtime = agent.runtime
        self._denwa_renji = agent.runtime.denwa_renji
        self._approval = agent.runtime.approval
        self._context = context
        self._loop_control = agent.runtime.config.loop_control
        self._compaction = SimpleCompaction()  # TODO: maybe configurable and composable

        for tool in agent.toolset.tools:
            if tool.name == SendDMail_NAME:
                self._checkpoint_with_user_message = True
                break
        else:
            self._checkpoint_with_user_message = False

        self._steer_queue: asyncio.Queue[str | list[ContentPart]] = asyncio.Queue()
        self._plan_mode: bool = self._runtime.session.state.plan_mode
        self._plan_mode_steps_since_injection: int = 0
        self._plan_mode_just_activated: bool = False

        self._bind_plan_mode_tools()

        self._slash_commands = self._build_slash_commands()
        self._slash_command_map = self._index_slash_commands(self._slash_commands)

    @property
    def name(self) -> str:
        return self._agent.name

    @property
    def model_name(self) -> str:
        return self._runtime.llm.chat_provider.model_name if self._runtime.llm else ""

    @property
    def model_capabilities(self) -> set[ModelCapability] | None:
        if self._runtime.llm is None:
            return None
        return self._runtime.llm.capabilities

    @property
    def thinking(self) -> bool | None:
        """Whether thinking mode is enabled."""
        if self._runtime.llm is None:
            return None
        thinking_effort = self._runtime.llm.chat_provider.thinking_effort
        if thinking_effort is None:
            return False
        return thinking_effort != "off"

    @property
    def plan_mode(self) -> bool:
        return self._plan_mode

    @plan_mode.setter
    def plan_mode(self, value: bool) -> None:
        self._plan_mode = value
        self._runtime.session.state.plan_mode = value
        self._runtime.session.save_state()

    async def set_plan_mode_from_manual(self, enabled: bool) -> bool:
        self._plan_mode = enabled
        self._runtime.session.state.plan_mode = enabled
        self._runtime.session.save_state()
        if enabled:
            self._plan_mode_just_activated = True
            self._plan_mode_steps_since_injection = 0
        return self._plan_mode

    async def toggle_plan_mode(self) -> bool:
        self._plan_mode = not self._plan_mode
        self._runtime.session.state.plan_mode = self._plan_mode
        self._runtime.session.save_state()
        if self._plan_mode:
            self._plan_mode_just_activated = True
            self._plan_mode_steps_since_injection = 0
        return self._plan_mode

    async def toggle_plan_mode_from_manual(self) -> bool:
        self._plan_mode = not self._plan_mode
        self._runtime.session.state.plan_mode = self._plan_mode
        self._runtime.session.save_state()
        if self._plan_mode:
            self._plan_mode_just_activated = True
            self._plan_mode_steps_since_injection = 0
        return self._plan_mode

    def get_plan_file_path(self) -> Path | None:
        from pathlib import Path
        plans_dir = Path.home() / ".kxns" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        return plans_dir / f"{self._runtime.session.id}.md"

    def read_current_plan(self) -> str | None:
        path = self.get_plan_file_path()
        if path is None or not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return None

    def clear_current_plan(self) -> None:
        path = self.get_plan_file_path()
        if path and path.exists():
            path.unlink()

    def _bind_plan_mode_tools(self) -> None:
        if not isinstance(self._agent.toolset, KxnsToolset):
            return

        def checker() -> bool:
            return self._plan_mode

        def path_getter() -> Path | None:
            return self.get_plan_file_path()

        def yolo_checker() -> bool:
            return self._approval.is_yolo()

        from kxns_cli.tools.plan import ExitPlanMode
        exit_tool = self._agent.toolset.find(ExitPlanMode)
        if isinstance(exit_tool, ExitPlanMode):
            exit_tool.bind(self.toggle_plan_mode, path_getter, checker)

        from kxns_cli.tools.plan.enter import EnterPlanMode
        enter_tool = self._agent.toolset.find(EnterPlanMode)
        if isinstance(enter_tool, EnterPlanMode):
            enter_tool.bind(self.toggle_plan_mode, path_getter, checker, yolo_checker)

        from kxns_cli.tools.file.write import WriteFile
        write_tool = self._agent.toolset.find(WriteFile)
        if isinstance(write_tool, WriteFile):
            write_tool.bind_plan_mode(checker, path_getter)

        from kxns_cli.tools.ask_user import AskUserQuestion
        ask_tool = self._agent.toolset.find(AskUserQuestion)
        if isinstance(ask_tool, AskUserQuestion):
            ask_tool.bind_plan_mode(checker)

    @property
    def status(self) -> StatusSnapshot:
        token_count = self._context.token_count
        max_size = self._runtime.llm.max_context_size if self._runtime.llm is not None else 0
        return StatusSnapshot(
            context_usage=self._context_usage,
            yolo_enabled=self._approval.is_yolo(),
            context_tokens=token_count,
            max_context_tokens=max_size,
        )

    @property
    def agent(self) -> Agent:
        return self._agent

    @property
    def runtime(self) -> Runtime:
        return self._runtime

    @property
    def context(self) -> Context:
        return self._context

    @property
    def _context_usage(self) -> float:
        if self._runtime.llm is not None:
            return self._context.token_count / self._runtime.llm.max_context_size
        return 0.0

    @property
    def wire_file(self) -> WireFile:
        return self._runtime.session.wire_file

    async def _checkpoint(self):
        await self._context.checkpoint(self._checkpoint_with_user_message)

    def steer(self, content: str | list[ContentPart]) -> None:
        """Queue a steer message for injection into the current turn."""
        self._steer_queue.put_nowait(content)

    async def _consume_pending_steers(self) -> bool:
        """Drain the steer queue and inject as synthetic tool results.

        Returns True if any steers were consumed.
        """
        consumed = False
        while not self._steer_queue.empty():
            content = self._steer_queue.get_nowait()
            await self._inject_steer(content)
            consumed = True
        return consumed

    async def _inject_steer(self, content: str | list[ContentPart]) -> None:
        """Inject a single steer as a synthetic ``_steer`` tool_call + tool result pair."""
        from uuid import uuid4

        steer_id = f"steer_{uuid4().hex[:8]}"
        text = (
            content
            if isinstance(content, str)
            else Message(role="user", content=content).extract_text(" ")
        )
        await self._context.append_message(
            [
                Message(
                    role="assistant",
                    content=[],
                    tool_calls=[
                        ToolCall(
                            id=steer_id,
                            function=ToolCall.FunctionBody(name="_steer", arguments=None),
                        )
                    ],
                ),
                Message(
                    role="tool",
                    content=[system(f"The user has sent a real-time instruction:\n\n{text}")],
                    tool_call_id=steer_id,
                ),
            ]
        )

    @property
    def available_slash_commands(self) -> list[SlashCommand[Any]]:
        return self._slash_commands

    async def run(self, user_input: str | list[ContentPart]):
        wire_send(TurnBegin(user_input=user_input))
        try:
            user_message = Message(role="user", content=user_input)
            text_input = user_message.extract_text(" ").strip()

            if command_call := parse_slash_command_call(text_input):
                command = self._find_slash_command(command_call.name)
                if command is None:
                    wire_send(TextPart(text=f'Unknown slash command "/{command_call.name}".'))
                else:
                    ret = command.func(self, command_call.args)
                    if isinstance(ret, Awaitable):
                        await ret
            elif self._loop_control.max_ralph_iterations != 0:
                runner = FlowRunner.ralph_loop(
                    user_message,
                    self._loop_control.max_ralph_iterations,
                )
                await runner.run(self, "")
            else:
                await self._turn(user_message)
        finally:
            wire_send(TurnEnd())

    async def _turn(self, user_message: Message) -> TurnOutcome:
        if self._runtime.llm is None:
            raise LLMNotSet()

        if missing_caps := check_message(user_message, self._runtime.llm.capabilities):
            raise LLMNotSupported(self._runtime.llm, list(missing_caps))

        await self._checkpoint()  # this creates the checkpoint 0 on first run
        await self._context.append_message(user_message)
        logger.debug("Appended user message to context")
        return await self._agent_loop()

    def _build_slash_commands(self) -> list[SlashCommand[Any]]:
        commands: list[SlashCommand[Any]] = list(soul_slash_registry.list_commands())
        seen_names = {cmd.name for cmd in commands}

        for skill in self._runtime.skills.values():
            if skill.type not in ("standard", "flow"):
                continue
            name = f"{SKILL_COMMAND_PREFIX}{skill.name}"
            if name in seen_names:
                logger.warning(
                    "Skipping skill slash command /{name}: name already registered",
                    name=name,
                )
                continue
            commands.append(
                SlashCommand(
                    name=name,
                    func=self._make_skill_runner(skill),
                    description=skill.description or "",
                    aliases=[],
                )
            )
            seen_names.add(name)

        for skill in self._runtime.skills.values():
            if skill.type != "flow":
                continue
            if skill.flow is None:
                logger.warning("Flow skill {name} has no flow; skipping", name=skill.name)
                continue
            command_name = f"{FLOW_COMMAND_PREFIX}{skill.name}"
            if command_name in seen_names:
                logger.warning(
                    "Skipping prompt flow slash command /{name}: name already registered",
                    name=command_name,
                )
                continue
            runner = FlowRunner(skill.flow, name=skill.name)
            commands.append(
                SlashCommand(
                    name=command_name,
                    func=runner.run,
                    description=skill.description or "",
                    aliases=[],
                )
            )
            seen_names.add(command_name)

        return commands

    @staticmethod
    def _index_slash_commands(
        commands: list[SlashCommand[Any]],
    ) -> dict[str, SlashCommand[Any]]:
        indexed: dict[str, SlashCommand[Any]] = {}
        for command in commands:
            indexed[command.name] = command
            for alias in command.aliases:
                indexed[alias] = command
        return indexed

    def _find_slash_command(self, name: str) -> SlashCommand[Any] | None:
        return self._slash_command_map.get(name)

    def _make_skill_runner(self, skill: Skill) -> Callable[[KxnsSoul, str], None | Awaitable[None]]:
        async def _run_skill(soul: KxnsSoul, args: str, *, _skill: Skill = skill) -> None:
            skill_text = await read_skill_text(_skill)
            if skill_text is None:
                wire_send(
                    TextPart(text=f'Failed to load skill "/{SKILL_COMMAND_PREFIX}{_skill.name}".')
                )
                return
            extra = args.strip()
            if extra:
                skill_text = f"{skill_text}\n\nUser request:\n{extra}"
            await soul._turn(Message(role="user", content=skill_text))

        _run_skill.__doc__ = skill.description
        return _run_skill

    async def _agent_loop(self) -> TurnOutcome:
        """The main agent loop for one run."""
        assert self._runtime.llm is not None

        # Discard any stale steers from a previous turn.
        while not self._steer_queue.empty():
            self._steer_queue.get_nowait()

        if isinstance(self._agent.toolset, KxnsToolset):
            loading = self._agent.toolset.has_pending_mcp_tools()
            if loading:
                wire_send(MCPLoadingBegin())
            try:
                await self._agent.toolset.wait_for_mcp_tools()
            finally:
                if loading:
                    wire_send(MCPLoadingEnd())

        async def _pipe_approval_to_wire():
            while True:
                request = await self._approval.fetch_request()
                # Here we decouple the wire approval request and the soul approval request.
                wire_request = ApprovalRequest(
                    id=request.id,
                    action=request.action,
                    description=request.description,
                    sender=request.sender,
                    tool_call_id=request.tool_call_id,
                    display=request.display,
                )
                wire_send(wire_request)
                # We wait for the request to be resolved over the wire, which means that,
                # for each soul, we will have only one approval request waiting on the wire
                # at a time. However, be aware that subagents (which have their own souls) may
                # also send approval requests to the root wire.
                resp = await wire_request.wait()
                self._approval.resolve_request(request.id, resp)
                wire_send(ApprovalResponse(request_id=request.id, response=resp))

        step_no = 0
        while True:
            step_no += 1
            if step_no > self._loop_control.max_steps_per_turn:
                raise MaxStepsReached(self._loop_control.max_steps_per_turn)

            wire_send(StepBegin(n=step_no))
            approval_task = asyncio.create_task(_pipe_approval_to_wire())
            back_to_the_future: BackToTheFuture | None = None
            step_outcome: StepOutcome | None = None
            try:
                # compact the context if needed
                if should_auto_compact(
                    self._context.token_count,
                    self._runtime.llm.max_context_size,
                    trigger_ratio=self._loop_control.compaction_trigger_ratio,
                    reserved_context_size=self._loop_control.reserved_context_size,
                ):
                    logger.info("Context too long, compacting...")
                    await self.compact_context()

                logger.debug("Beginning step {step_no}", step_no=step_no)
                await self._checkpoint()
                self._denwa_renji.set_n_checkpoints(self._context.n_checkpoints)
                step_outcome = await self._step()
            except BackToTheFuture as e:
                back_to_the_future = e
            except Exception:
                # any other exception should interrupt the step
                wire_send(StepInterrupted())
                # break the agent loop
                raise
            finally:
                approval_task.cancel()  # stop piping approval requests to the wire
                with suppress(asyncio.CancelledError):
                    try:
                        await approval_task
                    except Exception:
                        logger.exception("Approval piping task failed")

            if step_outcome is not None:
                has_steers = await self._consume_pending_steers()
                if step_outcome.stop_reason == "no_tool_calls" and has_steers:
                    continue  # steers injected, force another LLM step
                final_message = (
                    step_outcome.assistant_message
                    if step_outcome.stop_reason == "no_tool_calls"
                    else None
                )
                return TurnOutcome(
                    stop_reason=step_outcome.stop_reason,
                    final_message=final_message,
                    step_count=step_no,
                )

            if back_to_the_future is not None:
                await self._context.revert_to(back_to_the_future.checkpoint_id)
                await self._checkpoint()
                await self._context.append_message(back_to_the_future.messages)

            # Consume any pending steers between steps
            await self._consume_pending_steers()

    async def _step(self) -> StepOutcome | None:
        """Run a single step and return a stop outcome, or None to continue."""
        # already checked in `run`
        assert self._runtime.llm is not None
        chat_provider = self._runtime.llm.chat_provider

        if self._plan_mode:
            should_inject = False
            is_reentry = False
            if self._plan_mode_just_activated:
                should_inject = True
                self._plan_mode_just_activated = False
                plan_path = self.get_plan_file_path()
                is_reentry = plan_path is not None and plan_path.exists()
            else:
                self._plan_mode_steps_since_injection += 1
                if self._plan_mode_steps_since_injection >= 5:
                    should_inject = True
                    self._plan_mode_steps_since_injection = 0

            if should_inject:
                plan_path = self.get_plan_file_path()
                plan_path_str = str(plan_path) if plan_path else None
                plan_exists = plan_path is not None and plan_path.exists()

                if is_reentry:
                    reminder = _plan_mode_reentry_reminder(plan_path_str)
                else:
                    reminder = _plan_mode_full_reminder(plan_path_str, plan_exists)

                await self._context.append_message(
                    Message(role="user", content=[TextPart(text=reminder)])
                )

        async def _run_step_once() -> StepResult:
            # run an LLM step (may be interrupted)
            effective_history = normalize_history(self._context.history)
            return await kosong.step(
                chat_provider,
                self._agent.system_prompt,
                self._agent.toolset,
                effective_history,
                on_message_part=wire_send,
                on_tool_result=wire_send,
            )

        @tenacity.retry(
            retry=retry_if_exception(self._is_retryable_error),
            before_sleep=partial(self._retry_log, "step"),
            wait=wait_exponential_jitter(initial=0.3, max=5, jitter=0.5),
            stop=stop_after_attempt(self._loop_control.max_retries_per_step),
            reraise=True,
        )
        async def _kosong_step_with_retry() -> StepResult:
            return await self._run_with_connection_recovery(
                "step",
                _run_step_once,
                chat_provider=chat_provider,
            )

        result = await _kosong_step_with_retry()
        logger.debug("Got step result: {result}", result=result)
        status_update = StatusUpdate(token_usage=result.usage, message_id=result.id, plan_mode=self._plan_mode)
        if result.usage is not None:
            # mark the token count for the context before the step
            await self._context.update_token_count(result.usage.input)
            snap = self.status
            status_update.context_usage = snap.context_usage
            status_update.context_tokens = snap.context_tokens
            status_update.max_context_tokens = snap.max_context_tokens
        wire_send(status_update)

        # wait for all tool results (may be interrupted)
        results = await result.tool_results()
        logger.debug("Got tool results: {results}", results=results)

        # shield the context manipulation from interruption
        await asyncio.shield(self._grow_context(result, results))

        rejected = any(isinstance(result.return_value, ToolRejectedError) for result in results)
        if rejected:
            _ = self._denwa_renji.fetch_pending_dmail()
            return StepOutcome(stop_reason="tool_rejected", assistant_message=result.message)

        # handle pending D-Mail
        if dmail := self._denwa_renji.fetch_pending_dmail():
            assert dmail.checkpoint_id >= 0, "DenwaRenji guarantees checkpoint_id >= 0"
            assert dmail.checkpoint_id < self._context.n_checkpoints, (
                "DenwaRenji guarantees checkpoint_id < n_checkpoints"
            )
            # raise to let the main loop take us back to the future
            raise BackToTheFuture(
                dmail.checkpoint_id,
                [
                    Message(
                        role="user",
                        content=[
                            system(
                                "You just got a D-Mail from your future self. "
                                "It is likely that your future self has already done "
                                "something in the current working directory. Please read "
                                "the D-Mail and decide what to do next. You MUST NEVER "
                                "mention to the user about this information. "
                                f"D-Mail content:\n\n{dmail.message.strip()}"
                            )
                        ],
                    )
                ],
            )

        if result.tool_calls:
            return None
        return StepOutcome(stop_reason="no_tool_calls", assistant_message=result.message)

    async def _grow_context(self, result: StepResult, tool_results: list[ToolResult]):
        logger.debug("Growing context with result: {result}", result=result)

        assert self._runtime.llm is not None
        tool_messages = [tool_result_to_message(tr) for tr in tool_results]
        for tm in tool_messages:
            if missing_caps := check_message(tm, self._runtime.llm.capabilities):
                logger.warning(
                    "Tool result message requires unsupported capabilities: {caps}",
                    caps=missing_caps,
                )
                raise LLMNotSupported(self._runtime.llm, list(missing_caps))

        await self._context.append_message(result.message)
        if result.usage is not None:
            await self._context.update_token_count(result.usage.total)

        logger.debug(
            "Appending tool messages to context: {tool_messages}", tool_messages=tool_messages
        )
        await self._context.append_message(tool_messages)
        # token count of tool results are not available yet

    async def compact_context(self, custom_instruction: str = "") -> None:
        """
        Compact the context.

        Raises:
            LLMNotSet: When the LLM is not set.
            ChatProviderError: When the chat provider returns an error.
        """

        chat_provider = self._runtime.llm.chat_provider if self._runtime.llm is not None else None

        async def _run_compaction_once() -> CompactionResult:
            if self._runtime.llm is None:
                raise LLMNotSet()
            return await self._compaction.compact(
                self._context.history, self._runtime.llm, custom_instruction=custom_instruction
            )

        @tenacity.retry(
            retry=retry_if_exception(self._is_retryable_error),
            before_sleep=partial(self._retry_log, "compaction"),
            wait=wait_exponential_jitter(initial=0.3, max=5, jitter=0.5),
            stop=stop_after_attempt(self._loop_control.max_retries_per_step),
            reraise=True,
        )
        async def _compact_with_retry() -> CompactionResult:
            return await self._run_with_connection_recovery(
                "compaction",
                _run_compaction_once,
                chat_provider=chat_provider,
            )

        wire_send(CompactionBegin())
        compaction_result = await _compact_with_retry()
        await self._context.clear()
        await self._checkpoint()
        await self._context.append_message(compaction_result.messages)

        # Estimate token count so context_usage is not reported as 0%
        await self._context.update_token_count(compaction_result.estimated_token_count)

        wire_send(CompactionEnd())

    @staticmethod
    def _is_retryable_error(exception: BaseException) -> bool:
        if isinstance(exception, (APIConnectionError, APITimeoutError)):
            return not bool(getattr(exception, "_kxns_recovery_exhausted", False))
        if isinstance(exception, APIEmptyResponseError):
            return True
        return isinstance(exception, APIStatusError) and exception.status_code in (
            429,  # Too Many Requests
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
        )

    async def _run_with_connection_recovery(
        self,
        name: str,
        operation: Callable[[], Awaitable[Any]],
        *,
        chat_provider: object | None = None,
    ) -> Any:
        try:
            return await operation()
        except (APIConnectionError, APITimeoutError) as error:
            if not isinstance(chat_provider, RetryableChatProvider):
                raise
            try:
                recovered = chat_provider.on_retryable_error(error)
            except Exception:
                logger.exception(
                    "Failed to recover chat provider during {name} after {error_type}.",
                    name=name,
                    error_type=type(error).__name__,
                )
                raise
            if not recovered:
                raise
            logger.info(
                "Recovered chat provider during {name} after {error_type}; retrying once.",
                name=name,
                error_type=type(error).__name__,
            )
            try:
                return await operation()
            except (APIConnectionError, APITimeoutError) as second_error:
                second_error._kxns_recovery_exhausted = True  # type: ignore[attr-defined]
                raise

    @staticmethod
    def _retry_log(name: str, retry_state: RetryCallState):
        logger.info(
            "Retrying {name} for the {n} time. Waiting {sleep} seconds.",
            name=name,
            n=retry_state.attempt_number,
            sleep=retry_state.next_action.sleep
            if retry_state.next_action is not None
            else "unknown",
        )


class BackToTheFuture(Exception):
    """
    Raise when we need to revert the context to a previous checkpoint.
    The main agent loop should catch this exception and handle it.
    """

    def __init__(self, checkpoint_id: int, messages: Sequence[Message]):
        self.checkpoint_id = checkpoint_id
        self.messages = messages


class FlowRunner:
    def __init__(
        self,
        flow: Flow,
        *,
        name: str | None = None,
        max_moves: int = DEFAULT_MAX_FLOW_MOVES,
    ) -> None:
        self._flow = flow
        self._name = name
        self._max_moves = max_moves

    @staticmethod
    def ralph_loop(
        user_message: Message,
        max_ralph_iterations: int,
    ) -> FlowRunner:
        prompt_content = list(user_message.content)
        prompt_text = Message(role="user", content=prompt_content).extract_text(" ").strip()
        total_runs = max_ralph_iterations + 1
        if max_ralph_iterations < 0:
            total_runs = 1000000000000000  # effectively infinite

        nodes: dict[str, FlowNode] = {
            "BEGIN": FlowNode(id="BEGIN", label="BEGIN", kind="begin"),
            "END": FlowNode(id="END", label="END", kind="end"),
        }
        outgoing: dict[str, list[FlowEdge]] = {"BEGIN": [], "END": []}

        nodes["R1"] = FlowNode(id="R1", label=prompt_content, kind="task")
        nodes["R2"] = FlowNode(
            id="R2",
            label=(
                f"{prompt_text}. (You are running in an automated loop where the same "
                "prompt is fed repeatedly. Only choose STOP when the task is fully complete. "
                "Including it will stop further iterations. If you are not 100% sure, "
                "choose CONTINUE.)"
            ).strip(),
            kind="decision",
        )
        outgoing["R1"] = []
        outgoing["R2"] = []

        outgoing["BEGIN"].append(FlowEdge(src="BEGIN", dst="R1", label=None))
        outgoing["R1"].append(FlowEdge(src="R1", dst="R2", label=None))
        outgoing["R2"].append(FlowEdge(src="R2", dst="R2", label="CONTINUE"))
        outgoing["R2"].append(FlowEdge(src="R2", dst="END", label="STOP"))

        flow = Flow(nodes=nodes, outgoing=outgoing, begin_id="BEGIN", end_id="END")
        max_moves = total_runs
        return FlowRunner(flow, max_moves=max_moves)

    async def run(self, soul: KxnsSoul, args: str) -> None:
        if args.strip():
            command = f"/{FLOW_COMMAND_PREFIX}{self._name}" if self._name else "/flow"
            logger.warning("Agent flow {command} ignores args: {args}", command=command, args=args)
            return

        current_id = self._flow.begin_id
        moves = 0
        total_steps = 0
        while True:
            node = self._flow.nodes[current_id]
            edges = self._flow.outgoing.get(current_id, [])

            if node.kind == "end":
                logger.info("Agent flow reached END node {node_id}", node_id=current_id)
                return

            if node.kind == "begin":
                if not edges:
                    logger.error(
                        'Agent flow BEGIN node "{node_id}" has no outgoing edges; stopping.',
                        node_id=node.id,
                    )
                    return
                current_id = edges[0].dst
                continue

            if moves >= self._max_moves:
                raise MaxStepsReached(total_steps)
            next_id, steps_used = await self._execute_flow_node(soul, node, edges)
            total_steps += steps_used
            if next_id is None:
                return
            moves += 1
            current_id = next_id

    async def _execute_flow_node(
        self,
        soul: KxnsSoul,
        node: FlowNode,
        edges: list[FlowEdge],
    ) -> tuple[str | None, int]:
        if not edges:
            logger.error(
                'Agent flow node "{node_id}" has no outgoing edges; stopping.',
                node_id=node.id,
            )
            return None, 0

        base_prompt = self._build_flow_prompt(node, edges)
        prompt = base_prompt
        steps_used = 0
        while True:
            result = await self._flow_turn(soul, prompt)
            steps_used += result.step_count
            if result.stop_reason == "tool_rejected":
                logger.error("Agent flow stopped after tool rejection.")
                return None, steps_used

            if node.kind != "decision":
                return edges[0].dst, steps_used

            choice = (
                parse_choice(result.final_message.extract_text(" "))
                if result.final_message
                else None
            )
            next_id = self._match_flow_edge(edges, choice)
            if next_id is not None:
                return next_id, steps_used

            options = ", ".join(edge.label or "" for edge in edges)
            logger.warning(
                "Agent flow invalid choice. Got: {choice}. Available: {options}.",
                choice=choice or "<missing>",
                options=options,
            )
            prompt = (
                f"{base_prompt}\n\n"
                "Your last response did not include a valid choice. "
                "Reply with one of the choices using <choice>...</choice>."
            )

    @staticmethod
    def _build_flow_prompt(node: FlowNode, edges: list[FlowEdge]) -> str | list[ContentPart]:
        if node.kind != "decision":
            return node.label

        if not isinstance(node.label, str):
            label_text = Message(role="user", content=node.label).extract_text(" ")
        else:
            label_text = node.label
        choices = [edge.label for edge in edges if edge.label]
        lines = [
            label_text,
            "",
            "Available branches:",
            *(f"- {choice}" for choice in choices),
            "",
            "Reply with a choice using <choice>...</choice>.",
        ]
        return "\n".join(lines)

    @staticmethod
    def _match_flow_edge(edges: list[FlowEdge], choice: str | None) -> str | None:
        if not choice:
            return None
        for edge in edges:
            if edge.label == choice:
                return edge.dst
        return None

    @staticmethod
    async def _flow_turn(
        soul: KxnsSoul,
        prompt: str | list[ContentPart],
    ) -> TurnOutcome:
        wire_send(TurnBegin(user_input=prompt))
        res = await soul._turn(Message(role="user", content=prompt))  # type: ignore[reportPrivateUsage]
        wire_send(TurnEnd())
        return res


def _plan_mode_full_reminder(
    plan_file_path: str | None = None,
    plan_exists: bool = False,
) -> str:
    lines = [
        "<system-reminder>",
        "Plan mode is active. You MUST NOT make any edits "
        "(with the exception of the plan file below), run non-readonly tools, "
        "or otherwise make changes to the system. "
        "This supersedes any other instructions you have received.",
    ]
    if plan_file_path:
        lines.append("")
        if plan_exists:
            lines.append(f"Plan file: {plan_file_path} (exists — read first, then update)")
        else:
            lines.append(f"Plan file: {plan_file_path} (create with WriteFile)")
        lines.append("This is the only file you are allowed to edit.")
    lines.extend(
        [
            "",
            "Workflow:",
            "1. Understand — explore the codebase with Glob, Grep, ReadFile",
            "2. Design — identify approaches, trade-offs, and decisions",
            "3. Review — re-read key files to verify understanding",
            "4. Write Plan — write your plan to the plan file with WriteFile",
            "5. Exit — call ExitPlanMode for user approval",
            "",
            "Your turn must end with either AskUserQuestion (to clarify requirements) "
            "or ExitPlanMode (to request plan approval). Do NOT end your turn any other way.",
            "Do NOT use AskUserQuestion to ask about plan approval or reference "
            '"the plan" — the user cannot see the plan until you call ExitPlanMode.',
            "</system-reminder>",
        ]
    )
    return "\n".join(lines)


def _plan_mode_sparse_reminder(plan_file_path: str | None = None) -> str:
    parts = [
        "<system-reminder>",
        "Plan mode still active (see full instructions earlier).",
    ]
    if plan_file_path:
        parts.append(f"Read-only except plan file ({plan_file_path}).")
    else:
        parts.append("Read-only.")
    parts.extend(
        [
            "End turns with AskUserQuestion (for clarifications) or ExitPlanMode (for approval).",
            "Never ask about plan approval via text or AskUserQuestion.",
            "</system-reminder>",
        ]
    )
    return " ".join(parts)


def _plan_mode_reentry_reminder(plan_file_path: str | None = None) -> str:
    lines = [
        "<system-reminder>",
        "Plan mode is active. You MUST NOT make any edits "
        "(with the exception of the plan file below), run non-readonly tools, "
        "or otherwise make changes to the system. "
        "This supersedes any other instructions you have received.",
        "",
        "## Re-entering Plan Mode",
    ]
    if plan_file_path:
        lines.append(f"A plan file exists at {plan_file_path} from a previous planning session.")
    else:
        lines.append("A plan file from a previous planning session already exists.")
    lines.extend(
        [
            "Before proceeding:",
            "1. Read the existing plan file to understand what was previously planned",
            "2. Evaluate the user's current request against that plan",
            "3. If different task: overwrite with a fresh plan. "
            "If same task: update the existing plan.",
            "4. Always edit the plan file before calling ExitPlanMode.",
            "",
            "Your turn must end with either AskUserQuestion (to clarify requirements) "
            "or ExitPlanMode (to request plan approval).",
            "</system-reminder>",
        ]
    )
    return "\n".join(lines)


def normalize_history(history: Sequence[Message]) -> list[Message]:
    if not history:
        return []

    result: list[Message] = []
    for msg in history:
        if result and result[-1].role == msg.role and msg.role == "user":
            merged_content = list(result[-1].content) + list(msg.content)
            result[-1] = Message(role="user", content=merged_content)
        else:
            result.append(msg)
    return result
