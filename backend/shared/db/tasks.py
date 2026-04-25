"""Helpers for non-blocking persistence from synchronous session managers."""

import asyncio
import inspect
import logging
from collections.abc import Awaitable
from typing import Any

logger = logging.getLogger(__name__)


def schedule_repository_write(awaitable: Awaitable[Any]) -> None:
    """Schedule a persistence write when called inside an event loop."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        if inspect.iscoroutine(awaitable):
            awaitable.close()
        return

    task = loop.create_task(awaitable)
    task.add_done_callback(_log_task_exception)


def _log_task_exception(task: asyncio.Task[Any]) -> None:
    try:
        task.result()
    except Exception:
        logger.exception("Background persistence write failed.")
