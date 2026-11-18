"""Presença: quem abriu o app nos últimos instantes. Fica em memória (sem gravar no banco)."""

import time
import uuid

TTL_SECONDS = 120

_seen: dict[uuid.UUID, float] = {}


def ping(user_id: uuid.UUID, now: float | None = None) -> int:
    t = time.monotonic() if now is None else now
    _seen[user_id] = t
    return count(t)


def count(now: float | None = None) -> int:
    t = time.monotonic() if now is None else now
    for uid in [u for u, seen in _seen.items() if t - seen > TTL_SECONDS]:
        del _seen[uid]
    return len(_seen)


def reset() -> None:
    _seen.clear()
