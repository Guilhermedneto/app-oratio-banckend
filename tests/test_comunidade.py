import httpx
from conftest import FakePush

REQ = {"text": "Peço orações pela saúde do meu pai.", "anonymous": False}
ZERO = "00000000-0000-0000-0000-000000000000"
Headers = dict[str, str]


async def _post(client: httpx.AsyncClient, headers: Headers, **over: object) -> dict:  # type: ignore[type-arg]
    r = await client.post("/comunidade/pedidos", headers=headers, json={**REQ, **over})
    assert r.status_code == 201, r.text
    return r.json()


async def test_comunidade_exige_login(client: httpx.AsyncClient) -> None:
    for method, path in [
        ("GET", "/comunidade/pedidos"),
        ("POST", "/comunidade/pedidos"),
        ("PUT", f"/comunidade/pedidos/{ZERO}/oracao"),
        ("GET", "/comunidade/novos"),
    ]:
        assert (await client.request(method, path, json=REQ)).status_code == 401, path


async def test_publicar_e_ver_no_feed(
    client: httpx.AsyncClient, auth: Headers, user_b: Headers, push: FakePush
) -> None:
    created = await _post(client, auth)
    assert created["mine"] is True and created["prayed_count"] == 0
    assert created["author_name"] == "Ana"
    feed = (await client.get("/comunidade/pedidos", headers=user_b)).json()
    assert len(feed["items"]) == 1
    item = feed["items"][0]
    assert item["mine"] is False and item["i_prayed"] is False and item["author_name"] == "Ana"


async def test_pedido_anonimo_nao_revela_o_nome(
    client: httpx.AsyncClient, auth: Headers, user_b: Headers, push: FakePush
) -> None:
    await _post(client, auth, anonymous=True)
    item = (await client.get("/comunidade/pedidos", headers=user_b)).json()["items"][0]
    assert item["author_name"] is None


async def test_validacao_de_texto(client: httpx.AsyncClient, auth: Headers, push: FakePush) -> None:
    for text in ("", "x" * 1001):
        r = await client.post("/comunidade/pedidos", headers=auth, json={"text": text})
        assert r.status_code == 422


async def test_orei_e_idempotente_e_pode_desmarcar(
    client: httpx.AsyncClient, auth: Headers, user_b: Headers, push: FakePush
) -> None:
    rid = (await _post(client, auth))["id"]
    url = f"/comunidade/pedidos/{rid}/oracao"
    r1 = await client.put(url, headers=user_b)
    r2 = await client.put(url, headers=user_b)
    assert r1.json() == r2.json() == {"prayed_count": 1, "i_prayed": True}
    mine = (await client.get("/comunidade/pedidos?mine=true", headers=auth)).json()["items"][0]
    assert mine["prayed_count"] == 1 and mine["i_prayed"] is False
    assert (await client.delete(url, headers=user_b)).json() == {
        "prayed_count": 0,
        "i_prayed": False,
    }
    assert (await client.delete(url, headers=user_b)).json()["prayed_count"] == 0  # sem erro
    missing = await client.put(f"/comunidade/pedidos/{ZERO}/oracao", headers=user_b)
    assert missing.status_code == 404


async def test_comentarios(
    client: httpx.AsyncClient, auth: Headers, user_b: Headers, push: FakePush
) -> None:
    rid = (await _post(client, auth))["id"]
    url = f"/comunidade/pedidos/{rid}/comentarios"
    c = await client.post(url, headers=user_b, json={"text": "Rezando por vocês."})
    assert c.status_code == 201 and c.json()["mine"] is True
    assert c.json()["author_name"] == "Beatriz"
    for bad in ("", "y" * 501):
        assert (await client.post(url, headers=user_b, json={"text": bad})).status_code == 422
    lst = (await client.get(url, headers=auth)).json()
    assert [x["text"] for x in lst] == ["Rezando por vocês."] and lst[0]["mine"] is False
    feed = (await client.get("/comunidade/pedidos", headers=auth)).json()
    assert feed["items"][0]["comment_count"] == 1


async def test_permissoes_de_remocao(
    client: httpx.AsyncClient,
    auth: Headers,
    user_b: Headers,
    manager: Headers,
    push: FakePush,
) -> None:
    rid = (await _post(client, auth))["id"]
    cid = (
        await client.post(
            f"/comunidade/pedidos/{rid}/comentarios", headers=user_b, json={"text": "oi"}
        )
    ).json()["id"]
    assert (await client.delete(f"/comunidade/pedidos/{rid}", headers=user_b)).status_code == 403
    assert (await client.delete(f"/comunidade/comentarios/{cid}", headers=auth)).status_code == 403
    # gestor remove o comentário fora de conformidade
    url_c = f"/comunidade/comentarios/{cid}"
    assert (await client.delete(url_c, headers=manager)).status_code == 204
    coments = await client.get(f"/comunidade/pedidos/{rid}/comentarios", headers=auth)
    assert coments.json() == []
    assert (await client.delete(url_c, headers=manager)).status_code == 404
    # gestor remove o pedido: some para todos
    assert (await client.delete(f"/comunidade/pedidos/{rid}", headers=manager)).status_code == 204
    assert (await client.get("/comunidade/pedidos", headers=user_b)).json()["items"] == []
    gone = await client.get(f"/comunidade/pedidos/{rid}/comentarios", headers=user_b)
    assert gone.status_code == 404
    assert (
        await client.put(f"/comunidade/pedidos/{rid}/oracao", headers=user_b)
    ).status_code == 404


async def test_autor_remove_o_proprio_pedido_e_comentario(
    client: httpx.AsyncClient, auth: Headers, user_b: Headers, push: FakePush
) -> None:
    rid = (await _post(client, user_b))["id"]
    r = await client.post(
        f"/comunidade/pedidos/{rid}/comentarios", headers=auth, json={"text": "amém"}
    )
    assert (
        await client.delete(f"/comunidade/comentarios/{r.json()['id']}", headers=auth)
    ).status_code == 204
    assert (await client.delete(f"/comunidade/pedidos/{rid}", headers=user_b)).status_code == 204


async def test_paginacao_do_feed(client: httpx.AsyncClient, auth: Headers, push: FakePush) -> None:
    for i in range(5):
        await _post(client, auth, text=f"pedido {i}")
    p1 = (await client.get("/comunidade/pedidos?limit=2", headers=auth)).json()
    assert [x["text"] for x in p1["items"]] == ["pedido 4", "pedido 3"] and p1["next_before"]
    p2 = await client.get(
        "/comunidade/pedidos", params={"limit": 2, "before": p1["next_before"]}, headers=auth
    )
    assert [x["text"] for x in p2.json()["items"]] == ["pedido 2", "pedido 1"]


async def test_aviso_de_novos_pedidos(
    client: httpx.AsyncClient, auth: Headers, user_b: Headers, push: FakePush
) -> None:
    first = (await client.get("/comunidade/novos", headers=user_b)).json()
    assert first["count"] == 0  # a 1ª consulta só marca o ponto de partida
    await _post(client, auth, text="primeiro")
    await _post(client, auth, text="segundo")
    novos = (await client.get("/comunidade/novos", headers=user_b)).json()
    assert novos["count"] == 2 and novos["latest_text"] == "segundo"
    assert (await client.get("/comunidade/novos", headers=auth)).json()["count"] == 0  # autor não
    assert (await client.post("/comunidade/visto", headers=user_b)).status_code == 204
    assert (await client.get("/comunidade/novos", headers=user_b)).json()["count"] == 0


async def test_push_para_os_outros_usuarios(
    client: httpx.AsyncClient, auth: Headers, user_b: Headers, push: FakePush
) -> None:
    keys = {"p256dh": "k", "auth": "a"}
    for headers, ep in (
        (auth, "https://push.example/autor-0001"),
        (user_b, "https://push.example/b-000001"),
    ):
        await client.post("/push/subscribe", headers=headers, json={"endpoint": ep, "keys": keys})
    await _post(client, auth, text="Peço orações")
    assert [e for e, _ in push.sent] == ["https://push.example/b-000001"]  # não avisa o autor
    assert push.sent[0][1]["title"] == "Novo pedido de oração"

    push.sent.clear()
    r = await client.patch("/me/settings", headers=user_b, json={"notify_community": False})
    assert r.json()["notify_community"] is False
    await _post(client, auth, text="Outro pedido")
    assert push.sent == []  # opção desligada


async def test_assinatura_expirada_nao_derruba_o_pedido(
    client: httpx.AsyncClient, auth: Headers, user_b: Headers, push: FakePush
) -> None:
    ep = "https://push.example/expirada-1"
    keys = {"p256dh": "k", "auth": "a"}
    await client.post("/push/subscribe", headers=user_b, json={"endpoint": ep, "keys": keys})
    push.gone.add(ep)
    assert (await client.post("/comunidade/pedidos", headers=auth, json=REQ)).status_code == 201
    push.gone.clear()
    await _post(client, auth, text="de novo")
    assert push.sent == []  # a assinatura expirada foi removida na primeira tentativa


async def test_limite_de_frequencia(
    client: httpx.AsyncClient,
    auth: Headers,
    push: FakePush,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "community_post_limit", 3)
    for i in range(3):
        await _post(client, auth, text=f"pedido {i}")
    assert (await client.post("/comunidade/pedidos", headers=auth, json=REQ)).status_code == 429
