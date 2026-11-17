import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserSettings
from app.repositories import personal as repo
from app.repositories import users as users_repo
from app.schemas.api import IntentionPatch, NovenaIn, SettingsPatch


def compute_streak(dates_desc: list[date], today: date) -> int:
    """Dias consecutivos terminando hoje ou ontem (hoje ainda pode ser rezado)."""
    if not dates_desc:
        return 0
    days = set(dates_desc)
    cursor = today if today in days else today - timedelta(days=1)
    n = 0
    while cursor in days:
        n += 1
        cursor -= timedelta(days=1)
    return n


def _today(tz: str) -> date:
    try:
        return datetime.now(ZoneInfo(tz)).date()
    except ZoneInfoNotFoundError:
        return datetime.now(UTC).date()


async def streak_for(s: AsyncSession, user_id: uuid.UUID) -> int:
    settings = await users_repo.get_settings(s, user_id)
    return compute_streak(await repo.rosary_dates(s, user_id), _today(settings.timezone))


async def patch_settings(s: AsyncSession, user_id: uuid.UUID, patch: SettingsPatch) -> UserSettings:
    row = await users_repo.get_settings(s, user_id)
    data = patch.model_dump(exclude_unset=True)
    if "timezone" in data and data["timezone"]:
        try:
            ZoneInfo(data["timezone"])
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise HTTPException(422, "Fuso horário inválido") from exc
        row.timezone = data["timezone"]
    if data.get("theme") is not None:
        row.theme = data["theme"]
    if data.get("font_scale") is not None:
        row.font_scale = data["font_scale"]
    if data.get("rite_prefs") is not None:
        row.rite_prefs = data["rite_prefs"]
    if data.get("notify_community") is not None:
        row.notify_community = data["notify_community"]
    if data.get("clear_notify_time"):
        row.notify_time = None
    elif data.get("notify_time") is not None:
        row.notify_time = data["notify_time"].replace(second=0, microsecond=0, tzinfo=None)
    await s.commit()
    return row


async def put_novena(s: AsyncSession, user_id: uuid.UUID, body: NovenaIn):  # type: ignore[no-untyped-def]
    completed_at = datetime.now(UTC) if body.completed else None
    row = await repo.upsert_novena(
        s, user_id, body.novena_slug, body.started_on, body.current_day, completed_at
    )
    await s.commit()
    return row


async def add_rosary(s: AsyncSession, user_id: uuid.UUID, body: Any) -> int:
    await repo.add_rosary(s, user_id, body.client_id, body.date, body.mystery_set, body.completed)
    await s.commit()
    return await streak_for(s, user_id)


async def patch_intention(s: AsyncSession, user_id: uuid.UUID, iid: uuid.UUID, p: IntentionPatch):  # type: ignore[no-untyped-def]
    row = await repo.get_intention(s, user_id, iid)
    if row is None:
        raise HTTPException(404, "Intenção não encontrada")
    if p.text is not None:
        row.text = p.text
    if p.answered is not None:
        row.answered_at = repo.now() if p.answered else None
    await s.commit()
    return row


async def export_data(s: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    user = await users_repo.get_by_id(s, user_id)
    settings = await users_repo.get_settings(s, user_id)
    assert user is not None
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "user": {"id": str(user.id), "email": user.email, "name": user.name},
        "settings": {
            "theme": settings.theme,
            "font_scale": settings.font_scale,
            "notify_time": settings.notify_time.isoformat() if settings.notify_time else None,
            "timezone": settings.timezone,
            "rite_prefs": settings.rite_prefs,
        },
        "novenas": [
            {
                "novena_slug": n.novena_slug,
                "started_on": n.started_on.isoformat(),
                "current_day": n.current_day,
                "completed_at": n.completed_at.isoformat() if n.completed_at else None,
            }
            for n in await repo.list_novenas(s, user_id)
        ],
        "rosary": [
            {"date": r.date.isoformat(), "mystery_set": r.mystery_set, "completed": r.completed}
            for r in await repo.rosary_rows(s, user_id)
        ],
        "favorites": [
            {"item_type": f.item_type, "item_slug": f.item_slug}
            for f in await repo.list_favorites(s, user_id)
        ],
        "intentions": [
            {
                "text": i.text,
                "created_at": i.created_at.isoformat(),
                "answered_at": i.answered_at.isoformat() if i.answered_at else None,
            }
            for i in await repo.list_intentions(s, user_id)
        ],
    }


async def delete_account(s: AsyncSession, user_id: uuid.UUID) -> None:
    await users_repo.revoke_all_refresh(s, user_id)
    await users_repo.delete_user(s, user_id)
    await s.commit()
