import json
from pathlib import Path

import httpx
import pytest
from conftest import FakeSource

from app.integrations.base import SourceError
from app.integrations.http_sources import CancaoNovaSource, CnbbSource, RailwaySource


async def test_hoje_ok_and_cached(client: httpx.AsyncClient, source: FakeSource) -> None:
    r = await client.get("/liturgia/hoje")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and len(body["readings"]) == 2
    assert body["season"] and body["color"] and body["celebration"]
    assert body["credits"].startswith("Texto: CNBB")
    await client.get("/liturgia/hoje")
    assert source.calls == 1  # segunda requisição não dispara coleta


async def test_etag_304(client: httpx.AsyncClient) -> None:
    r = await client.get("/liturgia/2026-04-05")
    assert "max-age" in r.headers["cache-control"]
    etag = r.headers["etag"]
    r2 = await client.get("/liturgia/2026-04-05", headers={"If-None-Match": etag})
    assert r2.status_code == 304


async def test_partial_when_sources_fail(client: httpx.AsyncClient, source: FakeSource) -> None:
    source.fail = True
    r = await client.get("/liturgia/2026-04-05")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "partial" and body["readings"] == []
    assert body["color"] == "branco" and body["season"] == "pascoa"
    n = source.calls
    await client.get("/liturgia/2026-04-05")
    assert source.calls == n  # não martela a fonte logo após falhar


async def test_fallback_between_sources(client: httpx.AsyncClient) -> None:
    from app.main import app
    from app.routers.deps import get_sources

    bad, good = FakeSource("a", fail=True), FakeSource("b")
    app.dependency_overrides[get_sources] = lambda: [bad, good]
    r = await client.get("/liturgia/2026-05-01")
    assert r.json()["source"] == "b"
    assert bad.calls == 1 and good.calls == 1


async def test_invalid_date_422(client: httpx.AsyncClient) -> None:
    assert (await client.get("/liturgia/2026-13-45")).status_code == 422
    assert (await client.get("/liturgia/ontem")).status_code == 422
    assert (await client.get("/liturgia/1800-01-01")).status_code == 422


async def test_semana(client: httpx.AsyncClient) -> None:
    r = await client.get("/liturgia/semana?de=2026-11-16")
    assert r.status_code == 200
    days = r.json()
    assert len(days) == 7 and days[0]["date"] == "2026-11-16"


async def test_sugestoes_novenas(client: httpx.AsyncClient) -> None:
    r = await client.get("/novenas/sugestoes")
    assert r.status_code == 200
    slugs = {x["slug"] for x in r.json()}
    assert "nossa-senhora-aparecida" in slugs and "espirito-santo" in slugs


# ---- adaptadores com respostas simuladas (fixtures em tests/fixtures)


def _fixture(name: str):  # type: ignore[no-untyped-def]
    return json.loads((Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8"))


def _client(handler):  # type: ignore[no-untyped-def]
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_cnbb_adapter_parses() -> None:
    from datetime import date

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path.endswith("2026-04-05")
        return httpx.Response(200, json=_fixture("cnbb_2026-04-05.json"))

    src = CnbbSource(_client(handler))
    day = await src.fetch(date(2026, 4, 5))
    assert [r.kind for r in day.readings] == ["primeira", "evangelho"]
    assert day.readings[0].text == "Pedro"


async def test_cnbb_404_and_bad_format() -> None:
    from datetime import date

    with pytest.raises(SourceError):
        await CnbbSource(_client(lambda r: httpx.Response(404))).fetch(date(2026, 1, 1))
    with pytest.raises(SourceError):
        await CnbbSource(_client(lambda r: httpx.Response(200, json={"x": 1}))).fetch(
            date(2026, 1, 1)
        )
    with pytest.raises(SourceError):
        await CnbbSource(_client(lambda r: httpx.Response(200, text="<html>"))).fetch(
            date(2026, 1, 1)
        )


async def test_dict_sources_parse() -> None:
    from datetime import date

    payload = {
        "readings": {
            "first_reading": {"head": "Is 1,1", "title": "Primeira", "text": "texto"},
            "psalm": {"response": "R. Senhor", "content_psalm": ["v1", "v2"]},
            "gospel": {"head": "Mt 1,1", "text": "ev"},
        }
    }
    for cls in (CancaoNovaSource,):
        day = await cls(_client(lambda r: httpx.Response(200, json=payload))).fetch(
            date(2026, 1, 1)
        )
        kinds = [r.kind for r in day.readings]
        assert kinds == ["primeira", "salmo", "evangelho"]
        assert "v1" in day.readings[1].text


async def test_502_becomes_source_error() -> None:
    from datetime import date

    src = RailwaySource(
        _client(lambda r: httpx.Response(502, json={"error": "upstream_unavailable"}))
    )
    with pytest.raises(SourceError):
        await src.fetch(date(2026, 1, 1))


async def test_plano_b_guarda_so_referencias_e_tenta_texto_depois(
    client: httpx.AsyncClient, source: FakeSource
) -> None:
    from app.core.db import SessionLocal
    from app.integrations.base import ReadingData, SourceDay
    from app.repositories import liturgy as repo

    class RefsSource:
        name = "cnbb"

        async def fetch(self, d):  # type: ignore[no-untyped-def]
            return SourceDay("cnbb", [ReadingData("evangelho", "Jo 20,1-9", "", "")])

    from app.main import app
    from app.routers.deps import get_sources

    app.dependency_overrides[get_sources] = lambda: [RefsSource()]
    r = await client.get("/liturgia/2026-04-05")
    body = r.json()
    assert [x["reference"] for x in body["readings"]] == ["Jo 20,1-9"]
    assert body["readings"][0]["text"] == ""
    # depois do intervalo de retentativa, uma fonte com texto substitui as referências
    async with SessionLocal() as s:
        from datetime import UTC, datetime, timedelta

        day = await repo.get_day(s, __import__("datetime").date(2026, 4, 5))
        day.fetched_at = datetime.now(UTC) - timedelta(hours=1)
        await s.commit()
    app.dependency_overrides[get_sources] = lambda: [source]
    r2 = await client.get("/liturgia/2026-04-05")
    assert r2.json()["readings"][0]["text"] == "texto 1"


async def test_railway_v2_com_resposta_real() -> None:
    from datetime import date

    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(str(req.url))
        return httpx.Response(200, json=_fixture("railway_v2_2026-11-22.json"))

    day = await RailwaySource(_client(handler)).fetch(date(2026, 11, 22))
    assert seen == ["https://liturgia.up.railway.app/v2/?dia=22&mes=11&ano=2026"]
    assert [r.kind for r in day.readings] == ["primeira", "salmo", "segunda", "evangelho"]
    assert not any(r.text[:1].isdigit() for r in day.readings)  # números de versículo removidos
    assert "\n" in day.readings[1].text  # refrão + estrofes


async def test_railway_v2_sem_segunda_leitura_e_data_divergente() -> None:
    from datetime import date

    ok = lambda r: httpx.Response(200, json=_fixture("railway_v2_2026-11-16.json"))  # noqa: E731
    day = await RailwaySource(_client(ok)).fetch(date(2026, 11, 16))
    assert [r.kind for r in day.readings] == ["primeira", "salmo", "evangelho"]
    with pytest.raises(SourceError):  # a fonte devolveu outro dia
        await RailwaySource(_client(ok)).fetch(date(2026, 11, 22))
    with pytest.raises(SourceError):
        await RailwaySource(_client(lambda r: httpx.Response(404, json={"erro": "x"}))).fetch(
            date(2026, 11, 28)
        )


async def test_railway_cai_para_a_v1_se_a_v2_falhar() -> None:
    from datetime import date

    def handler(req: httpx.Request) -> httpx.Response:
        if "/v2/" in str(req.url):
            return httpx.Response(502, json={"erro": "x"})
        return httpx.Response(200, json=_fixture("railway_2026-11-22.json"))

    day = await RailwaySource(_client(handler)).fetch(date(2026, 11, 22))
    assert [r.kind for r in day.readings] == ["primeira", "salmo", "segunda", "evangelho"]


async def test_hoje_traz_oracoes_do_dia(client: httpx.AsyncClient) -> None:
    body = (await client.get("/liturgia/2026-11-16")).json()
    assert [p["kind"] for p in body["prayers"]] == ["antifona_entrada", "coleta"]
    assert body["prayers"][1]["text"] == "coleta"


async def test_railway_v2_extrai_oracoes_e_extras() -> None:
    from datetime import date

    payload = _fixture("railway_v2_2026-11-22.json")
    payload["oracoes"]["extras"] = [
        {"titulo": "Benção do fogo", "texto": "Ó Deus, santificai este fogo."}
    ]
    payload["leituras"]["extras"] = [
        {
            "tipo": "Terceira Leitura",
            "referencia": "Ex 14, 15",
            "titulo": "Êxodo",
            "texto": "3Texto",
        }
    ]
    day = await RailwaySource(_client(lambda r: httpx.Response(200, json=payload))).fetch(
        date(2026, 11, 22)
    )
    kinds = [p.kind for p in day.prayers]
    assert kinds[:5] == [
        "antifona_entrada",
        "coleta",
        "oferendas",
        "antifona_comunhao",
        "depois_comunhao",
    ]
    assert kinds[5:] == ["extra", "extra"]
    assert day.prayers[5].title == "Benção do fogo"
    assert day.prayers[6].title == "Terceira Leitura — Ex 14, 15"
    assert day.prayers[6].text == "Texto"


async def test_v1_tambem_extrai_oracoes() -> None:
    from datetime import date

    def handler(req: httpx.Request) -> httpx.Response:
        if "/v2/" in str(req.url):
            return httpx.Response(502, json={})
        return httpx.Response(200, json=_fixture("railway_2026-11-22.json"))

    day = await RailwaySource(_client(handler)).fetch(date(2026, 11, 22))
    kinds = [p.kind for p in day.prayers]
    assert {"coleta", "oferendas", "depois_comunhao"} <= set(kinds)


async def test_dia_salvo_e_atualizado_quando_o_calendario_muda(client: httpx.AsyncClient) -> None:
    from sqlalchemy import update

    from app.core.db import SessionLocal
    from app.models import LiturgicalDay

    await client.get("/liturgia/2026-11-17")
    async with SessionLocal() as s:
        await s.execute(
            update(LiturgicalDay)
            .where(LiturgicalDay.date == __import__("datetime").date(2026, 11, 17))
            .values(celebration="texto antigo", color="verde")
        )
        await s.commit()
    body = (await client.get("/liturgia/2026-11-17")).json()
    assert body["celebration"].startswith("Santa Isabel da Hungria")
    assert body["color"] == "branco"
