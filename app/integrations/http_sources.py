"""Adaptadores de fontes externas de leitura.

Os formatos de JSON abaixo foram inferidos da documentação dos repositórios citados em plano.md
(§9.1) e NÃO foram verificados ao vivo. Cada adaptador é defensivo: qualquer formato inesperado
vira SourceError e o serviço tenta a próxima fonte.
"""

import asyncio
import re
from datetime import date
from typing import Any

import httpx

from app.integrations.base import PrayerData, ReadingData, SourceDay, SourceError

TIMEOUT = 5.0
RETRIES = 2
_TAG = re.compile(r"<[^>]+>")


def _clean(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    text = re.sub(r"<br\s*/?>|</p>", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", _TAG.sub("", text)).strip()


async def _get_json(client: httpx.AsyncClient, url: str, **kw: Any) -> Any:
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            r = await client.get(url, timeout=TIMEOUT, **kw)
            if r.status_code == 404:
                raise SourceError("data não disponível (404)")
            r.raise_for_status()
            return r.json()
        except SourceError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            last = exc
            if attempt + 1 < RETRIES:
                await asyncio.sleep(0.3 * (attempt + 1))
    raise SourceError(f"falha de rede/parse: {last}")


def _pick(d: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _reading(kind: str, raw: Any) -> ReadingData | None:
    if not isinstance(raw, dict):
        return None
    text = _pick(raw, "text", "texto", "content", "conteudo")
    if isinstance(text, list):
        text = "\n".join(str(t) for t in text)
    ref = _pick(raw, "reference", "referencia", "citation", "head") or ""
    title = _pick(raw, "title", "titulo") or ""
    if not text and not ref:
        return None
    return ReadingData(kind, _clean(ref)[:120], _clean(title)[:300], _clean(text))


class CnbbSource:
    """Edições CNBB: Liturgia da Palavra. Rota conhecida; JSON não documentado."""

    name = "cnbb"
    BASE = "https://api-liturgia.edicoescnbb.com.br/contents/in/date/"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch(self, d: date) -> SourceDay:
        data = await _get_json(self.client, f"{self.BASE}{d.isoformat()}")
        items = data.get("readings") if isinstance(data, dict) else None
        if items is None and isinstance(data, dict):
            items = data.get("leituras")
        if not isinstance(items, list):
            raise SourceError("formato inesperado (CNBB)")
        mapping = {
            "primeira": "primeira",
            "first_reading": "primeira",
            "salmo": "salmo",
            "psalm": "salmo",
            "segunda": "segunda",
            "second_reading": "segunda",
            "aclamacao": "aclamacao",
            "evangelho": "evangelho",
            "gospel": "evangelho",
        }
        out: list[ReadingData] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            k = mapping.get(str(_pick(it, "type", "tipo", "kind") or "").lower())
            r = _reading(k, it) if k else None
            if r:
                out.append(r)
        if not out:
            raise SourceError("sem leituras (CNBB)")
        return SourceDay(self.name, out)


class DictReadingsSource:
    """Fontes cujo JSON traz `readings.{first_reading, psalm, gospel, second_reading}`."""

    name = "base"

    def __init__(self, client: httpx.AsyncClient, url_for: Any) -> None:
        self.client = client
        self._url_for = url_for

    async def fetch(self, d: date) -> SourceDay:
        data = await _get_json(self.client, self._url_for(d))
        block = data.get("readings") if isinstance(data, dict) else None
        if not isinstance(block, dict):
            raise SourceError(f"formato inesperado ({self.name})")
        out: list[ReadingData] = []
        for key, kind in (
            ("first_reading", "primeira"),
            ("psalm", "salmo"),
            ("second_reading", "segunda"),
            ("gospel", "evangelho"),
        ):
            raw = block.get(key)
            if isinstance(raw, dict) and kind == "salmo":
                content = raw.get("content_psalm")
                lines = [str(raw.get("response") or "")]
                lines += [str(c) for c in content] if isinstance(content, list) else []
                raw = {**raw, "text": "\n".join(lines).strip() or raw.get("text")}
            r = _reading(kind, raw)
            if r:
                out.append(r)
        if not out:
            raise SourceError(f"sem leituras ({self.name})")
        return SourceDay(self.name, out)


class CancaoNovaSource(DictReadingsSource):
    name = "cancaonova"
    BASE = "https://liturgia.cancaonova.com/pb/"

    def __init__(self, client: httpx.AsyncClient, base: str | None = None) -> None:
        root = base or self.BASE
        super().__init__(client, lambda d: f"{root}?date={d.isoformat()}")


class RailwaySource:
    """liturgia.up.railway.app, projeto Dancrf/liturgia-diaria (verificado ao vivo em 16/11/2026).

    Usa a v2 (`/v2/`, leituras em lista). A v1 (raiz) será desativada em 01/12/2026 e fica só
    como reserva. A data vai por `?dia=&mes=&ano=` (o parâmetro `date` é ignorado) e o campo
    `data` (dd/mm/aaaa) da resposta é conferido.
    """

    name = "railway"
    BASE = "https://liturgia.up.railway.app/"
    _VERSE = re.compile(r"(?<![\w])\d{1,3}(?=[A-Za-zÀ-ÿ“\"‘'(«])")
    _KINDS = (
        ("primeiraLeitura", "primeira"),
        ("salmo", "salmo"),
        ("segundaLeitura", "segunda"),
        ("evangelho", "evangelho"),
    )

    def __init__(self, client: httpx.AsyncClient, base: str | None = None) -> None:
        self.client = client
        self.base = base or self.BASE

    def _text(self, raw: Any) -> str:
        return self._VERSE.sub("", _clean(raw)).strip()

    def _block(self, kind: str, block: Any) -> ReadingData | None:
        if not isinstance(block, dict):  # ex.: "Não há segunda leitura hoje!" (v1)
            return None
        text = self._text(block.get("texto"))
        refrao = self._text(block.get("refrao"))
        if kind == "salmo" and refrao:
            text = refrao + "\n\n" + text
        ref = _clean(block.get("referencia"))[:120]
        if not (text.strip() or ref):
            return None
        return ReadingData(kind, ref, _clean(block.get("titulo"))[:300], text.strip())

    async def _load(self, path: str, d: date) -> dict[str, Any]:
        data = await _get_json(
            self.client, f"{self.base}{path}?dia={d.day}&mes={d.month}&ano={d.year}"
        )
        if not isinstance(data, dict):
            raise SourceError("formato inesperado (railway)")
        if data.get("data") != d.strftime("%d/%m/%Y"):
            raise SourceError(f"data divergente (railway): {data.get('data')}")
        return data

    def _parse(self, data: dict[str, Any], v2: bool) -> list[ReadingData]:
        blocks = data.get("leituras") if v2 else data
        if not isinstance(blocks, dict):
            raise SourceError("formato inesperado (railway)")
        out: list[ReadingData] = []
        for key, kind in self._KINDS:
            item = blocks.get(key)
            if v2:  # lista; a primeira opção é a forma principal (ex.: forma longa)
                item = item[0] if isinstance(item, list) and item else None
            r = self._block(kind, item)
            if r:
                out.append(r)
        return out

    def _prayers(self, data: dict[str, Any], v2: bool) -> list[PrayerData]:
        antifonas: dict[str, Any] = data.get("antifonas") or {}
        if not isinstance(antifonas, dict):
            antifonas = {}
        oracoes: dict[str, Any] = (data.get("oracoes") if v2 else data) or {}
        if not isinstance(oracoes, dict):
            oracoes = {}
        coleta = oracoes.get("coleta") if v2 else data.get("dia")
        plan = (
            ("antifona_entrada", "Antífona de entrada", antifonas.get("entrada")),
            ("coleta", "Oração do dia (coleta)", coleta),
            ("oferendas", "Oração sobre as oferendas", oracoes.get("oferendas")),
            ("antifona_comunhao", "Antífona da comunhão", antifonas.get("comunhao")),
            ("depois_comunhao", "Oração depois da comunhão", oracoes.get("comunhao")),
        )
        out = [PrayerData(k, t, _clean(raw)) for k, t, raw in plan if _clean(raw)]
        if v2:
            extras = list(oracoes.get("extras") or [])
            leituras = data.get("leituras")
            extras += list(leituras.get("extras") or []) if isinstance(leituras, dict) else []
            for e in extras:
                if not isinstance(e, dict) or not _clean(e.get("texto")):
                    continue
                parts = [
                    _clean(e.get("tipo")),
                    _clean(e.get("referencia")) or _clean(e.get("titulo")),
                ]
                title = " — ".join(p for p in parts if p) or "Oração"
                out.append(PrayerData("extra", title[:200], self._text(e.get("texto"))))
        return out

    async def fetch(self, d: date) -> SourceDay:
        try:
            data = await self._load("v2/", d)
            readings, prayers = self._parse(data, v2=True), self._prayers(data, v2=True)
        except SourceError:
            data = await self._load("", d)  # reserva: v1
            readings, prayers = self._parse(data, v2=False), self._prayers(data, v2=False)
        if not readings:
            raise SourceError("sem leituras (railway)")
        return SourceDay(self.name, readings, prayers)
