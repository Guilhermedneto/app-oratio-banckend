from datetime import UTC, date, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LiturgicalDay, Reading
from app.services.calendar import LiturgicalInfo


async def get_day(s: AsyncSession, d: date) -> LiturgicalDay | None:
    return await s.get(LiturgicalDay, d)


async def upsert_day(s: AsyncSession, info: LiturgicalInfo) -> None:
    values = {
        "date": info.date,
        "season": info.season,
        "week": info.week,
        "color": info.color,
        "celebration": info.celebration,
        "rank": info.rank,
        "cycle_sunday": info.cycle_sunday,
        "cycle_weekday": info.cycle_weekday,
    }
    stmt = insert(LiturgicalDay).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["date"], set_={k: v for k, v in values.items() if k != "date"}
    )
    await s.execute(stmt)


async def get_day_with_readings(
    s: AsyncSession, d: date
) -> tuple[LiturgicalDay | None, list[Reading]]:
    """Uma única ida ao banco (caminho quente de /liturgia/hoje)."""
    q = (
        select(LiturgicalDay, Reading)
        .outerjoin(Reading, Reading.date == LiturgicalDay.date)
        .where(LiturgicalDay.date == d)
        .order_by(Reading.id)
        .execution_options(populate_existing=True)
    )
    rows = (await s.execute(q)).all()
    if not rows:
        return None, []
    return rows[0][0], [r for _, r in rows if r is not None]


async def readings_for(s: AsyncSession, d: date) -> list[Reading]:
    q = select(Reading).where(Reading.date == d).order_by(Reading.id)
    return list((await s.execute(q)).scalars())


async def replace_readings(
    s: AsyncSession,
    d: date,
    source: str,
    items: list[tuple[str, str, str, str]],
    prayers: list[dict[str, str]] | None = None,
) -> None:
    await s.execute(delete(Reading).where(Reading.date == d))
    for kind, ref, title, text in items:
        s.add(Reading(date=d, kind=kind, reference=ref, title=title, text=text, source=source))
    day = await s.get(LiturgicalDay, d)
    if day is not None:
        day.source = source
        day.fetched_at = datetime.now(UTC)
        day.prayers = prayers if prayers is not None else []
    await s.flush()


async def mark_fetch_attempt(s: AsyncSession, d: date) -> None:
    day = await s.get(LiturgicalDay, d)
    if day is not None:
        day.fetched_at = datetime.now(UTC)
        await s.flush()
