import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.webpush import PushGone, PushSender, Subscription
from app.models import PushSubscription, UserSettings
from app.repositories import personal as repo

log = logging.getLogger("oratio.push")
WINDOW_MIN = 15


def is_due(notify_minutes: int, tz: str, now_utc: datetime) -> bool:
    """Devido se o horário local atual está na janela [notify, notify + 15 min)."""
    try:
        local = now_utc.astimezone(ZoneInfo(tz))
    except ZoneInfoNotFoundError:
        return False
    current = local.hour * 60 + local.minute
    return 0 <= (current - notify_minutes) % (24 * 60) < WINDOW_MIN


async def send_due_reminders(
    s: AsyncSession, sender: PushSender, now: datetime | None = None
) -> int:
    now = now or datetime.now(UTC)
    q = (
        select(UserSettings, PushSubscription)
        .join(PushSubscription, PushSubscription.user_id == UserSettings.user_id)
        .where(UserSettings.notify_time.is_not(None))
    )
    sent = 0
    for settings, sub in (await s.execute(q)).all():
        nt = settings.notify_time
        if nt is None or not is_due(nt.hour * 60 + nt.minute, settings.timezone, now):
            continue
        try:
            await sender.send(
                Subscription(sub.endpoint, sub.p256dh, sub.auth),
                {"title": "Oratio", "body": "É hora da sua oração de hoje.", "url": "/"},
            )
            sent += 1
        except PushGone:
            await repo.delete_subscription_by_endpoint(s, sub.endpoint)
        except Exception:
            log.exception("falha ao enviar push")
    await s.commit()
    return sent
