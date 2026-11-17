import httpx

BODY = {
    "kind": "oracao",
    "title": "Oração de cura",
    "category": "cura",
    "body": "Senhor, **cura** os que sofrem.\n\n<script>alert(1)</script>",
    "author": "Autor Exemplo",
    "origin": "Livro de orações, 1950",
    "source_url": "https://exemplo.org/livro",
}
ZERO = "00000000-0000-0000-0000-000000000000"


async def test_papel_do_gestor_vem_do_ambiente(
    client: httpx.AsyncClient, manager: dict[str, str], auth: dict[str, str]
) -> None:
    assert (await client.get("/me", headers=manager)).json()["user"]["role"] == "manager"
    assert (await client.get("/me", headers=auth)).json()["user"]["role"] == "user"
    login = await client.post(
        "/auth/login", json={"email": "gestor@x.com", "password": "senha-forte-1"}
    )
    assert login.json()["user"]["role"] == "manager"


async def test_rotas_do_gestor_exigem_papel(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    for method, path in [
        ("GET", "/gestor/conteudos"),
        ("POST", "/gestor/conteudos"),
        ("PUT", f"/gestor/conteudos/{ZERO}"),
        ("DELETE", f"/gestor/conteudos/{ZERO}"),
        ("POST", "/gestor/categorias"),
        ("DELETE", f"/gestor/categorias/{ZERO}"),
    ]:
        assert (await client.request(method, path, json=BODY)).status_code == 401, path
        r = await client.request(method, path, json=BODY, headers=auth)
        assert r.status_code == 403, path


async def test_crud_de_conteudo_e_visibilidade_publica(
    client: httpx.AsyncClient, manager: dict[str, str]
) -> None:
    r = await client.post("/gestor/conteudos", headers=manager, json=BODY)
    assert r.status_code == 201
    item = r.json()
    assert item["slug"] == "oracao-de-cura" and item["author"] == "Autor Exemplo"

    pub = await client.get("/conteudos")  # público, sem login
    assert [c["slug"] for c in pub.json()] == ["oracao-de-cura"]
    etag = pub.headers["etag"]
    assert (await client.get("/conteudos", headers={"If-None-Match": etag})).status_code == 304
    # guardado como texto; o front nunca interpreta HTML
    assert "<script>" in pub.json()[0]["body"]

    upd = await client.put(
        f"/gestor/conteudos/{item['id']}",
        headers=manager,
        json={**BODY, "title": "Outro título", "published": False},
    )
    assert upd.status_code == 200 and upd.json()["title"] == "Outro título"
    assert (await client.get("/conteudos")).json() == []  # oculto
    assert len((await client.get("/gestor/conteudos", headers=manager)).json()) == 1

    url = f"/gestor/conteudos/{item['id']}"
    assert (await client.delete(url, headers=manager)).status_code == 204
    assert (await client.delete(url, headers=manager)).status_code == 404


async def test_slug_unico_para_titulos_iguais(
    client: httpx.AsyncClient, manager: dict[str, str]
) -> None:
    a = (await client.post("/gestor/conteudos", headers=manager, json=BODY)).json()
    b = (await client.post("/gestor/conteudos", headers=manager, json=BODY)).json()
    assert a["slug"] != b["slug"] and b["slug"].startswith("oracao-de-cura-")


async def test_validacao_do_conteudo(client: httpx.AsyncClient, manager: dict[str, str]) -> None:
    for bad in (
        {**BODY, "title": ""},
        {**BODY, "body": ""},
        {**BODY, "kind": "musica"},
        {**BODY, "category": "Com Espaço"},
    ):
        r = await client.post("/gestor/conteudos", headers=manager, json=bad)
        assert r.status_code == 422


async def test_categorias_criar_duplicar_e_excluir(
    client: httpx.AsyncClient, manager: dict[str, str]
) -> None:
    r = await client.post("/gestor/categorias", headers=manager, json={"name": "Orações de Cura"})
    assert r.status_code == 201 and r.json()["slug"] == "oracoes-de-cura"
    dup = await client.post("/gestor/categorias", headers=manager, json={"name": "orações de cura"})
    assert dup.status_code == 409
    assert [c["slug"] for c in (await client.get("/categorias")).json()] == ["oracoes-de-cura"]

    created = await client.post(
        "/gestor/conteudos", headers=manager, json={**BODY, "category": "oracoes-de-cura"}
    )
    from app.core.db import SessionLocal
    from app.repositories import content as repo

    async with SessionLocal() as s:
        cat_id = (await repo.list_categories(s))[0].id
    url = f"/gestor/categorias/{cat_id}"
    assert (await client.delete(url, headers=manager)).status_code == 409  # em uso
    await client.delete(f"/gestor/conteudos/{created.json()['id']}", headers=manager)
    assert (await client.delete(url, headers=manager)).status_code == 204
