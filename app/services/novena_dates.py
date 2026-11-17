from datetime import date, timedelta

from app.schemas.api import NovenaSuggestionOut
from app.services.calendar import easter


def _next(year_fn, today: date) -> tuple[date, date]:  # type: ignore[no-untyped-def]
    for y in (today.year, today.year + 1):
        feast = year_fn(y)
        start = feast - timedelta(days=9)
        if start >= today:
            return start, feast
    feast = year_fn(today.year + 1)
    return feast - timedelta(days=9), feast


def suggestions(today: date) -> list[NovenaSuggestionOut]:
    """Início sugerido: a próxima ocorrência cujo primeiro dia ainda não passou.

    Para cada novena o 'feast' é o dia em que a novena termina (9º dia = véspera da festa,
    exceto onde indicado).
    """
    table = {
        # Espírito Santo: da sexta após a Ascensão (Brasil: domingo) até o sábado antes de Pentecostes
        "espirito-santo": lambda y: easter(y) + timedelta(days=49),
        "natal": lambda y: date(y, 12, 25),
        "nossa-senhora-aparecida": lambda y: date(y, 10, 12),
        "sagrado-coracao": lambda y: easter(y) + timedelta(days=49 + 19),
        "sao-jose": lambda y: date(y, 3, 19),
        "santa-terezinha": lambda y: date(y, 10, 1),
    }
    out = []
    for slug, fn in table.items():
        start, feast = _next(fn, today)
        out.append(NovenaSuggestionOut(slug=slug, start=start, feast=feast))
    return sorted(out, key=lambda x: x.start)
