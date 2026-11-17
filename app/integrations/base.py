from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

READING_KINDS = ("primeira", "salmo", "segunda", "aclamacao", "evangelho")


class SourceError(Exception):
    """Falha ao obter ou interpretar dados de uma fonte."""


@dataclass
class ReadingData:
    kind: str
    reference: str = ""
    title: str = ""
    text: str = ""


@dataclass
class PrayerData:
    kind: str  # antifona_entrada, coleta, oferendas, antifona_comunhao, depois_comunhao, extra
    title: str
    text: str


@dataclass
class SourceDay:
    source: str
    readings: list[ReadingData] = field(default_factory=list)
    prayers: list[PrayerData] = field(default_factory=list)


class LiturgySource(Protocol):
    name: str

    async def fetch(self, d: date) -> SourceDay: ...
