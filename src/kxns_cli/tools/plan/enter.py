from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import override
from uuid import uuid4

from kosong.tooling import CallableTool2, Tool, ToolError, ToolReturnValue
from pydantic import BaseModel

from kxns_cli.soul import get_wire_or_none, wire_send
from kxns_cli.soul.toolset import get_current_tool_call_or_none
from kxns_cli.tools.utils import load_desc
from kxns_cli.wire.types import QuestionItem, QuestionNotSupported, QuestionOption, QuestionRequest

logger = logging.getLogger(__name__)

NAME = "EnterPlanMode"

_DEFAULT_DESCRIPTION = load_desc(Path(__file__).parent / "enter_description.md")
_YOLO_DESCRIPTION = load_desc(Path(__file__).parent / "enter_description_yolo.md")


class Params(BaseModel):
    pass


class EnterPlanMode(CallableTool2[Params]):
    name: str = NAME
    description: str = _DEFAULT_DESCRIPTION
    params: type[Params] = Params

    def __init__(self) -> None:
        super().__init__()
        self._toggle_callback: Callable[[], Awaitable[bool]] | None = None
        self._plan_file_path_getter: Callable[[], Path | None] | None = None
        self._plan_mode_checker: Callable[[], bool] | None = None
        self._yolo_checker: Callable[[], bool] | None = None
        self._cached_yolo: bool = False

    def bind(
        self,
        toggle_callback: Callable[[], Awaitable[bool]],
        plan_file_path_getter: Callable[[], Path | None],
        plan_mode_checker: Callable[[], bool],
        yolo_checker: Callable[[], bool] | None = None,
    ) -> None:
        self._toggle_callback = toggle_callback
        self._plan_file_path_getter = plan_file_path_getter
        self._plan_mode_checker = plan_mode_checker
        self._yolo_checker = yolo_checker

    @property
    def base(self):
        if self._yolo_checker is not None:
            in_yolo = self._yolo_checker()
            if in_yolo != self._cached_yolo:
                self._cached_yolo = in_yolo
                desc = _YOLO_DESCRIPTION if in_yolo else _DEFAULT_DESCRIPTION
                self._base = Tool(name=self._base.name, description=desc, parameters=self._base.parameters)
        return self._base

    @override
    async def __call__(self, params: Params) -> ToolReturnValue:
        if self._plan_mode_checker and self._plan_mode_checker():
            return ToolError(
                message="Already in plan mode. Use ExitPlanMode when your plan is ready.",
                brief="Already in plan mode",
            )

        if not self._toggle_callback or not self._plan_file_path_getter:
            return ToolError(
                message="EnterPlanMode is not properly initialized.",
                brief="Not initialized",
            )

        wire = get_wire_or_none()
        if wire is None:
            return ToolError(
                message="Cannot request plan mode entry: Wire is not available.",
                brief="Wire unavailable",
            )

        tool_call = get_current_tool_call_or_none()
        if tool_call is None:
            return ToolError(
                message="EnterPlanMode must be called from a tool call context.",
                brief="Invalid context",
            )

        request = QuestionRequest(
            id=str(uuid4()),
            tool_call_id=tool_call.id,
            questions=[
                QuestionItem(
                    question="Enter plan mode?",
                    header="Plan Mode",
                    options=[
                        QuestionOption(
                            label="Yes",
                            description="Enter plan mode to explore and design an approach",
                        ),
                        QuestionOption(
                            label="No",
                            description="Skip planning, start implementing now",
                        ),
                    ],
                )
            ],
        )

        wire_send(request)

        try:
            answers = await request.wait()
        except QuestionNotSupported:
            new_state = await self._toggle_callback()
            plan_path = self._plan_file_path_getter()
            path_hint = str(plan_path) if plan_path else "plan file"
            return ToolReturnValue(
                is_error=False,
                output=(
                    f"Plan mode activated (client does not support questions). "
                    f"You MUST NOT edit code files — only read and plan.\n"
                    f"Plan file: {path_hint}\n"
                    f"Workflow: explore with Glob/Grep/ReadFile → design approach → "
                    f"write plan with WriteFile → call ExitPlanMode."
                ),
                message="Plan mode activated.",
            )
        except Exception:
            logger.exception("Failed to get user response for plan mode entry")
            return ToolError(
                message="Failed to get user response for plan mode entry.",
                brief="Entry failed",
            )

        if not answers:
            return ToolReturnValue(
                is_error=False,
                output="User dismissed the plan mode request. Continue with your current approach.",
                message="Plan mode dismissed",
            )

        chose_yes = any(v == "Yes" for v in answers.values())

        if chose_yes:
            new_state = await self._toggle_callback()
            plan_path = self._plan_file_path_getter()
            path_hint = str(plan_path) if plan_path else "plan file"
            return ToolReturnValue(
                is_error=False,
                output=(
                    f"Plan mode activated. You MUST NOT edit code files — only read and plan.\n"
                    f"Plan file: {path_hint}\n"
                    f"Workflow: explore with Glob/Grep/ReadFile → design approach → "
                    f"write plan with WriteFile → call ExitPlanMode."
                ),
                message="Plan mode activated.",
            )
        else:
            return ToolReturnValue(
                is_error=False,
                output="User declined to enter plan mode. Continue with your current approach.",
                message="Plan mode declined",
            )
