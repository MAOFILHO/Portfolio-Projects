"""Server-Sent Events helpers shared by the streaming demos.

Every demo streams the same two kinds of thing over this wire format: a
running trail of "agent did X" progress lines (with a timing/log UI in
common — see `demos/progress-log.js`) and, for Research and Travel, partially
validated Pydantic output pushed as it's produced. `drain_progress` is generic
over the queued item type so both fit through one implementation.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Awaitable
from typing import Any, TypeVar

from fastapi.responses import StreamingResponse

T = TypeVar("T")
QueueItemT = TypeVar("QueueItemT")

# Nginx/ALB-style buffering would defeat the point of streaming: events must
# reach the browser as they happen, not batched at the end.
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"


def sse_response(stream: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(stream, media_type="text/event-stream", headers=SSE_HEADERS)


async def drain_progress(
    task: Awaitable[T],
    queue: asyncio.Queue[QueueItemT],
) -> AsyncIterator[QueueItemT | T]:
    """Interleave a long-running task with the items it queues as it runs.

    Yields each queued item while `task` is still running, then yields the
    task's result as the final item. Callers distinguish the two by type (a
    `str`/`dict` progress item vs. the task's own result type). Items queued
    in the final moments before the task finishes are drained afterwards, so
    none are lost to the race.

    Exceptions from `task` propagate to the caller unchanged — a failing
    pipeline should surface as an error event, not a silently truncated stream.
    """
    pending_task = asyncio.ensure_future(task)

    while not pending_task.done():
        get_message = asyncio.create_task(queue.get())
        done, _ = await asyncio.wait(
            {pending_task, get_message}, return_when=asyncio.FIRST_COMPLETED
        )
        if get_message in done:
            yield get_message.result()
        else:
            get_message.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await get_message

    while not queue.empty():
        yield queue.get_nowait()

    yield pending_task.result()
