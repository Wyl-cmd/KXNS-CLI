from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import threading
from typing import Any, cast

import pydantic
from kosong.chat_provider import ChatProviderError
from kosong.tooling import ToolError, ToolResult
from kosong.utils.typing import JsonType

from kxns_cli.constant import USER_AGENT
from kxns_cli.soul import LLMNotSet, LLMNotSupported, MaxStepsReached, RunCancelled, Soul, run_soul
from kxns_cli.soul.kxnssoul import KxnsSoul
from kxns_cli.soul.toolset import KxnsToolset, WireExternalTool
from kxns_cli.utils.aioqueue import Queue, QueueShutDown
from kxns_cli.utils.logging import logger
from kxns_cli.utils.signals import install_sigint_handler
from kxns_cli.wire import Wire
from kxns_cli.wire.types import (
    ApprovalRequest,
    ApprovalResponse,
    QuestionNotSupported,
    QuestionRequest,
    QuestionResponse,
    Request,
    StatusUpdate,
    ToolCallRequest,
    is_event,
    is_request,
)

from .jsonrpc import (
    ClientInfo,
    ErrorCodes,
    JSONRPCCancelMessage,
    JSONRPCErrorObject,
    JSONRPCErrorResponse,
    JSONRPCErrorResponseNullableID,
    JSONRPCEventMessage,
    JSONRPCInitializeMessage,
    JSONRPCInMessage,
    JSONRPCInMessageAdapter,
    JSONRPCMessage,
    JSONRPCOutMessage,
    JSONRPCPromptMessage,
    JSONRPCReplayMessage,
    JSONRPCRequestMessage,
    JSONRPCSetModelMessage,
    JSONRPCSetPlanModeMessage,
    JSONRPCSetThinkingMessage,
    JSONRPCSteerMessage,
    JSONRPCSuccessResponse,
    Statuses,
)

STDIO_BUFFER_LIMIT = 100 * 1024 * 1024


class _ThreadedStdioWriter:
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        import queue as queue_mod

        self._loop = loop
        self._queue: queue_mod.Queue[bytes | None] = queue_mod.Queue()
        self._closed = False

        def _writer() -> None:
            while True:
                try:
                    data = self._queue.get()
                    if data is None:
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                except Exception:
                    break

        self._thread = threading.Thread(target=_writer, daemon=True)
        self._thread.start()

    def write(self, data: bytes) -> None:
        if not self._closed:
            self._queue.put(data)

    async def drain(self) -> None:
        await asyncio.sleep(0)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._queue.put(None)

    async def wait_closed(self) -> None:
        await asyncio.sleep(0)


async def _stdio_streams(limit: int = STDIO_BUFFER_LIMIT) -> tuple[asyncio.StreamReader, _ThreadedStdioWriter | asyncio.StreamWriter]:
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(limit=limit)

    if sys.platform == "win32":
        def _stdin_reader() -> None:
            while True:
                try:
                    line = sys.stdin.buffer.readline()
                    if not line:
                        break
                    loop.call_soon_threadsafe(reader.feed_data, line)
                except Exception:
                    break
            loop.call_soon_threadsafe(reader.feed_eof)

        stdin_thread = threading.Thread(target=_stdin_reader, daemon=True)
        stdin_thread.start()

        writer = _ThreadedStdioWriter(loop)
        return reader, writer
    else:
        # read / write 必须使用各自的 protocol；connect_write_pipe 返回 (transport, protocol)
        read_protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: read_protocol, sys.stdin)
        write_transport, write_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin,
            sys.stdout,
        )
        writer = asyncio.StreamWriter(write_transport, write_protocol, None, loop)
        return reader, writer


class WireServer:
    def __init__(self, soul: Soul):
        self._reader: asyncio.StreamReader | None = None
        self._writer: _ThreadedStdioWriter | asyncio.StreamWriter | None = None

        # outward
        self._write_task: asyncio.Task[None] | None = None
        self._write_queue: Queue[JSONRPCOutMessage] = Queue()

        # inward
        self._dispatch_tasks: set[asyncio.Task[None]] = set()

        # soul running stuffs
        self._soul = soul
        self._cancel_event: asyncio.Event | None = None
        self._pending_requests: dict[str, Request] = {}
        """Maps JSON RPC message IDs to pending `Request`s."""
        self._client_supports_question: bool = False
        """Whether the Wire client supports QuestionRequest."""

        self._client_supports_plan_mode: bool = False
        """Whether the Wire client supports plan mode."""

    async def serve(self) -> None:
        logger.info("Starting Wire server on stdio")

        self._reader, self._writer = await _stdio_streams(limit=STDIO_BUFFER_LIMIT)
        self._write_task = asyncio.create_task(self._write_loop())
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        remove_sigint = install_sigint_handler(loop, stop_event.set)
        read_task = asyncio.create_task(self._read_loop())
        stop_task = asyncio.create_task(stop_event.wait())
        tasks: set[asyncio.Task[Any]] = {read_task, stop_task}
        pending = tasks
        try:
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop_event.is_set():
                logger.info("Wire server interrupted, shutting down")
                if self._cancel_event is not None:
                    self._cancel_event.set()
                if not read_task.done():
                    read_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await read_task
            elif read_task in done:
                read_task.result()
        except KeyboardInterrupt:
            logger.info("Wire server interrupted, shutting down")
            if self._cancel_event is not None:
                self._cancel_event.set()
        finally:
            remove_sigint()
            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            await self._shutdown()

    async def _write_loop(self) -> None:
        assert self._writer is not None

        try:
            while True:
                try:
                    msg = await self._write_queue.get()
                except QueueShutDown:
                    logger.debug("Send queue shut down, stopping Wire server write loop")
                    break
                self._writer.write(msg.model_dump_json().encode("utf-8") + b"\n")
                await self._writer.drain()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Wire server write loop error:")
            raise

    async def _read_loop(self) -> None:
        assert self._reader is not None

        while True:
            raw_line = await self._reader.readline()
            if not raw_line:
                logger.info("stdin closed, Wire server exiting")
                break
            line = raw_line.decode("utf-8", errors="replace").strip()

            try:
                msg_json = json.loads(line)
            except ValueError:
                logger.error("Invalid JSON line: {line}", line=line)
                await self._send_msg(
                    JSONRPCErrorResponseNullableID(
                        id=None,
                        error=JSONRPCErrorObject(
                            code=ErrorCodes.PARSE_ERROR,
                            message="Invalid JSON format",
                        ),
                    )
                )
                continue

            try:
                generic_msg = JSONRPCMessage.model_validate(msg_json)
            except pydantic.ValidationError as e:
                logger.error("Invalid JSON-RPC message: {error}", error=e)
                await self._send_msg(
                    JSONRPCErrorResponseNullableID(
                        id=None,
                        error=JSONRPCErrorObject(
                            code=ErrorCodes.INVALID_REQUEST,
                            message="Invalid request",
                        ),
                    )
                )
                continue

            if generic_msg.is_response():
                # for responses, we skip the method check
                try:
                    msg = JSONRPCInMessageAdapter.validate_python(msg_json)
                except pydantic.ValidationError as e:
                    logger.error("Invalid JSON-RPC response: {error}", error=e)
                    await self._send_msg(
                        JSONRPCErrorResponseNullableID(
                            id=None,
                            error=JSONRPCErrorObject(
                                code=ErrorCodes.INVALID_REQUEST,
                                message="Invalid response",
                            ),
                        )
                    )
                    continue  # ignore invalid json-rpc responses

                if not isinstance(msg, (JSONRPCSuccessResponse, JSONRPCErrorResponse)):
                    logger.error(
                        "Invalid JSON-RPC response message: {msg}",
                        msg=msg_json,
                    )
                    continue  # ignore invalid response messages

                task = asyncio.create_task(self._dispatch_msg(msg))
                task.add_done_callback(self._dispatch_tasks.discard)
                self._dispatch_tasks.add(task)
                continue

            if not generic_msg.method_is_inbound():
                logger.error(
                    "Unexpected JSON-RPC method received: {method}",
                    method=generic_msg.method,
                )
                if generic_msg.id is not None:
                    resp = JSONRPCErrorResponse(
                        id=generic_msg.id,
                        error=JSONRPCErrorObject(
                            code=ErrorCodes.METHOD_NOT_FOUND,
                            message=f"Unexpected method received: {generic_msg.method}",
                        ),
                    )
                    await self._send_msg(resp)
                continue  # ignore unexpected outbound methods

            try:
                msg = JSONRPCInMessageAdapter.validate_python(msg_json)
            except pydantic.ValidationError as e:
                logger.error("Invalid JSON-RPC inbound message: {error}", error=e)
                if generic_msg.id is not None:
                    resp = JSONRPCErrorResponse(
                        id=generic_msg.id,
                        error=JSONRPCErrorObject(
                            code=ErrorCodes.INVALID_PARAMS,
                            message=f"Invalid parameters for method `{generic_msg.method}`",
                        ),
                    )
                    await self._send_msg(resp)
                continue  # ignore invalid inbound messages

            task = asyncio.create_task(self._dispatch_msg(msg))
            task.add_done_callback(self._dispatch_tasks.discard)
            self._dispatch_tasks.add(task)

    async def _shutdown(self) -> None:
        for request in self._pending_requests.values():
            if request.resolved:
                continue
            match request:
                case ApprovalRequest():
                    request.resolve("reject")
                case ToolCallRequest():
                    request.resolve(
                        ToolError(
                            message="Wire connection closed before tool result was received.",
                            brief="Wire closed",
                        )
                    )
                case QuestionRequest():
                    request.resolve({})
        self._pending_requests.clear()

        if self._cancel_event is not None:
            self._cancel_event.set()
            self._cancel_event = None

        self._write_queue.shutdown()
        if self._write_task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await self._write_task

        await asyncio.gather(*self._dispatch_tasks, return_exceptions=True)
        self._dispatch_tasks.clear()

        if self._writer is not None:
            self._writer.close()
            with contextlib.suppress(Exception):
                await self._writer.wait_closed()
            self._writer = None

        self._reader = None

    async def _dispatch_msg(self, msg: JSONRPCInMessage) -> None:
        resp: JSONRPCSuccessResponse | JSONRPCErrorResponse | None = None
        try:
            match msg:
                case JSONRPCInitializeMessage():
                    resp = await self._handle_initialize(msg)
                case JSONRPCPromptMessage():
                    resp = await self._handle_prompt(msg)
                case JSONRPCReplayMessage():
                    resp = await self._handle_replay(msg)
                case JSONRPCSteerMessage():
                    resp = await self._handle_steer(msg)
                case JSONRPCSetPlanModeMessage():
                    resp = await self._handle_set_plan_mode(msg)
                case JSONRPCCancelMessage():
                    resp = await self._handle_cancel(msg)
                case JSONRPCSetThinkingMessage():
                    resp = await self._handle_set_thinking(msg)
                case JSONRPCSetModelMessage():
                    resp = await self._handle_set_model(msg)
                case JSONRPCSuccessResponse() | JSONRPCErrorResponse():
                    await self._handle_response(msg)

            if resp is not None:
                await self._send_msg(resp)
        except Exception:
            logger.exception("Unexpected error dispatching JSONRPC message:")
            raise

    async def _send_msg(self, msg: JSONRPCOutMessage) -> None:
        try:
            await self._write_queue.put(msg)
        except QueueShutDown:
            logger.error("Send queue shut down; dropping message: {msg}", msg=msg)

    @property
    def _is_streaming(self) -> bool:
        return self._cancel_event is not None

    async def _handle_initialize(
        self, msg: JSONRPCInitializeMessage
    ) -> JSONRPCSuccessResponse | JSONRPCErrorResponse:
        if self._is_streaming:
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(
                    code=ErrorCodes.INVALID_STATE,
                    message="An agent turn is already in progress",
                ),
            )

        accepted: list[str] = []
        rejected: list[dict[str, str]] = []
        toolset = None
        if isinstance(self._soul, KxnsSoul) and isinstance(self._soul.agent.toolset, KxnsToolset):
            toolset = self._soul.agent.toolset

        if toolset and msg.params.external_tools:
            for tool in msg.params.external_tools:
                existing = toolset.find(tool.name)
                if existing is not None and not isinstance(existing, WireExternalTool):
                    rejected.append({"name": tool.name, "reason": "conflicts with builtin tool"})
                    continue
                ok, reason = toolset.register_external_tool(
                    tool.name,
                    tool.description,
                    tool.parameters,
                )
                if ok:
                    accepted.append(tool.name)
                else:
                    rejected.append({"name": tool.name, "reason": reason or "invalid schema"})

        slash_commands: list[JsonType] = []
        for cmd in self._soul.available_slash_commands:
            slash_commands.append(
                cast(
                    JsonType,
                    {"name": cmd.name, "description": cmd.description, "aliases": cmd.aliases},
                )
            )

        from kxns_cli.constant import NAME, VERSION
        from kxns_cli.wire.protocol import WIRE_PROTOCOL_VERSION

        result: dict[str, JsonType] = {
            "protocol_version": WIRE_PROTOCOL_VERSION,
            "server": cast(JsonType, {"name": NAME, "version": VERSION}),
            "slash_commands": cast(JsonType, slash_commands),
        }
        if accepted or rejected:
            result["external_tools"] = cast(
                JsonType,
                {
                    "accepted": accepted,
                    "rejected": rejected,
                },
            )

        self._apply_wire_client_info(msg.params.client)

        if msg.params.capabilities is not None:
            self._client_supports_question = msg.params.capabilities.supports_question
            self._client_supports_plan_mode = msg.params.capabilities.supports_plan_mode

        if toolset is not None:
            self._sync_ask_user_tool_visibility(toolset)
            self._sync_plan_mode_tool_visibility(toolset)

        result["capabilities"] = cast(
            JsonType,
            {"supports_question": True, "supports_plan_mode": True},
        )

        return JSONRPCSuccessResponse(
            id=msg.id,
            result=result,
        )

    def _sync_ask_user_tool_visibility(self, toolset: KxnsToolset) -> None:
        """Hide or unhide the AskUserQuestion tool based on client capabilities."""
        from kxns_cli.tools.ask_user import NAME as ASK_USER_TOOL_NAME

        all_toolsets = [toolset]
        if isinstance(self._soul, KxnsSoul):
            for subagent in self._soul.agent.runtime.labor_market.fixed_subagents.values():
                if isinstance(subagent.toolset, KxnsToolset):
                    all_toolsets.append(subagent.toolset)

        if self._client_supports_question:
            for ts in all_toolsets:
                ts.unhide(ASK_USER_TOOL_NAME)
        else:
            for ts in all_toolsets:
                ts.hide(ASK_USER_TOOL_NAME)
            logger.info(
                "Hid {tool} tool: client does not support questions",
                tool=ASK_USER_TOOL_NAME,
            )

    def _sync_plan_mode_tool_visibility(self, toolset: KxnsToolset) -> None:
        from kxns_cli.tools.plan import NAME as EXIT_PLAN_MODE_TOOL_NAME
        from kxns_cli.tools.plan.enter import NAME as ENTER_PLAN_MODE_TOOL_NAME

        plan_tool_names = [ENTER_PLAN_MODE_TOOL_NAME, EXIT_PLAN_MODE_TOOL_NAME]

        all_toolsets = [toolset]
        if isinstance(self._soul, KxnsSoul):
            for subagent in self._soul.agent.runtime.labor_market.fixed_subagents.values():
                if isinstance(subagent.toolset, KxnsToolset):
                    all_toolsets.append(subagent.toolset)

        if self._client_supports_plan_mode:
            for ts in all_toolsets:
                for name in plan_tool_names:
                    ts.unhide(name)
        else:
            for ts in all_toolsets:
                for name in plan_tool_names:
                    ts.hide(name)
            logger.info(
                "Hid plan mode tools: client does not support plan mode",
            )

    def _apply_wire_client_info(self, client: ClientInfo | None) -> None:
        if not isinstance(self._soul, KxnsSoul):
            return
        llm = self._soul.runtime.llm
        if llm is None:
            return

        ua_suffix = ""
        if client is not None:
            ua_suffix = client.name
            if client.version:
                ua_suffix += f" {client.version}"
            ua_suffix = f" ({ua_suffix.strip()})"

        if hasattr(llm.chat_provider, "client") and hasattr(llm.chat_provider.client, "_custom_headers"):
            kxns_client = llm.chat_provider.client
            headers = dict(kxns_client._custom_headers)
            headers["User-Agent"] = f"{USER_AGENT}{ua_suffix}"
            kxns_client._custom_headers = headers

    async def _handle_prompt(
        self, msg: JSONRPCPromptMessage
    ) -> JSONRPCSuccessResponse | JSONRPCErrorResponse:
        if self._is_streaming:
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(
                    code=ErrorCodes.INVALID_STATE, message="An agent turn is already in progress"
                ),
            )

        self._cancel_event = asyncio.Event()
        try:
            await run_soul(
                self._soul,
                msg.params.user_input,
                self._stream_wire_messages,
                self._cancel_event,
                self._soul.wire_file if isinstance(self._soul, KxnsSoul) else None,
            )
            return JSONRPCSuccessResponse(
                id=msg.id,
                result={"status": Statuses.FINISHED},
            )
        except LLMNotSet:
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(code=ErrorCodes.LLM_NOT_SET, message="LLM is not set"),
            )
        except LLMNotSupported as e:
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(code=ErrorCodes.LLM_NOT_SUPPORTED, message=str(e)),
            )
        except ChatProviderError as e:
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(code=ErrorCodes.CHAT_PROVIDER_ERROR, message=str(e)),
            )
        except MaxStepsReached as e:
            return JSONRPCSuccessResponse(
                id=msg.id,
                result={"status": Statuses.MAX_STEPS_REACHED, "steps": e.n_steps},
            )
        except RunCancelled:
            return JSONRPCSuccessResponse(
                id=msg.id,
                result={"status": Statuses.CANCELLED},
            )
        except Exception as e:
            logger.exception("Unexpected error in _handle_prompt")
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(code=ErrorCodes.INTERNAL_ERROR, message=str(e)),
            )
        finally:
            # Clean up any remaining pending requests from this turn.
            # After run_soul() returns, the soul and all subagents are done,
            # so any unresolved requests are stale.
            stale_ids = [k for k, v in self._pending_requests.items() if not v.resolved]
            for msg_id in stale_ids:
                request = self._pending_requests.pop(msg_id)
                match request:
                    case ApprovalRequest():
                        request.resolve("reject")
                    case ToolCallRequest():
                        request.resolve(
                            ToolError(
                                message="Agent turn ended before tool result was received.",
                                brief="Turn ended",
                            )
                        )
                    case QuestionRequest():
                        request.resolve({})
            self._cancel_event = None

    async def _handle_steer(
        self, msg: JSONRPCSteerMessage
    ) -> JSONRPCSuccessResponse | JSONRPCErrorResponse:
        if not isinstance(self._soul, KxnsSoul) or not self._is_streaming:
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(
                    code=ErrorCodes.INVALID_STATE,
                    message="No agent turn is in progress",
                ),
            )

        self._soul.steer(msg.params.user_input)
        return JSONRPCSuccessResponse(
            id=msg.id,
            result={"status": Statuses.STEERED},
        )

    async def _handle_replay(
        self, msg: JSONRPCReplayMessage
    ) -> JSONRPCSuccessResponse | JSONRPCErrorResponse:
        if self._is_streaming:
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(
                    code=ErrorCodes.INVALID_STATE, message="An agent turn is already in progress"
                ),
            )

        wire_file = self._soul.wire_file if isinstance(self._soul, KxnsSoul) else None

        self._cancel_event = asyncio.Event()
        events = 0
        requests = 0
        try:
            if wire_file is None or not wire_file.path.exists():
                return JSONRPCSuccessResponse(
                    id=msg.id,
                    result={"status": Statuses.FINISHED, "events": 0, "requests": 0},
                )

            async for record in wire_file.iter_records():
                if self._cancel_event.is_set():
                    return JSONRPCSuccessResponse(
                        id=msg.id,
                        result={
                            "status": Statuses.CANCELLED,
                            "events": events,
                            "requests": requests,
                        },
                    )

                try:
                    wire_msg = record.to_wire_message()
                except Exception:
                    logger.exception(
                        "Failed to deserialize wire record for replay: {file}",
                        file=wire_file.path,
                    )
                    continue

                if is_request(wire_msg):
                    await self._send_msg(JSONRPCRequestMessage(id=wire_msg.id, params=wire_msg))
                    requests += 1
                elif is_event(wire_msg):
                    await self._send_msg(JSONRPCEventMessage(params=wire_msg))
                    events += 1
                else:
                    # Not reachable for valid WireMessage, but keep a guard for corrupted data.
                    logger.warning(
                        "Skipping non-wire message during replay: {msg}",
                        msg=wire_msg,
                    )

                await asyncio.sleep(0)  # yield control for cancel handling

            if self._cancel_event.is_set():
                return JSONRPCSuccessResponse(
                    id=msg.id,
                    result={
                        "status": Statuses.CANCELLED,
                        "events": events,
                        "requests": requests,
                    },
                )

            return JSONRPCSuccessResponse(
                id=msg.id,
                result={"status": Statuses.FINISHED, "events": events, "requests": requests},
            )
        except Exception:
            logger.exception("Replay failed:")
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(
                    code=ErrorCodes.INTERNAL_ERROR,
                    message="Replay failed",
                ),
            )
        finally:
            self._cancel_event = None

    async def _handle_cancel(
        self, msg: JSONRPCCancelMessage
    ) -> JSONRPCSuccessResponse | JSONRPCErrorResponse:
        if not self._is_streaming:
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(
                    code=ErrorCodes.INVALID_STATE, message="No agent turn is in progress"
                ),
            )

        assert self._cancel_event is not None
        self._cancel_event.set()
        return JSONRPCSuccessResponse(
            id=msg.id,
            result={},
        )

    async def _handle_set_thinking(
        self, msg: JSONRPCSetThinkingMessage
    ) -> JSONRPCSuccessResponse | JSONRPCErrorResponse:
        if not isinstance(self._soul, KxnsSoul):
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(
                    code=ErrorCodes.INTERNAL_ERROR,
                    message="Thinking mode is not supported by this soul",
                ),
            )

        self._apply_thinking(self._soul, msg.params.enabled)

        thinking_state = self._soul.thinking
        status = StatusUpdate(thinking=thinking_state)
        await self._send_msg(JSONRPCEventMessage(params=status))

        return JSONRPCSuccessResponse(
            id=msg.id,
            result={},
        )

    async def _handle_set_plan_mode(
        self, msg: JSONRPCSetPlanModeMessage
    ) -> JSONRPCSuccessResponse | JSONRPCErrorResponse:
        if not isinstance(self._soul, KxnsSoul):
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(
                    code=ErrorCodes.INVALID_STATE,
                    message="Plan mode is not supported",
                ),
            )

        new_state = await self._soul.set_plan_mode_from_manual(msg.params.enabled)

        status = StatusUpdate(plan_mode=new_state)
        await self._send_msg(JSONRPCEventMessage(params=status))
        return JSONRPCSuccessResponse(
            id=msg.id,
            result={"status": "ok", "plan_mode": new_state},
        )

    @staticmethod
    def _apply_thinking(soul: KxnsSoul, enabled: bool) -> None:
        from kosong.chat_provider import ThinkingEffort

        llm = soul.runtime.llm
        if llm is None:
            return

        capabilities = llm.capabilities or set()
        if "always_thinking" in capabilities:
            llm.chat_provider = llm.chat_provider.with_thinking("high")
            return
        if enabled and "thinking" not in capabilities:
            return

        effort: ThinkingEffort = "high" if enabled else "off"

        llm.chat_provider = llm.chat_provider.with_thinking(effort)

    async def _handle_set_model(
        self, msg: JSONRPCSetModelMessage
    ) -> JSONRPCSuccessResponse | JSONRPCErrorResponse:
        if not isinstance(self._soul, KxnsSoul):
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(
                    code=ErrorCodes.INTERNAL_ERROR,
                    message="Model switching is not supported by this soul",
                ),
            )

        from kxns_cli.config import load_config
        from kxns_cli.llm import augment_provider_with_env_vars, create_llm

        try:
            config = load_config()
        except Exception:
            config = self._soul.runtime.config

        model_name = msg.params.model

        model_cfg = config.models.get(model_name)
        if model_cfg is None:
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(
                    code=ErrorCodes.LLM_NOT_SUPPORTED,
                    message=f"Model '{model_name}' is not configured",
                ),
            )

        provider_cfg = config.providers.get(model_cfg.provider)
        if provider_cfg is None:
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(
                    code=ErrorCodes.LLM_NOT_SUPPORTED,
                    message=f"Provider '{model_cfg.provider}' for model '{model_name}' is not configured",
                ),
            )

        # 深拷贝后套环境变量，与 app.py / 标题生成路径一致
        model_cfg = model_cfg.model_copy(deep=True)
        provider_cfg = provider_cfg.model_copy(deep=True)
        augment_provider_with_env_vars(provider_cfg, model_cfg)

        old_llm = self._soul.runtime.llm
        thinking_enabled = old_llm is not None and old_llm.chat_provider.thinking_effort not in (None, "off")

        try:
            new_llm = create_llm(
                provider_cfg,
                model_cfg,
                thinking=thinking_enabled,
                session_id=self._soul.runtime.session.id,
                oauth=self._soul.runtime.oauth,
            )
        except Exception as e:
            logger.error("Failed to create LLM for model '{model}': {error}", model=model_name, error=e)
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(
                    code=ErrorCodes.LLM_NOT_SUPPORTED,
                    message=f"Failed to create LLM for model '{model_name}': {e}",
                ),
            )

        if new_llm is None:
            return JSONRPCErrorResponse(
                id=msg.id,
                error=JSONRPCErrorObject(
                    code=ErrorCodes.LLM_NOT_SUPPORTED,
                    message=f"Failed to create LLM for model '{model_name}'",
                ),
            )

        self._soul.runtime.llm = new_llm
        logger.info("Switched model to {model}", model=model_name)

        status = StatusUpdate(model=model_name)
        await self._send_msg(JSONRPCEventMessage(params=status))

        return JSONRPCSuccessResponse(
            id=msg.id,
            result={"model": model_name},
        )

    async def _handle_response(self, msg: JSONRPCSuccessResponse | JSONRPCErrorResponse) -> None:
        request = self._pending_requests.pop(msg.id, None)
        if request is None:
            logger.error("No pending request for response id={id}", id=msg.id)
            return

        match request:
            case ApprovalRequest():
                if isinstance(msg, JSONRPCErrorResponse):
                    request.resolve("reject")
                    return

                try:
                    result = ApprovalResponse.model_validate(msg.result)
                except pydantic.ValidationError as e:
                    logger.error(
                        "Invalid response result for request id={id}: {error}",
                        id=msg.id,
                        error=e,
                    )
                    request.resolve("reject")
                    return

                if result.request_id != request.id:
                    logger.warning(
                        "Approval response id mismatch: request={request_id}, "
                        "response={response_id}",
                        request_id=request.id,
                        response_id=result.request_id,
                    )
                request.resolve(result.response)
            case ToolCallRequest():
                if isinstance(msg, JSONRPCErrorResponse):
                    error = msg.error.message
                    request.resolve(
                        ToolError(
                            message=error,
                            brief="External tool error",
                        )
                    )
                    return

                try:
                    tool_result = ToolResult.model_validate(msg.result)
                except pydantic.ValidationError as e:
                    logger.error(
                        "Invalid tool result for request id={id}: {error}",
                        id=msg.id,
                        error=e,
                    )
                    request.resolve(
                        ToolError(
                            message="Invalid tool result payload from client.",
                            brief="Invalid tool result",
                        )
                    )
                    return
                if tool_result.tool_call_id != request.id:
                    logger.warning(
                        "Tool result id mismatch: request={request_id}, result={result_id}",
                        request_id=request.id,
                        result_id=tool_result.tool_call_id,
                    )
                request.resolve(tool_result.return_value)
            case QuestionRequest():
                if isinstance(msg, JSONRPCErrorResponse):
                    request.resolve({})
                    return

                try:
                    result = QuestionResponse.model_validate(msg.result)
                except pydantic.ValidationError as e:
                    logger.error(
                        "Invalid question response for request id={id}: {error}",
                        id=msg.id,
                        error=e,
                    )
                    request.resolve({})
                    return

                if result.request_id != request.id:
                    logger.warning(
                        "Question response id mismatch: request={request_id}, "
                        "response={response_id}",
                        request_id=request.id,
                        response_id=result.request_id,
                    )
                request.resolve(result.answers)

    async def _stream_wire_messages(self, wire: Wire) -> None:
        wire_ui = wire.ui_side(merge=False)
        while True:
            msg = await wire_ui.receive()
            match msg:
                case ApprovalRequest():
                    await self._request_approval(msg)
                case ToolCallRequest():
                    await self._request_external_tool(msg)
                case QuestionRequest():
                    await self._request_question(msg)
                case _:
                    await self._send_msg(JSONRPCEventMessage(method="event", params=msg))

    async def _request_approval(self, request: ApprovalRequest) -> None:
        msg_id = request.id  # just use the approval request id as message id
        self._pending_requests[msg_id] = request
        await self._send_msg(JSONRPCRequestMessage(id=msg_id, params=request))
        # Do NOT await request.wait() here.  The approval future is awaited by
        # the tool that created the request (inside the soul task).  Blocking the
        # UI loop would prevent ALL subsequent Wire messages - from every
        # concurrent subagent - from reaching stdout, causing a cascade deadlock
        # when the approval response is lost (e.g. no WebSocket connected).

    async def _request_external_tool(self, request: ToolCallRequest) -> None:
        msg_id = request.id
        self._pending_requests[msg_id] = request
        await self._send_msg(JSONRPCRequestMessage(id=msg_id, params=request))
        # Same rationale as _request_approval: do not block the UI loop.

    async def _request_question(self, request: QuestionRequest) -> None:
        if not self._client_supports_question:
            # Client does not support interactive questions; signal the tool
            # so it can tell the LLM to use an alternative approach.
            request.set_exception(QuestionNotSupported())
            return
        msg_id = request.id
        self._pending_requests[msg_id] = request
        await self._send_msg(JSONRPCRequestMessage(id=msg_id, params=request))
        # Same rationale as _request_approval: do not block the UI loop.
