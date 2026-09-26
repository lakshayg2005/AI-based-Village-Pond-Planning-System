from __future__ import annotations

import asyncio
from typing import Callable, TypeVar

from fastapi import HTTPException

T = TypeVar("T")

# One heavy analysis at a time: the deployment target has a single vCPU and
# 512 MB of RAM, so parallel analyses would only slow each other down or OOM.
_slot = asyncio.Semaphore(1)
QUEUE_TIMEOUT_S = 60.0
RUN_TIMEOUT_S = 120.0


async def run_exclusive(func: Callable[..., T], *args, **kwargs) -> T:
    try:
        await asyncio.wait_for(_slot.acquire(), timeout=QUEUE_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=503,
            detail="Server is busy with other analyses. Please retry shortly.",
        )
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(func, *args, **kwargs),
            timeout=RUN_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Analysis took too long. Try a smaller area.",
        )
    finally:
        _slot.release()
