"""Background task manager for scan jobs, worker agents, and lifecycle tasks."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class TaskState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class ManagedTask:
    name: str
    coro: Awaitable[Any]
    job_id: str = ""
    state: TaskState = TaskState.PENDING
    result: Any = None
    error: str | None = None
    _asyncio_task: asyncio.Task[Any] | None = None


@dataclass(slots=True)
class BackgroundTaskManager:
    """Lightweight background task manager with lifecycle tracking.

    Tracks scan jobs, worker agents, and long-running operations.
    Integrates with Shell UI's existing _background_tasks pattern.
    """

    max_tasks: int = 16
    _tasks: dict[str, ManagedTask] = field(default_factory=dict)

    async def submit(
        self,
        name: str,
        coro: Awaitable[Any],
        job_id: str = "",
        on_done: Callable[[ManagedTask], Awaitable[Any]] | None = None,
    ) -> ManagedTask:
        """Submit a background task and return its managed handle immediately."""
        if len(self._tasks) >= self.max_tasks:
            raise RuntimeError(f"Max background tasks ({self.max_tasks}) reached")

        task_id = job_id or name
        mt = ManagedTask(name=name, coro=coro, job_id=task_id)
        self._tasks[task_id] = mt

        async def _runner() -> None:
            mt.state = TaskState.RUNNING
            try:
                mt.result = await coro
                mt.state = TaskState.DONE
            except asyncio.CancelledError:
                mt.state = TaskState.CANCELLED
            except Exception as exc:
                mt.state = TaskState.FAILED
                mt.error = str(exc)
                logger.warning(f"Background task '{name}' failed: {exc}")
            if on_done:
                try:
                    await on_done(mt)
                except Exception:
                    logger.warning(f"on_done callback for '{name}' failed", exc_info=True)

        mt._asyncio_task = asyncio.create_task(_runner())
        return mt

    async def cancel(self, task_id: str) -> bool:
        """Cancel a running task by ID. Returns True if cancelled."""
        mt = self._tasks.get(task_id)
        if mt and mt._asyncio_task and not mt._asyncio_task.done():
            mt._asyncio_task.cancel()
            return True
        return False

    def get(self, task_id: str) -> ManagedTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self, state: TaskState | None = None) -> list[ManagedTask]:
        tasks = list(self._tasks.values())
        if state:
            tasks = [t for t in tasks if t.state == state]
        return tasks

    @property
    def active_count(self) -> int:
        return sum(
            1 for t in self._tasks.values() if t.state in (TaskState.PENDING, TaskState.RUNNING)
        )

    async def cleanup(self) -> None:
        """Cancel all running tasks and clear registry."""
        for mt in list(self._tasks.values()):
            if mt._asyncio_task and not mt._asyncio_task.done():
                mt._asyncio_task.cancel()
        self._tasks.clear()
