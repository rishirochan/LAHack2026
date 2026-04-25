"""Helpers for non-blocking persistence from synchronous session managers."""

import asyncio
import inspect
import logging
from collections.abc import Awaitable
from typing import Any

logger = logging.getLogger(__name__)
_SERIALIZED_WRITES: dict[str, asyncio.Task[Any]] = {}


def schedule_repository_write(awaitable: Awaitable[Any], *, key: str | None = None) -> None:
    """Schedule a persistence write when called inside an event loop."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        if inspect.iscoroutine(awaitable):
            awaitable.close()
        return

    if key is None:
        task = loop.create_task(awaitable)
    else:
        previous_task = _SERIALIZED_WRITES.get(key)
        task = loop.create_task(_run_serialized_write(awaitable, previous_task))
        _SERIALIZED_WRITES[key] = task
        task.add_done_callback(lambda completed_task, write_key=key: _clear_serialized_write(write_key, completed_task))

    task.add_done_callback(_log_task_exception)


async def _run_serialized_write(
    awaitable: Awaitable[Any],
    previous_task: asyncio.Task[Any] | None,
) -> Any:
    if previous_task is not None:
        try:
            await previous_task
        except Exception:
            pass
    return await awaitable


def _clear_serialized_write(key: str, task: asyncio.Task[Any]) -> None:
    current_task = _SERIALIZED_WRITES.get(key)
    if current_task is task:
        _SERIALIZED_WRITES.pop(key, None)


def _log_task_exception(task: asyncio.Task[Any]) -> None:
    try:
        task.result()
    except Exception:
        logger.exception("Background persistence write failed.")
