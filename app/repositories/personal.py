import uuid
from datetime import UTC, date, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Favorite, Intention, NovenaProgress, PushSubscription, RosaryLog

# ---- novenas


async def list_novenas(s: AsyncSession, user_id: uuid.UUID) -> list[NovenaProgress]:
    q = select(NovenaProgress).where(NovenaProgress.user_id == user_id)
    return list((await s.execute(q.order_by(NovenaProgress.started_on.desc()))).scalars())


async def upsert_novena(
    s: AsyncSession,
    user_id: uuid.UUID,
    slug: str,
    started_on: date,
    current_day: int,
    completed_at: datetime | None,
) -> NovenaProgress:
    stmt = insert(NovenaProgress).values(
        user_id=user_id,
        novena_slug=slug,
        started_on=started_on,
        current_day=current_day,
        completed_at=completed_at,
    )
    upsert = stmt.on_conflict_do_update(
        constraint="uq_novena_start",
        set_={"current_day": current_day, "completed_at": completed_at},
    ).returning(NovenaProgress)
    return (await s.execute(upsert)).scalar_one()


# ---- rosário


async def add_rosary(
    s: AsyncSession,
    user_id: uuid.UUID,
    client_id: uuid.UUID,
    d: date,
    mystery_set: str,
    completed: bool,
) -> None:
    stmt = insert(RosaryLog).values(
        user_id=user_id, client_id=client_id, date=d, mystery_set=mystery_set, completed=completed
    )
    await s.execute(stmt.on_conflict_do_nothing(constraint="uq_rosary_client"))


async def rosary_dates(s: AsyncSession, user_id: uuid.UUID) -> list[date]:
    q = (
        select(RosaryLog.date)
        .where(RosaryLog.user_id == user_id, RosaryLog.completed.is_(True))
        .distinct()
        .order_by(RosaryLog.date.desc())
    )
    return list((await s.execute(q)).scalars())


async def rosary_rows(s: AsyncSession, user_id: uuid.UUID) -> list[RosaryLog]:
    q = select(RosaryLog).where(RosaryLog.user_id == user_id).order_by(RosaryLog.date)
    return list((await s.execute(q)).scalars())


# ---- favoritos


async def list_favorites(s: AsyncSession, user_id: uuid.UUID) -> list[Favorite]:
    q = select(Favorite).where(Favorite.user_id == user_id).order_by(Favorite.created_at)
    return list((await s.execute(q)).scalars())


async def add_favorite(s: AsyncSession, user_id: uuid.UUID, item_type: str, slug: str) -> None:
    stmt = insert(Favorite).values(user_id=user_id, item_type=item_type, item_slug=slug)
    await s.execute(stmt.on_conflict_do_nothing())


async def remove_favorite(s: AsyncSession, user_id: uuid.UUID, item_type: str, slug: str) -> None:
    await s.execute(
        delete(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.item_type == item_type,
            Favorite.item_slug == slug,
        )
    )


# ---- intenções


async def list_intentions(s: AsyncSession, user_id: uuid.UUID) -> list[Intention]:
    q = select(Intention).where(Intention.user_id == user_id).order_by(Intention.created_at.desc())
    return list((await s.execute(q)).scalars())


async def get_intention(s: AsyncSession, user_id: uuid.UUID, iid: uuid.UUID) -> Intention | None:
    row = await s.get(Intention, iid)
    return row if row and row.user_id == user_id else None


async def create_intention(
    s: AsyncSession, user_id: uuid.UUID, text: str, iid: uuid.UUID | None = None
) -> Intention:
    if iid is not None:
        existing = await s.get(Intention, iid)
        if existing is not None:
            if existing.user_id != user_id:
                raise ValueError("id em uso")
            return existing
    row = Intention(user_id=user_id, text=text, **({"id": iid} if iid else {}))
    s.add(row)
    await s.flush()
    await s.refresh(row)
    return row


async def delete_intention(s: AsyncSession, row: Intention) -> None:
    await s.delete(row)
    await s.flush()


def now() -> datetime:
    return datetime.now(UTC)


# ---- push


async def upsert_subscription(
    s: AsyncSession, user_id: uuid.UUID, endpoint: str, p256dh: str, auth: str
) -> None:
    stmt = insert(PushSubscription).values(
        user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["endpoint"], set_={"user_id": user_id, "p256dh": p256dh, "auth": auth}
    )
    await s.execute(stmt)


async def delete_subscription(s: AsyncSession, user_id: uuid.UUID, endpoint: str) -> None:
    await s.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint
        )
    )


async def delete_subscription_by_endpoint(s: AsyncSession, endpoint: str) -> None:
    await s.execute(delete(PushSubscription).where(PushSubscription.endpoint == endpoint))


async def list_subscriptions(s: AsyncSession, user_id: uuid.UUID) -> list[PushSubscription]:
    q = select(PushSubscription).where(PushSubscription.user_id == user_id)
    return list((await s.execute(q)).scalars())
