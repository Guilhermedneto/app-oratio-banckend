from datetime import date

import httpx

from app.core.config import get_settings
from app.integrations.base import LiturgySource, ReadingData, SourceDay
from app.integrations.http_sources import CancaoNovaSource, CnbbSource, RailwaySource


class SampleSource:
    """Fonte de desenvolvimento: texto de amostra, claramente rotulado."""

    name = "amostra"

    async def fetch(self, d: date) -> SourceDay:
        note = "[AMOSTRA DE DESENVOLVIMENTO — não é o texto litúrgico oficial]"
        return SourceDay(
            self.name,
            [
                ReadingData("primeira", "Referência de exemplo", "Primeira leitura", note),
                ReadingData("salmo", "Sl 0", "Salmo responsorial", note),
                ReadingData("aclamacao", "", "Aclamação ao Evangelho", note),
                ReadingData("evangelho", "Referência de exemplo", "Evangelho", note),
            ],
        )


_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(headers={"User-Agent": "oratio/0.1"}, follow_redirects=True)
    return _client


def build_sources(names: list[str] | None = None) -> list[LiturgySource]:
    names = names if names is not None else get_settings().source_list
    out: list[LiturgySource] = []
    for n in names:
        if n == "cnbb":
            out.append(CnbbSource(_http()))
        elif n == "cancaonova":
            out.append(CancaoNovaSource(_http()))
        elif n == "railway":
            out.append(RailwaySource(_http()))
        elif n in ("sample", "amostra"):
            out.append(SampleSource())
    return out
