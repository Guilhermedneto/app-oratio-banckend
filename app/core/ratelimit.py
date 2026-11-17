import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request

from app.core.config import get_settings

_hits: dict[str, deque[float]] = defaultdict(deque)


def reset() -> None:
    _hits.clear()


def rate_limit(name: str) -> Callable[[Request], Awaitable[None]]:
    async def dep(request: Request) -> None:
        s = get_settings()
        if not s.rate_limit_enabled:
            return
        ip = request.client.host if request.client else "unknown"
        q = _hits[f"{name}:{ip}"]
        now = time.monotonic()
        while q and now - q[0] > s.rate_limit_window_s:
            q.popleft()
        if len(q) >= s.rate_limit_max:
            raise HTTPException(429, "Muitas tentativas. Tente novamente em instantes.")
        q.append(now)

    return dep
