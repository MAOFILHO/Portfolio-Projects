"""Server-Sent Events helpers shared by the streaming demos.

Two demos stream for different reasons — Research Analyst pushes discrete
progress messages from a `pydantic_graph` run, Travel Planner pushes partially
validated Pydantic models from `run_stream` — but both need the same wire
format and the same "keep the ALB's idle timeout from firing" property, so the
encoding lives here rather than being reimplemented per demo.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Awaitable
from typing import Any, TypeVar

from fastapi.responses import StreamingResponse

T = TypeVar("T")

# Nginx/ALB-style buffering would defeat the point of streaming: events must
# reach the browser as they happen, not batched at the end.
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"


def sse_response(stream: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(stream, media_type="text/event-stream", headers=SSE_HEADERS)


async def drain_progress(
    task: Awaitable[T],
    queue: asyncio.Queue[str],
) -> AsyncIterator[str | T]:
    """Interleave a long-running task with the progress messages it queues.

    Yields each queued message as a `str` while `task` is still running, then
    yields the task's result as the final item. Callers distinguish the two by
    type. Progress messages emitted in the final moments before the task
    finishes are drained afterwards, so none are lost to the race.

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
