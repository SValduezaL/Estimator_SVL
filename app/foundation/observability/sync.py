"""Utilidades para propagar contextvars en ejecutores síncronos."""

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


async def run_sync_with_context(
    loop: asyncio.AbstractEventLoop,
    executor: object | None,
    func: Callable[..., T],
    /,
    *args: object,
    **kwargs: object,
) -> T:
    ctx = contextvars.copy_context()
    return await loop.run_in_executor(
        executor,
        lambda: ctx.run(func, *args, **kwargs),
    )
