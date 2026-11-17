import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.base import LiturgySource, SourceDay, SourceError
from app.repositories import liturgy as repo
from app.schemas.api import LiturgyDayOut, PrayerOut, ReadingOut
from app.services.calendar import SEASON_LABELS, LiturgicalCalendar, get_calendar

log = logging.getLogger("oratio.liturgy")
RETRY_AFTER = timedelta(minutes=15)
_locks: dict[date, asyncio.Lock] = {}


class LiturgyService:
    def __init__(
        self,
        session: AsyncSession,
        sources: list[LiturgySource],
        calendar: LiturgicalCalendar | None = None,
    ) -> None:
        self.s = session
        self.sources = sources
        self.calendar = calendar or get_calendar()

    async def get_day(self, d: date, allow_fetch: bool = True) -> LiturgyDayOut:
        """Calcula e persiste o dia; só consulta fontes se ainda não houver leituras no banco."""
        row, readings = await repo.get_day_with_readings(self.s, d)
        info = self.calendar.day(d)  # cálculo local e barato; mantém o banco em dia após ajustes
        if row is None or (row.season, row.week, row.color, row.celebration, row.rank) != (
            info.season,
            info.week,
            info.color,
            info.celebration,
            info.rank,
        ):
            await repo.upsert_day(self.s, info)
            await self.s.commit()
            row, readings = await repo.get_day_with_readings(self.s, d)
        missing_prayers = bool(readings) and row is not None and row.prayers is None
        if (
            (not _has_text(readings) or missing_prayers)
            and allow_fetch
            and self.sources
            and self._can_retry(row.fetched_at if row else None)
        ):
            lock = _locks.setdefault(d, asyncio.Lock())
            async with lock:
                self.s.expire_all()
                readings = await repo.readings_for(self.s, d)
                row = await repo.get_day(self.s, d)
                missing_prayers = bool(readings) and row is not None and row.prayers is None
                if (not _has_text(readings) or missing_prayers) and self._can_retry(
                    row.fetched_at if row else None
                ):
                    await self._collect(d)
                    self.s.expire_all()
                    row = await repo.get_day(self.s, d)
                    readings = await repo.readings_for(self.s, d)
        assert row is not None
        return LiturgyDayOut(
            date=row.date,
            season=row.season,
            season_label=SEASON_LABELS[row.season],
            week=row.week,
            color=row.color,
            celebration=row.celebration,
            rank=row.rank,
            cycle_sunday=row.cycle_sunday,
            cycle_weekday=row.cycle_weekday,
            status="ok" if readings else "partial",
            source=readings[0].source if readings else None,
            credits=_credits(readings[0].source) if readings else None,
            readings=[ReadingOut.model_validate(r) for r in readings],
            prayers=[PrayerOut(**p) for p in (row.prayers or [])],
        )

    @staticmethod
    def _can_retry(fetched_at: datetime | None) -> bool:
        return fetched_at is None or datetime.now(UTC) - fetched_at > RETRY_AFTER

    async def _collect(self, d: date) -> None:
        # Plano B: se nenhuma fonte trouxer texto, guarda só as referências do dia.
        refs_only: SourceDay | None = None
        for src in self.sources:
            try:
                day = await src.fetch(d)
            except SourceError as exc:
                log.warning("fonte %s falhou para %s: %s", src.name, d, exc)
                continue
            except Exception:  # fonte externa nunca deve derrubar a requisição
                log.exception("erro inesperado na fonte %s", src.name)
                continue
            if any(r.text for r in day.readings):
                await self._store(d, day)
                return
            if day.readings and refs_only is None:
                refs_only = day
        if refs_only is not None and not _has_text(await repo.readings_for(self.s, d)):
            await self._store(d, refs_only)
            return
        await repo.mark_fetch_attempt(self.s, d)
        await self.s.commit()

    async def _store(self, d: date, day: SourceDay) -> None:
        items = [(r.kind, r.reference, r.title, r.text) for r in day.readings]
        prayers = [{"kind": p.kind, "title": p.title, "text": p.text} for p in day.prayers]
        await repo.replace_readings(self.s, d, day.source, items, prayers)
        await self.s.commit()

    async def week(self, start: date, days: int = 7) -> list[LiturgyDayOut]:
        return [await self.get_day(start + timedelta(days=i)) for i in range(days)]


def _has_text(readings: list) -> bool:  # type: ignore[type-arg]
    return any(r.text for r in readings)


def _credits(source: str) -> str:
    if source == "amostra":
        return "Texto de amostra para desenvolvimento"
    names = {
        "cnbb": "Edições CNBB",
        "cancaonova": "Canção Nova",
        "railway": "liturgia.up.railway.app",
    }
    return f"Texto: CNBB, via {names.get(source, source)}"
