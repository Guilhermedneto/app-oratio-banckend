import asyncio
import json
from dataclasses import dataclass
from typing import Protocol

from app.core.config import get_settings


class PushGone(Exception):
    """Assinatura expirada (404/410): deve ser removida."""


@dataclass
class Subscription:
    endpoint: str
    p256dh: str
    auth: str


class PushSender(Protocol):
    async def send(self, sub: Subscription, payload: dict[str, str]) -> None: ...


class WebPushSender:
    async def send(self, sub: Subscription, payload: dict[str, str]) -> None:
        from pywebpush import WebPushException, webpush

        s = get_settings()

        def _send() -> None:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=json.dumps(payload),
                vapid_private_key=s.vapid_private_key,
                vapid_claims={"sub": s.vapid_subject},
            )

        try:
            await asyncio.to_thread(_send)
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                raise PushGone from exc
            raise
