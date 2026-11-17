import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.integrations.webpush import PushGone, PushSender, Subscription
from app.models import PrayerComment, PrayerRequest, User
from app.repositories import community as repo
from app.repositories import personal as personal_repo
from app.repositories import users as users_repo
from app.schemas.api import (
    NewRequestsOut,
    PrayedOut,
    PrayerCommentOut,
    PrayerFeedOut,
    PrayerRequestOut,
)

log = logging.getLogger("oratio.community")
PUSH_LIMIT = 1000


def _out(row: repo.Row, me: uuid.UUID) -> PrayerRequestOut:
    req, name, prayed, comments, i_prayed = row
    return PrayerRequestOut(
        id=req.id,
        text=req.text,
        author_name=None if req.anonymous else name,
        mine=req.user_id == me,
        created_at=req.created_at,
        prayed_count=prayed,
        comment_count=comments,
        i_prayed=bool(i_prayed),
    )


async def _check_rate(s: AsyncSession, user: User) -> None:
    cfg = get_settings()
    since = datetime.now(UTC) - timedelta(seconds=cfg.community_post_window_s)
    if await repo.count_recent_posts(s, user.id, since) >= cfg.community_post_limit:
        raise HTTPException(429, "Muitas publicações em pouco tempo. Tente mais tarde.")


async def feed(
    s: AsyncSession, user: User, before: datetime | None, limit: int, mine_only: bool
) -> PrayerFeedOut:
    rows = await repo.feed(s, user.id, before, limit + 1, mine_only)
    page = rows[:limit]
    nxt = page[-1][0].created_at if len(rows) > limit and page else None
    return PrayerFeedOut(items=[_out(r, user.id) for r in page], next_before=nxt)


async def create_request(
    s: AsyncSession, user: User, text: str, anonymous: bool
) -> tuple[PrayerRequestOut, uuid.UUID]:
    await _check_rate(s, user)
    req = await repo.create_request(s, user.id, text.strip(), anonymous)
    await s.commit()
    row = await repo.get_one(s, user.id, req.id)
    assert row is not None
    return _out(row, user.id), req.id


async def delete_request(s: AsyncSession, user: User, rid: uuid.UUID) -> None:
    req = await repo.get_request(s, rid)
    if req is None:
        raise HTTPException(404, "Pedido não encontrado")
    if req.user_id != user.id and user.role != "manager":
        raise HTTPException(403, "Sem permissão para remover este pedido")
    await repo.remove_request(s, req, user.id)
    await s.commit()


async def _require(s: AsyncSession, rid: uuid.UUID) -> PrayerRequest:
    req = await repo.get_request(s, rid)
    if req is None:
        raise HTTPException(404, "Pedido não encontrado")
    return req


async def set_prayed(s: AsyncSession, user: User, rid: uuid.UUID, on: bool) -> PrayedOut:
    await _require(s, rid)
    await repo.set_prayed(s, rid, user.id, on)
    await s.commit()
    count, mine = await repo.prayed_state(s, rid, user.id)
    return PrayedOut(prayed_count=count, i_prayed=mine)


async def list_comments(s: AsyncSession, user: User, rid: uuid.UUID) -> list[PrayerCommentOut]:
    await _require(s, rid)
    return [
        PrayerCommentOut(
            id=c.id,
            text=c.text,
            author_name=name,
            mine=c.user_id == user.id,
            created_at=c.created_at,
        )
        for c, name in await repo.list_comments(s, rid)
    ]


async def add_comment(s: AsyncSession, user: User, rid: uuid.UUID, text: str) -> PrayerCommentOut:
    await _require(s, rid)
    await _check_rate(s, user)
    c = await repo.create_comment(s, rid, user.id, text.strip())
    await s.commit()
    return PrayerCommentOut(
        id=c.id, text=c.text, author_name=user.name, mine=True, created_at=c.created_at
    )


async def delete_comment(s: AsyncSession, user: User, cid: uuid.UUID) -> None:
    c: PrayerComment | None = await repo.get_comment(s, cid)
    if c is None:
        raise HTTPException(404, "Comentário não encontrado")
    if c.user_id != user.id and user.role != "manager":
        raise HTTPException(403, "Sem permissão para remover este comentário")
    await repo.remove_comment(s, c, user.id)
    await s.commit()


async def new_since_last_visit(s: AsyncSession, user: User) -> NewRequestsOut:
    settings = await users_repo.get_settings(s, user.id)
    if settings.community_seen_at is None:
        settings.community_seen_at = datetime.now(UTC)
        await s.commit()
        return NewRequestsOut(count=0, latest_id=None, latest_text=None)
    n, latest = await repo.new_requests_since(s, user.id, settings.community_seen_at)
    return NewRequestsOut(
        count=n,
        latest_id=latest.id if latest else None,
        latest_text=latest.text[:120] if latest else None,
    )


async def mark_seen(s: AsyncSession, user: User) -> None:
    settings = await users_repo.get_settings(s, user.id)
    settings.community_seen_at = datetime.now(UTC)
    await s.commit()


async def notify_new_request(
    request_id: uuid.UUID, author_id: uuid.UUID, sender: PushSender
) -> None:
    """Fan-out de Web Push; roda depois da resposta e nunca derruba a criação do pedido."""
    try:
        async with SessionLocal() as s:
            req = await repo.get_request(s, request_id)
            if req is None:
                return
            body = req.text if len(req.text) <= 90 else req.text[:87] + "…"
            for sub in await repo.push_targets(s, author_id, PUSH_LIMIT):
                try:
                    await sender.send(
                        Subscription(sub.endpoint, sub.p256dh, sub.auth),
                        {"title": "Novo pedido de oração", "body": body, "url": "/mais/comunidade"},
                    )
                except PushGone:
                    await personal_repo.delete_subscription_by_endpoint(s, sub.endpoint)
                except Exception:
                    log.exception("falha ao enviar push de pedido")
            await s.commit()
    except Exception:
        log.exception("falha no fan-out de pedidos")
