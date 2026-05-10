from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import override
from uuid import uuid4

from kosong.tooling import CallableTool2, ToolError, ToolReturnValue
from pydantic import BaseModel

from kxns_cli.soul import get_wire_or_none, wire_send
from kxns_cli.soul.toolset import get_current_tool_call_or_none
from kxns_cli.tools.utils import ToolRejectedError, load_desc
from kxns_cli.wire.types import QuestionItem, QuestionNotSupported, QuestionOption, QuestionRequest

logger = logging.getLogger(__name__)

NAME = "ExitPlanMode"


class Params(BaseModel):
    pass


class ExitPlanMode(CallableTool2[Params]):
    name: str = NAME
    description: str = load_desc(Path(__file__).parent / "description.md")
    params: type[Params] = Params

    def __init__(self) -> None:
        super().__init__()
        self._toggle_callback: Callable[[], Awaitable[bool]] | None = None
        self._plan_file_path_getter: Callable[[], Path | None] | None = None
        self._plan_mode_checker: Callable[[], bool] | None = None

    def bind(
        self,
        toggle_callback: Callable[[], Awaitable[bool]],
        plan_file_path_getter: Callable[[], Path | None],
        plan_mode_checker: Callable[[], bool],
    ) -> None:
        self._toggle_callback = toggle_callback
        self._plan_file_path_getter = plan_file_path_getter
        self._plan_mode_checker = plan_mode_checker

    @override
    async def __call__(self, params: Params) -> ToolReturnValue:
        if not self._plan_mode_checker or not self._plan_mode_checker():
            return ToolError(
                message="Not in plan mode. ExitPlanMode is only available during plan mode.",
                brief="Not in plan mode",
            )

        if not self._toggle_callback or not self._plan_file_path_getter:
            return ToolError(
                message="ExitPlanMode is not properly initialized.",
                brief="Not initialized",
            )

        plan_path = self._plan_file_path_getter()
        plan_content = None
        if plan_path and plan_path.exists():
            try:
                plan_content = await asyncio.to_thread(plan_path.read_text, encoding="utf-8")
            except Exception:
                logger.exception("Failed to read plan file")
                plan_content = None

        if not plan_content:
            path_hint = str(plan_path) if plan_path else "plan file"
            return ToolError(
                message=f"No plan file found. Write your plan to {path_hint} first, then call ExitPlanMode.",
                brief="No plan file",
            )

        wire = get_wire_or_none()
        if wire is None:
            return ToolError(
                message="Cannot request plan approval: Wire is not available.",
                brief="Wire unavailable",
            )

        tool_call = get_current_tool_call_or_none()
        if tool_call is None:
            return ToolError(
                message="ExitPlanMode must be called from a tool call context.",
                brief="Invalid context",
            )

        request = QuestionRequest(
            id=str(uuid4()),
            tool_call_id=tool_call.id,
            questions=[
                QuestionItem(
                    question=f"Plan ready for review (saved at {plan_path}):",
                    header="Plan",
                    body=plan_content,
                    options=[
                        QuestionOption(
                            label="Approve",
                            description="Exit plan mode and start execution",
                        ),
                        QuestionOption(
                            label="Reject",
                            description="Stay in plan mode and continue conversation",
                        ),
                    ],
                    other_label="Revise",
                    other_description="Stay in plan mode and provide feedback",
                )
            ],
        )

        wire_send(request)

        try:
            answers = await request.wait()
        except QuestionNotSupported:
            await self._toggle_callback()
            return ToolReturnValue(
                is_error=False,
                output=f"Plan mode deactivated (client does not support questions). Plan saved at: {plan_path}",
                message=f"Plan mode deactivated. Plan: {plan_path}",
            )
        except Exception:
            logger.exception("Failed to get user response for plan approval")
            return ToolError(
                message="Failed to get user response for plan approval.",
                brief="Approval failed",
            )

        if not answers:
            return ToolReturnValue(
                is_error=False,
                output="User dismissed the plan review. Continue working on your plan and call ExitPlanMode again when ready.",
                message="Plan review dismissed",
            )

        chose_approve = any(v == "Approve" for v in answers.values())
        chose_reject = any(v == "Reject" for v in answers.values())

        if chose_approve:
            await self._toggle_callback()
            return ToolReturnValue(
                is_error=False,
                output=f"Plan approved by user. Plan mode deactivated. Plan saved at: {plan_path}",
                message=f"Plan mode deactivated. Plan: {plan_path}",
            )
        elif chose_reject:
            return ToolRejectedError(
                message="Plan rejected by user. Stay in plan mode and continue conversation.",
            )
        else:
            feedback = ""
            for v in answers.values():
                if v not in ("Approve", "Reject"):
                    feedback = v
            msg = "Plan needs revision. Please revise your plan based on feedback and call ExitPlanMode again."
            if feedback:
                msg += f"\n\nUser feedback: {feedback}"
            return ToolReturnValue(
                is_error=False,
                output=msg,
                message="Plan needs revision",
            )
