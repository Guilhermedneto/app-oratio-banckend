import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PrayerComment,
    PrayerPrayed,
    PrayerRequest,
    PushSubscription,
    User,
    UserSettings,
)

Row = tuple[PrayerRequest, str, int, int, bool]


def _request_query(me: uuid.UUID):  # type: ignore[no-untyped-def]
    prayed = (
        select(func.count()).where(PrayerPrayed.request_id == PrayerRequest.id).scalar_subquery()
    )
    comments = (
        select(func.count())
        .where(PrayerComment.request_id == PrayerRequest.id, PrayerComment.removed_at.is_(None))
        .scalar_subquery()
    )
    i_prayed = exists().where(
        and_(PrayerPrayed.request_id == PrayerRequest.id, PrayerPrayed.user_id == me)
    )
    return (
        select(PrayerRequest, User.name, prayed, comments, i_prayed)
        .join(User, User.id == PrayerRequest.user_id)
        .where(PrayerRequest.removed_at.is_(None))
    )


async def feed(
    s: AsyncSession, me: uuid.UUID, before: datetime | None, limit: int, mine_only: bool
) -> list[Row]:
    q = _request_query(me)
    if before is not None:
        q = q.where(PrayerRequest.created_at < before)
    if mine_only:
        q = q.where(PrayerRequest.user_id == me)
    q = q.order_by(PrayerRequest.created_at.desc()).limit(limit)
    return [tuple(r) for r in (await s.execute(q)).all()]  # type: ignore[misc]


async def get_one(s: AsyncSession, me: uuid.UUID, rid: uuid.UUID) -> Row | None:
    q = _request_query(me).where(PrayerRequest.id == rid)
    row = (await s.execute(q)).first()
    return tuple(row) if row else None  # type: ignore[return-value]


async def get_request(s: AsyncSession, rid: uuid.UUID) -> PrayerRequest | None:
    row = await s.get(PrayerRequest, rid)
    return row if row is not None and row.removed_at is None else None


async def create_request(
    s: AsyncSession, user_id: uuid.UUID, text: str, anonymous: bool
) -> PrayerRequest:
    row = PrayerRequest(user_id=user_id, text=text, anonymous=anonymous)
    s.add(row)
    await s.flush()
    await s.refresh(row)
    return row


async def remove_request(s: AsyncSession, row: PrayerRequest, by: uuid.UUID) -> None:
    row.removed_at = datetime.now(UTC)
    row.removed_by = by
    await s.flush()


async def count_recent_posts(s: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    reqs = select(func.count()).where(
        PrayerRequest.user_id == user_id, PrayerRequest.created_at >= since
    )
    coms = select(func.count()).where(
        PrayerComment.user_id == user_id, PrayerComment.created_at >= since
    )
    return int((await s.execute(reqs)).scalar_one() + (await s.execute(coms)).scalar_one())


async def set_prayed(s: AsyncSession, rid: uuid.UUID, user_id: uuid.UUID, on: bool) -> None:
    if on:
        stmt = insert(PrayerPrayed).values(request_id=rid, user_id=user_id)
        await s.execute(stmt.on_conflict_do_nothing())
    else:
        await s.execute(
            delete(PrayerPrayed).where(
                PrayerPrayed.request_id == rid, PrayerPrayed.user_id == user_id
            )
        )


async def prayed_state(s: AsyncSession, rid: uuid.UUID, user_id: uuid.UUID) -> tuple[int, bool]:
    n = (await s.execute(select(func.count()).where(PrayerPrayed.request_id == rid))).scalar_one()
    mine = (
        await s.execute(
            select(func.count()).where(
                PrayerPrayed.request_id == rid, PrayerPrayed.user_id == user_id
            )
        )
    ).scalar_one()
    return int(n), bool(mine)


async def list_comments(s: AsyncSession, rid: uuid.UUID) -> list[tuple[PrayerComment, str]]:
    q = (
        select(PrayerComment, User.name)
        .join(User, User.id == PrayerComment.user_id)
        .where(PrayerComment.request_id == rid, PrayerComment.removed_at.is_(None))
        .order_by(PrayerComment.created_at)
    )
    return [(c, n) for c, n in (await s.execute(q)).all()]


async def create_comment(
    s: AsyncSession, rid: uuid.UUID, user_id: uuid.UUID, text: str
) -> PrayerComment:
    row = PrayerComment(request_id=rid, user_id=user_id, text=text)
    s.add(row)
    await s.flush()
    await s.refresh(row)
    return row


async def get_comment(s: AsyncSession, cid: uuid.UUID) -> PrayerComment | None:
    row = await s.get(PrayerComment, cid)
    return row if row is not None and row.removed_at is None else None


async def remove_comment(s: AsyncSession, row: PrayerComment, by: uuid.UUID) -> None:
    row.removed_at = datetime.now(UTC)
    row.removed_by = by
    await s.flush()


async def new_requests_since(
    s: AsyncSession, me: uuid.UUID, since: datetime
) -> tuple[int, PrayerRequest | None]:
    base = (
        PrayerRequest.removed_at.is_(None),
        PrayerRequest.user_id != me,
        PrayerRequest.created_at > since,
    )
    n = (await s.execute(select(func.count()).where(*base))).scalar_one()
    latest = (
        await s.execute(
            select(PrayerRequest).where(*base).order_by(PrayerRequest.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    return int(n), latest


async def push_targets(s: AsyncSession, exclude: uuid.UUID, limit: int) -> list[PushSubscription]:
    q = (
        select(PushSubscription)
        .join(UserSettings, UserSettings.user_id == PushSubscription.user_id)
        .where(UserSettings.notify_community.is_(True), PushSubscription.user_id != exclude)
        .limit(limit)
    )
    return list((await s.execute(q)).scalars())
