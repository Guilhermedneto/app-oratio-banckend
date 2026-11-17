import httpx

from app.core import ratelimit
from app.core.config import get_settings
from app.integrations import google as google_integration

CREDS = {"email": "x@y.com", "password": "senha-forte-1", "name": "X"}


async def test_register_login_me(client: httpx.AsyncClient) -> None:
    r = await client.post("/auth/register", json=CREDS)
    assert r.status_code == 201
    assert "oratio_refresh" in r.cookies
    sc = r.headers["set-cookie"].lower()
    assert "httponly" in sc and "samesite=lax" in sc
    r = await client.post("/auth/login", json={"email": "X@Y.com", "password": CREDS["password"]})
    assert r.status_code == 200
    me = await client.get("/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "x@y.com"
    assert me.json()["settings"]["theme"] == "auto"


async def test_duplicate_email_409(client: httpx.AsyncClient) -> None:
    await client.post("/auth/register", json=CREDS)
    r = await client.post("/auth/register", json=CREDS)
    assert r.status_code == 409


async def test_bad_credentials_same_message(client: httpx.AsyncClient) -> None:
    await client.post("/auth/register", json=CREDS)
    wrong_pw = await client.post(
        "/auth/login", json={"email": CREDS["email"], "password": "errada-123"}
    )
    unknown = await client.post("/auth/login", json={"email": "no@y.com", "password": "errada-123"})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


async def test_weak_password_422(client: httpx.AsyncClient) -> None:
    r = await client.post("/auth/register", json={**CREDS, "password": "curta"})
    assert r.status_code == 422


async def test_protected_routes_need_token(client: httpx.AsyncClient) -> None:
    for method, path in [
        ("GET", "/me"),
        ("PATCH", "/me/settings"),
        ("GET", "/me/novenas"),
        ("PUT", "/me/novenas"),
        ("POST", "/me/rosario"),
        ("GET", "/me/favoritos"),
        ("POST", "/me/favoritos"),
        ("GET", "/me/intencoes"),
        ("POST", "/me/intencoes"),
        ("POST", "/push/subscribe"),
        ("DELETE", "/push/subscribe?endpoint=x"),
        ("GET", "/me/export"),
        ("DELETE", "/me"),
    ]:
        r = await client.request(method, path, json={})
        assert r.status_code == 401, (method, path)
    bad = await client.get("/me", headers={"Authorization": "Bearer lixo"})
    assert bad.status_code == 401


async def test_refresh_rotates_and_reuse_kills_session(client: httpx.AsyncClient) -> None:
    r = await client.post("/auth/register", json=CREDS)
    old = r.cookies["oratio_refresh"]
    r2 = await client.post("/auth/refresh")
    assert r2.status_code == 200
    new = r2.cookies["oratio_refresh"]
    assert new != old
    # reutilizar o token antigo: 401 e derruba a família inteira
    client.cookies.clear()
    client.cookies.set("oratio_refresh", old)
    assert (await client.post("/auth/refresh")).status_code == 401
    client.cookies.clear()
    client.cookies.set("oratio_refresh", new)
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_refresh_without_cookie_401(client: httpx.AsyncClient) -> None:
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_logout_revokes(client: httpx.AsyncClient) -> None:
    await client.post("/auth/register", json=CREDS)
    token = client.cookies["oratio_refresh"]
    assert (await client.post("/auth/logout")).status_code == 204
    client.cookies.set("oratio_refresh", token)
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_rate_limit(client: httpx.AsyncClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    s = get_settings()
    monkeypatch.setattr(s, "rate_limit_enabled", True)
    monkeypatch.setattr(s, "rate_limit_max", 3)
    ratelimit.reset()
    codes = [
        (await client.post("/auth/login", json={"email": "a@b.com", "password": "x"})).status_code
        for _ in range(5)
    ]
    ratelimit.reset()
    assert codes[:3] == [401, 401, 401]
    assert codes[3:] == [429, 429]


async def test_google_not_configured(client: httpx.AsyncClient) -> None:
    r = await client.post("/auth/google", json={"id_token": "x" * 20})
    assert r.status_code == 503
    assert "Google" in r.json()["detail"]


async def test_google_login_creates_and_links(client: httpx.AsyncClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(get_settings(), "google_client_id", "cid")

    async def fake(token: str, client_id: str):  # type: ignore[no-untyped-def]
        if token.startswith("bad"):
            raise ValueError("inválido")
        return {"sub": "g-123", "email": "G@x.com", "name": "Gui", "email_verified": True}

    monkeypatch.setattr(google_integration, "verify_google_token", fake)
    ok = await client.post("/auth/google", json={"id_token": "good-token-000"})
    assert ok.status_code == 200 and ok.json()["user"]["email"] == "g@x.com"
    again = await client.post("/auth/google", json={"id_token": "good-token-000"})
    assert again.json()["user"]["id"] == ok.json()["user"]["id"]
    bad = await client.post("/auth/google", json={"id_token": "bad-token-0000"})
    assert bad.status_code == 401


async def test_security_headers(client: httpx.AsyncClient) -> None:
    r = await client.get("/health")
    assert r.json()["status"] == "ok" and r.json()["db"] == "ok"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
