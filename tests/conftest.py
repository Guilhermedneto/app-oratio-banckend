import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://oratio:oratio@localhost:5433/oratio_test"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["NULL_POOL"] = "true"
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-00"
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["MANAGER_EMAILS"] = "gestor@x.com"
os.environ["COMMUNITY_POST_LIMIT"] = "1000"

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.integrations.base import PrayerData, ReadingData, SourceDay, SourceError  # noqa: E402
from app.main import app  # noqa: E402
from app.routers.deps import get_push_sender, get_sources  # noqa: E402


class FakeSource:
    def __init__(self, name: str = "fake", fail: bool = False) -> None:
        self.name = name
        self.fail = fail
        self.calls = 0

    async def fetch(self, d):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.fail:
            raise SourceError("fora do ar")
        return SourceDay(
            self.name,
            [
                ReadingData("primeira", "Is 1,1", "Primeira", "texto 1"),
                ReadingData("evangelho", "Jo 1,1", "Evangelho", "texto ev"),
            ],
            [
                PrayerData("antifona_entrada", "Antífona de entrada", "entrada"),
                PrayerData("coleta", "Oração do dia (coleta)", "coleta"),
            ],
        )


@pytest.fixture(scope="session", autouse=True)
def migrated() -> None:
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(autouse=True)
async def clean(migrated: None):  # type: ignore[no-untyped-def]
    async with engine.begin() as c:
        await c.execute(
            text(
                "TRUNCATE users, liturgical_days, readings, refresh_tokens, user_settings, "
                "novena_progress, rosary_log, favorites, intentions, push_subscriptions, categories CASCADE"
            )
        )
    yield


class FakePush:
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict[str, str]]] = []
        self.gone: set[str] = set()

    async def send(self, sub, payload):  # type: ignore[no-untyped-def]
        from app.integrations.webpush import PushGone

        if sub.endpoint in self.gone:
            raise PushGone
        self.sent.append((sub.endpoint, payload))


@pytest.fixture
def push() -> FakePush:
    p = FakePush()
    app.dependency_overrides[get_push_sender] = lambda: p
    return p


@pytest.fixture
def source() -> FakeSource:
    src = FakeSource()
    app.dependency_overrides[get_sources] = lambda: [src]
    yield src
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(source: FakeSource):  # type: ignore[no-untyped-def]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth(client: httpx.AsyncClient) -> dict[str, str]:
    r = await client.post(
        "/auth/register", json={"email": "a@b.com", "password": "senha-forte-1", "name": "Ana"}
    )
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _register(client: httpx.AsyncClient, email: str, name: str) -> dict[str, str]:
    r = await client.post(
        "/auth/register", json={"email": email, "password": "senha-forte-1", "name": name}
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest_asyncio.fixture
async def manager(client: httpx.AsyncClient) -> dict[str, str]:
    return await _register(client, "gestor@x.com", "Gestor")


@pytest_asyncio.fixture
async def user_b(client: httpx.AsyncClient) -> dict[str, str]:
    return await _register(client, "b@x.com", "Beatriz")
