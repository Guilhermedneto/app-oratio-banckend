import uuid

import httpx

Headers = dict[str, str]


def _novena_data(n: int = 9) -> dict:  # type: ignore[type-arg]
    return {
        "days": [{"title": f"Dia {i}", "text": f"Texto do dia {i}"} for i in range(1, n + 1)],
        "final_prayer": "Oração final",
    }


def _misterios_data(n: int = 5) -> dict:  # type: ignore[type-arg]
    return {
        "mysteries": [
            {"title": f"Mistério {i}", "fruit": "Fé", "meditation": "Medite"}
            for i in range(1, n + 1)
        ],
        "weekdays": [1, 6],
    }


def _body(kind: str, **over: object) -> dict:  # type: ignore[type-arg]
    base = {"kind": kind, "title": "Título", "category": "cat", "body": "Descrição"}
    return {**base, **over}


async def test_novena_exige_nove_dias(client: httpx.AsyncClient, manager: Headers) -> None:
    ok = await client.post(
        "/gestor/conteudos", headers=manager, json=_body("novena", data=_novena_data())
    )
    assert ok.status_code == 201
    assert (
        len(ok.json()["data"]["days"]) == 9 and ok.json()["data"]["final_prayer"] == "Oração final"
    )
    for bad in (_novena_data(8), _novena_data(10), None, {"days": "x"}):
        r = await client.post("/gestor/conteudos", headers=manager, json=_body("novena", data=bad))
        assert r.status_code == 422, bad
    sem_texto = _novena_data()
    sem_texto["days"][3]["text"] = "  "
    r = await client.post(
        "/gestor/conteudos", headers=manager, json=_body("novena", data=sem_texto)
    )
    assert r.status_code == 422 and "Dia 4" in r.json()["detail"]


async def test_misterios_exigem_cinco_e_dias_validos(
    client: httpx.AsyncClient, manager: Headers
) -> None:
    ok = await client.post(
        "/gestor/conteudos", headers=manager, json=_body("misterio", data=_misterios_data())
    )
    assert ok.status_code == 201 and ok.json()["data"]["weekdays"] == [1, 6]
    for bad in (_misterios_data(4), _misterios_data(6), None):
        r = await client.post(
            "/gestor/conteudos", headers=manager, json=_body("misterio", data=bad)
        )
        assert r.status_code == 422
    dias = {**_misterios_data(), "weekdays": [7]}
    assert (
        await client.post("/gestor/conteudos", headers=manager, json=_body("misterio", data=dias))
    ).status_code == 422
    sem_titulo = _misterios_data()
    sem_titulo["mysteries"][2]["title"] = ""
    r = await client.post(
        "/gestor/conteudos", headers=manager, json=_body("misterio", data=sem_titulo)
    )
    assert r.status_code == 422 and "Mistério 3" in r.json()["detail"]


async def test_santo_exige_data_da_festa(client: httpx.AsyncClient, manager: Headers) -> None:
    ok = await client.post(
        "/gestor/conteudos", headers=manager, json=_body("santo", data={"date": "10-04"})
    )
    assert ok.status_code == 201 and ok.json()["data"] == {"date": "10-04"}
    assert (
        await client.post(
            "/gestor/conteudos", headers=manager, json=_body("santo", data={"date": "02-29"})
        )
    ).status_code == 201  # 29 de fevereiro existe no calendário
    for bad in (None, {}, {"date": "13-01"}, {"date": "02-30"}, {"date": "1-4"}):
        r = await client.post("/gestor/conteudos", headers=manager, json=_body("santo", data=bad))
        assert r.status_code == 422, bad


async def test_horas_e_demais_tipos_nao_exigem_dados(
    client: httpx.AsyncClient, manager: Headers
) -> None:
    for kind in ("hora", "oracao", "texto", "reflexao", "rito", "terco"):
        r = await client.post("/gestor/conteudos", headers=manager, json=_body(kind))
        assert r.status_code == 201 and r.json()["data"] is None, kind


async def test_identificador_personalizado(client: httpx.AsyncClient, manager: Headers) -> None:
    a = await client.post(
        "/gestor/conteudos",
        headers=manager,
        json=_body("oracao", title="Glória ao Pai", slug="gloria"),
    )
    assert a.status_code == 201 and a.json()["slug"] == "gloria"
    dup = await client.post(
        "/gestor/conteudos", headers=manager, json=_body("oracao", title="Outra", slug="gloria")
    )
    assert dup.status_code == 409
    for bad in ("Com Espaço", "-x", "a--b", "x" * 101):
        r = await client.post("/gestor/conteudos", headers=manager, json=_body("oracao", slug=bad))
        assert r.status_code == 422, bad
    # editar mantendo o mesmo identificador não conflita consigo mesmo; trocar para um livre funciona
    cid = a.json()["id"]
    same = await client.put(
        f"/gestor/conteudos/{cid}",
        headers=manager,
        json=_body("oracao", title="Glória", slug="gloria"),
    )
    assert same.status_code == 200 and same.json()["slug"] == "gloria"
    moved = await client.put(
        f"/gestor/conteudos/{cid}",
        headers=manager,
        json=_body("oracao", title="Glória", slug="gloria-2"),
    )
    assert moved.json()["slug"] == "gloria-2"
    # sem identificador na edição, o atual é mantido
    keep = await client.put(
        f"/gestor/conteudos/{cid}", headers=manager, json=_body("oracao", title="X")
    )
    assert keep.json()["slug"] == "gloria-2"


async def test_terco_com_conjunto_proprio_e_registro_de_oracao(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    for slug in ("misterios-de-sao-jose", "gozosos", "gloriosos-2"):
        r = await client.post(
            "/me/rosario",
            headers=auth,
            json={"client_id": str(uuid.uuid4()), "date": "2026-05-10", "mystery_set": slug},
        )
        assert r.status_code == 201, slug
    for bad in ("", "Com Espaço", "x" * 61):
        r = await client.post(
            "/me/rosario",
            headers=auth,
            json={"client_id": str(uuid.uuid4()), "date": "2026-05-10", "mystery_set": bad},
        )
        assert r.status_code == 422, bad


async def test_conteudos_publicos_trazem_os_dados_estruturados(
    client: httpx.AsyncClient, manager: Headers
) -> None:
    await client.post(
        "/gestor/conteudos", headers=manager, json=_body("novena", data=_novena_data())
    )
    pub = (await client.get("/conteudos")).json()
    assert pub[0]["kind"] == "novena" and len(pub[0]["data"]["days"]) == 9
