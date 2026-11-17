"""Job de lembretes (Render Cron, a cada 15 min). Uso: python -m app.jobs.send_push"""

import asyncio

from app.core.db import SessionLocal, engine
from app.integrations.webpush import WebPushSender
from app.services.push import send_due_reminders


def main() -> None:
    async def _go() -> None:
        async with SessionLocal() as s:
            n = await send_due_reminders(s, WebPushSender())
        print(f"lembretes enviados: {n}")
        await engine.dispose()

    asyncio.run(_go())


if __name__ == "__main__":
    main()
