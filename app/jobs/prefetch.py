"""Job diário (Render Cron): pré-carrega os próximos dias. Uso: python -m app.jobs.prefetch [dias]"""

import asyncio
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.integrations.registry import build_sources
from app.services.liturgy import LiturgyService


async def run(days: int = 14, start: date | None = None) -> int:
    start = start or datetime.now(ZoneInfo(get_settings().default_tz)).date()
    ok = 0
    sources = build_sources()
    for i in range(days):
        async with SessionLocal() as s:
            day = await LiturgyService(s, sources).get_day(start + timedelta(days=i))
            ok += day.status == "ok"
    return ok


def main() -> None:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 14

    async def _go() -> None:
        n = await run(days)
        print(f"pré-carga: {n}/{days} dias com leituras")
        await engine.dispose()

    asyncio.run(_go())


if __name__ == "__main__":
    main()
