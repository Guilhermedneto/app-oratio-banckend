import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app.integrations.webpush import PushGone, Subscription
from app.services.personal import compute_streak
from app.services.push import is_due, send_due_reminders


async def test_settings_patch(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    r = await client.patch(
        "/me/settings",
        headers=auth,
        json={
            "theme": "sepia",
            "font_scale": 1.2,
            "notify_time": "07:30:00",
            "timezone": "America/Sao_Paulo",
        },
    )
    assert r.status_code == 200
    assert r.json()["theme"] == "sepia" and r.json()["notify_time"] == "07:30:00"
    assert (
        await client.patch("/me/settings", headers=auth, json={"theme": "neon"})
    ).status_code == 422
    assert (
        await client.patch("/me/settings", headers=auth, json={"font_scale": 5})
    ).status_code == 422
    assert (
        await client.patch("/me/settings", headers=auth, json={"timezone": "Marte/Olimpo"})
    ).status_code == 422
    r = await client.patch("/me/settings", headers=auth, json={"clear_notify_time": True})
    assert r.json()["notify_time"] is None


async def test_novena_put_is_idempotent(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    body = {"novena_slug": "sao-jose", "started_on": "2026-03-10", "current_day": 3}
    assert (await client.put("/me/novenas", headers=auth, json=body)).status_code == 200
    await client.put("/me/novenas", headers=auth, json=body)
    r = await client.put(
        "/me/novenas", headers=auth, json={**body, "current_day": 9, "completed": True}
    )
    assert r.json()["completed_at"] is not None
    lst = (await client.get("/me/novenas", headers=auth)).json()
    assert len(lst) == 1 and lst[0]["current_day"] == 9
    bad = await client.put("/me/novenas", headers=auth, json={**body, "current_day": 10})
    assert bad.status_code == 422


async def test_rosary_idempotent_and_streak(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    ids = [str(uuid.uuid4()) for _ in range(4)]
    for i, d in enumerate([today, today - timedelta(days=1), today - timedelta(days=2)]):
        r = await client.post(
            "/me/rosario",
            headers=auth,
            json={"client_id": ids[i], "date": d.isoformat(), "mystery_set": "gozosos"},
        )
        assert r.status_code == 201
    # mesmo client_id reenviado (fila offline) não duplica
    again = await client.post(
        "/me/rosario",
        headers=auth,
        json={"client_id": ids[0], "date": today.isoformat(), "mystery_set": "gozosos"},
    )
    assert again.json()["streak"] == 3
    # segundo terço no mesmo dia: conta uma vez para a sequência
    two = await client.post(
        "/me/rosario",
        headers=auth,
        json={"client_id": ids[3], "date": today.isoformat(), "mystery_set": "gloriosos"},
    )
    assert two.json()["streak"] == 3
    assert (await client.get("/me", headers=auth)).json()["rosary_streak"] == 3
    exp = (await client.get("/me/export", headers=auth)).json()
    assert len(exp["rosary"]) == 4


def test_compute_streak() -> None:
    t = date(2026, 5, 10)
    assert compute_streak([], t) == 0
    assert compute_streak([t, t - timedelta(days=1)], t) == 2
    assert compute_streak([t - timedelta(days=1)], t) == 1  # hoje ainda pode ser rezado
    assert compute_streak([t - timedelta(days=2)], t) == 0


async def test_favorites(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    body = {"item_type": "oracao", "item_slug": "ave-maria"}
    assert (await client.post("/me/favoritos", headers=auth, json=body)).status_code == 201
    r = await client.post("/me/favoritos", headers=auth, json=body)
    assert len(r.json()) == 1
    assert (
        await client.post("/me/favoritos", headers=auth, json={"item_type": "x", "item_slug": "a"})
    ).status_code == 422
    assert (await client.delete("/me/favoritos/oracao/ave-maria", headers=auth)).status_code == 204
    assert (await client.get("/me/favoritos", headers=auth)).json() == []


async def test_intentions_crud(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    r = await client.post("/me/intencoes", headers=auth, json={"text": "Pela minha família"})
    iid = r.json()["id"]
    assert (await client.post("/me/intencoes", headers=auth, json={"text": ""})).status_code == 422
    r = await client.patch(
        f"/me/intencoes/{iid}", headers=auth, json={"answered": True, "text": "Família"}
    )
    assert r.json()["answered_at"] and r.json()["text"] == "Família"
    r = await client.patch(f"/me/intencoes/{iid}", headers=auth, json={"answered": False})
    assert r.json()["answered_at"] is None
    assert (await client.delete(f"/me/intencoes/{iid}", headers=auth)).status_code == 204
    assert (await client.delete(f"/me/intencoes/{iid}", headers=auth)).status_code == 404


async def test_intentions_isolated_between_users(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    iid = (await client.post("/me/intencoes", headers=auth, json={"text": "minha"})).json()["id"]
    other = await client.post(
        "/auth/register", json={"email": "o@o.com", "password": "senha-forte-2", "name": "O"}
    )
    h2 = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert (
        await client.patch(f"/me/intencoes/{iid}", headers=h2, json={"answered": True})
    ).status_code == 404
    assert (await client.get("/me/intencoes", headers=h2)).json() == []


async def test_push_subscribe_and_unsubscribe(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    body = {"endpoint": "https://push.example/abc123456", "keys": {"p256dh": "k", "auth": "a"}}
    assert (await client.post("/push/subscribe", headers=auth, json=body)).status_code == 201
    assert (await client.post("/push/subscribe", headers=auth, json=body)).status_code == 201
    r = await client.delete("/push/subscribe", headers=auth, params={"endpoint": body["endpoint"]})
    assert r.status_code == 204


class FakeSender:
    def __init__(self, gone: bool = False) -> None:
        self.sent: list[Subscription] = []
        self.gone = gone

    async def send(self, sub: Subscription, payload: dict[str, str]) -> None:
        if self.gone:
            raise PushGone
        self.sent.append(sub)


def test_is_due_respects_timezone() -> None:
    now = datetime(2026, 5, 10, 10, 5, tzinfo=UTC)  # 07:05 em São Paulo
    assert is_due(7 * 60, "America/Sao_Paulo", now)
    assert not is_due(8 * 60, "America/Sao_Paulo", now)
    assert not is_due(7 * 60, "Europe/Lisbon", now)


async def test_send_due_reminders(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    from app.core.db import SessionLocal

    await client.patch("/me/settings", headers=auth, json={"notify_time": "07:00:00"})
    await client.post(
        "/push/subscribe",
        headers=auth,
        json={"endpoint": "https://push.example/endpoint-1", "keys": {"p256dh": "k", "auth": "a"}},
    )
    now = datetime(2026, 5, 10, 10, 3, tzinfo=UTC)
    async with SessionLocal() as s:
        sender = FakeSender()
        assert await send_due_reminders(s, sender, now) == 1
        assert await send_due_reminders(s, sender, now.replace(hour=15)) == 0
        gone = FakeSender(gone=True)
        assert await send_due_reminders(s, gone, now) == 0
    async with SessionLocal() as s:
        assert await send_due_reminders(s, FakeSender(), now) == 0  # assinatura removida


async def test_export_and_delete_account(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    await client.post("/me/intencoes", headers=auth, json={"text": "x"})
    exp = (await client.get("/me/export", headers=auth)).json()
    assert exp["user"]["email"] == "a@b.com" and len(exp["intentions"]) == 1
    assert (await client.delete("/me", headers=auth)).status_code == 204
    assert (await client.get("/me", headers=auth)).status_code == 401
    assert (
        await client.post("/auth/login", json={"email": "a@b.com", "password": "senha-forte-1"})
    ).status_code == 401
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_prefetch_job(source) -> None:  # type: ignore[no-untyped-def]
    from app.integrations import registry
    from app.jobs import prefetch

    registry.build_sources = lambda names=None: [source]  # type: ignore[assignment]
    prefetch.build_sources = registry.build_sources  # type: ignore[assignment]
    assert await prefetch.run(days=3, start=date(2026, 6, 1)) == 3
    assert source.calls == 3
    assert await prefetch.run(days=3, start=date(2026, 6, 1)) == 3
    assert source.calls == 3  # já no banco: nenhuma coleta nova


async def test_intention_create_with_client_id_is_idempotent(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    iid = str(uuid.uuid4())
    for _ in range(2):
        r = await client.post("/me/intencoes", headers=auth, json={"id": iid, "text": "offline"})
        assert r.status_code == 201 and r.json()["id"] == iid
    assert len((await client.get("/me/intencoes", headers=auth)).json()) == 1
    other = await client.post(
        "/auth/register", json={"email": "z@z.com", "password": "senha-forte-3", "name": "Z"}
    )
    h2 = {"Authorization": f"Bearer {other.json()['access_token']}"}
    r = await client.post("/me/intencoes", headers=h2, json={"id": iid, "text": "roubo"})
    assert r.status_code == 409
