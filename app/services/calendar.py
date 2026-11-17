"""Cálculo litúrgico local (sem rede): calendário romano com adaptações do Brasil."""

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import Protocol

SEASON_LABELS = {
    "advento": "Advento",
    "natal": "Natal",
    "comum": "Tempo Comum",
    "quaresma": "Quaresma",
    "triduo": "Tríduo Pascal",
    "pascoa": "Páscoa",
}
SEASON_COLORS = {
    "advento": "roxo",
    "natal": "branco",
    "comum": "verde",
    "quaresma": "roxo",
    "triduo": "vermelho",
    "pascoa": "branco",
}

# prioridade: menor vence
P_TOP, P_SOLEMNITY, P_LORD_FEAST, P_SUNDAY_OT, P_FEAST, P_MEMORIAL, P_OPTIONAL, P_FERIA = (
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
)


@dataclass(frozen=True)
class LiturgicalInfo:
    date: date
    season: str
    week: int | None
    color: str
    celebration: str
    rank: str
    cycle_sunday: str
    cycle_weekday: str


class LiturgicalCalendar(Protocol):
    def day(self, d: date) -> LiturgicalInfo: ...


def easter(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


def sunday_on_or_before(d: date) -> date:
    return d - timedelta(days=(d.weekday() + 1) % 7)


def first_advent(year: int) -> date:
    return sunday_on_or_before(date(year, 12, 24)) - timedelta(days=21)


def epiphany(year: int) -> date:
    """Brasil: Epifania no domingo entre 2 e 8 de janeiro."""
    d = date(year, 1, 2)
    return d + timedelta(days=(6 - d.weekday()) % 7)


def baptism(year: int) -> date:
    e = epiphany(year)
    return e + timedelta(days=1) if e.day >= 7 else e + timedelta(days=7)


def holy_family(year: int) -> date:
    xmas = date(year, 12, 25)
    if xmas.weekday() == 6:
        return date(year, 12, 30)
    return xmas + timedelta(days=(6 - xmas.weekday()) % 7)


def liturgical_year_start(d: date) -> int:
    return d.year if d >= first_advent(d.year) else d.year - 1


def _season_and_week(d: date) -> tuple[str, int | None]:
    y = d.year
    e = easter(y)
    advent = first_advent(y)
    if d >= date(y, 12, 25):
        return "natal", None
    if d >= advent:
        return "advento", (sunday_on_or_before(d) - advent).days // 7 + 1
    bap = baptism(y)
    if d <= bap:
        return "natal", None
    ash = e - timedelta(days=46)
    if d < ash:
        return "comum", _ot_week_first_part(d, bap)
    if d < e - timedelta(days=3):
        first_sunday = e - timedelta(days=42)
        wk = 0 if d < first_sunday else (sunday_on_or_before(d) - first_sunday).days // 7 + 1
        return "quaresma", wk
    if d < e:
        return "triduo", None
    pentecost = e + timedelta(days=49)
    if d <= pentecost:
        return "pascoa", (sunday_on_or_before(d) - e).days // 7 + 1
    christ_king = advent - timedelta(days=7)
    return "comum", 34 - (christ_king - sunday_on_or_before(d)).days // 7


def _ot_week_first_part(d: date, bap: date) -> int:
    first_sunday = sunday_on_or_before(bap + timedelta(days=7))
    s = sunday_on_or_before(d)
    return 1 if s < first_sunday else (s - first_sunday).days // 7 + 2


@dataclass(frozen=True)
class _Cel:
    name: str
    rank: str
    color: str
    priority: int


S, F, M, MO = "solenidade", "festa", "memoria", "memoria_facultativa"
_PRIORITY = {S: P_SOLEMNITY, F: P_FEAST, M: P_MEMORIAL, MO: P_OPTIONAL}

# (mês, dia, nome, grau, cor, festa_do_senhor)
_FIXED: list[tuple[int, int, str, str, str, bool]] = [
    (1, 1, "Santa Maria, Mãe de Deus", S, "branco", False),
    (1, 17, "Santo Antão, abade", M, "branco", False),
    (1, 20, "São Sebastião, mártir", MO, "vermelho", False),
    (1, 21, "Santa Inês, virgem e mártir", M, "vermelho", False),
    (1, 24, "São Francisco de Sales, bispo e doutor da Igreja", M, "branco", False),
    (1, 25, "Conversão de São Paulo, apóstolo", F, "branco", False),
    (1, 26, "Santos Timóteo e Tito, bispos", M, "branco", False),
    (1, 28, "São Tomás de Aquino, presbítero e doutor da Igreja", M, "branco", False),
    (1, 31, "São João Bosco, presbítero", M, "branco", False),
    (2, 2, "Apresentação do Senhor", F, "branco", True),
    (2, 3, "São Brás, bispo e mártir", MO, "vermelho", False),
    (2, 10, "Santa Escolástica, virgem", M, "branco", False),
    (2, 14, "Santos Cirilo, monge, e Metódio, bispo", M, "branco", False),
    (2, 22, "Cátedra de São Pedro, apóstolo", F, "branco", False),
    (3, 17, "São Patrício, bispo", MO, "branco", False),
    (3, 19, "São José, esposo da Virgem Maria", S, "branco", False),
    (3, 25, "Anunciação do Senhor", S, "branco", True),
    (4, 25, "São Marcos, evangelista", F, "vermelho", False),
    (4, 29, "Santa Catarina de Sena, virgem e doutora da Igreja", M, "branco", False),
    (5, 1, "São José Operário", MO, "branco", False),
    (5, 3, "São Filipe e São Tiago, apóstolos", F, "vermelho", False),
    (5, 13, "Nossa Senhora de Fátima", MO, "branco", False),
    (5, 14, "São Matias, apóstolo", F, "vermelho", False),
    (5, 31, "Visitação de Nossa Senhora", F, "branco", False),
    (6, 11, "São Barnabé, apóstolo", M, "vermelho", False),
    (6, 13, "Santo Antônio de Pádua, presbítero e doutor da Igreja", M, "branco", False),
    (6, 21, "São Luís Gonzaga, religioso", M, "branco", False),
    (6, 24, "Natividade de São João Batista", S, "branco", False),
    (6, 29, "São Pedro e São Paulo, apóstolos", S, "vermelho", False),
    (7, 3, "São Tomé, apóstolo", F, "vermelho", False),
    (7, 11, "São Bento, abade", M, "branco", False),
    (7, 16, "Nossa Senhora do Carmo", MO, "branco", False),
    (7, 25, "São Tiago, apóstolo", F, "vermelho", False),
    (7, 26, "São Joaquim e Santa Ana, pais de Nossa Senhora", M, "branco", False),
    (7, 29, "Santa Marta", M, "branco", False),
    (7, 31, "Santo Inácio de Loyola, presbítero", M, "branco", False),
    (8, 4, "São João Maria Vianney, presbítero", M, "branco", False),
    (8, 6, "Transfiguração do Senhor", F, "branco", True),
    (8, 8, "São Domingos, presbítero", M, "branco", False),
    (8, 10, "São Lourenço, diácono e mártir", F, "vermelho", False),
    (8, 15, "Assunção de Nossa Senhora", S, "branco", False),
    (8, 20, "São Bernardo, abade e doutor da Igreja", M, "branco", False),
    (8, 22, "Nossa Senhora Rainha", M, "branco", False),
    (8, 24, "São Bartolomeu, apóstolo", F, "vermelho", False),
    (8, 27, "Santa Mônica", M, "branco", False),
    (8, 28, "Santo Agostinho, bispo e doutor da Igreja", M, "branco", False),
    (8, 29, "Martírio de São João Batista", M, "vermelho", False),
    (9, 8, "Natividade de Nossa Senhora", F, "branco", False),
    (9, 14, "Exaltação da Santa Cruz", F, "vermelho", True),
    (9, 15, "Nossa Senhora das Dores", M, "branco", False),
    (9, 21, "São Mateus, apóstolo e evangelista", F, "vermelho", False),
    (9, 27, "São Vicente de Paulo, presbítero", M, "branco", False),
    (9, 29, "Santos Miguel, Gabriel e Rafael, arcanjos", F, "branco", False),
    (9, 30, "São Jerônimo, presbítero e doutor da Igreja", M, "branco", False),
    (10, 1, "Santa Teresinha do Menino Jesus, virgem e doutora da Igreja", M, "branco", False),
    (10, 2, "Santos Anjos da Guarda", M, "branco", False),
    (10, 4, "São Francisco de Assis", M, "branco", False),
    (10, 7, "Nossa Senhora do Rosário", M, "branco", False),
    (10, 12, "Nossa Senhora Conceição Aparecida, Padroeira do Brasil", S, "branco", False),
    (10, 15, "Santa Teresa de Ávila, virgem e doutora da Igreja", M, "branco", False),
    (10, 18, "São Lucas, evangelista", F, "vermelho", False),
    (10, 22, "São João Paulo II, papa", MO, "branco", False),
    (10, 28, "São Simão e São Judas Tadeu, apóstolos", F, "vermelho", False),
    (11, 1, "Todos os Santos", S, "branco", False),
    (11, 2, "Comemoração de Todos os Fiéis Defuntos", S, "roxo", False),
    (11, 4, "São Carlos Borromeu, bispo", M, "branco", False),
    (11, 9, "Dedicação da Basílica de Latrão", F, "branco", True),
    (11, 11, "São Martinho de Tours, bispo", M, "branco", False),
    (11, 21, "Apresentação de Nossa Senhora", M, "branco", False),
    (11, 22, "Santa Cecília, virgem e mártir", M, "vermelho", False),
    (11, 30, "Santo André, apóstolo", F, "vermelho", False),
    (12, 3, "São Francisco Xavier, presbítero", M, "branco", False),
    (12, 6, "São Nicolau, bispo", MO, "branco", False),
    (12, 7, "Santo Ambrósio, bispo e doutor da Igreja", M, "branco", False),
    (12, 8, "Imaculada Conceição de Nossa Senhora", S, "branco", False),
    (12, 12, "Nossa Senhora de Guadalupe", MO, "branco", False),
    (12, 13, "Santa Luzia, virgem e mártir", M, "vermelho", False),
    (12, 14, "São João da Cruz, presbítero e doutor da Igreja", M, "branco", False),
    (12, 25, "Natal do Senhor", S, "branco", True),
    (12, 26, "Santo Estêvão, primeiro mártir", F, "vermelho", False),
    (12, 27, "São João, apóstolo e evangelista", F, "branco", False),
    (12, 28, "Santos Inocentes, mártires", F, "vermelho", False),
    (
        1,
        2,
        "Santos Basílio Magno e Gregório Nazianzeno, bispos e doutores da Igreja",
        M,
        "branco",
        False,
    ),
    (1, 13, "Santo Hilário, bispo e doutor da Igreja", MO, "branco", False),
    (2, 6, "São Paulo Miki e companheiros, mártires", M, "vermelho", False),
    (2, 11, "Nossa Senhora de Lourdes", MO, "branco", False),
    (3, 7, "Santas Perpétua e Felicidade, mártires", M, "vermelho", False),
    (4, 7, "São João Batista de La Salle, presbítero", M, "branco", False),
    (4, 11, "Santo Estanislau, bispo e mártir", M, "vermelho", False),
    (4, 23, "São Jorge, mártir", MO, "vermelho", False),
    (5, 2, "Santo Atanásio, bispo e doutor da Igreja", M, "branco", False),
    (5, 22, "Santa Rita de Cássia, religiosa", MO, "branco", False),
    (5, 26, "São Filipe Néri, presbítero", M, "branco", False),
    (6, 1, "São Justino, mártir", M, "vermelho", False),
    (6, 3, "Santos Carlos Lwanga e companheiros, mártires", M, "vermelho", False),
    (6, 5, "São Bonifácio, bispo e mártir", M, "vermelho", False),
    (6, 22, "Santos João Fisher e Tomás More, mártires", MO, "vermelho", False),
    (6, 28, "Santo Ireneu, bispo e mártir", M, "vermelho", False),
    (7, 4, "Santa Isabel de Portugal", MO, "branco", False),
    (7, 6, "Santa Maria Goretti, virgem e mártir", MO, "vermelho", False),
    (7, 14, "São Camilo de Lélis, presbítero", MO, "branco", False),
    (7, 15, "São Boaventura, bispo e doutor da Igreja", M, "branco", False),
    (7, 22, "Santa Maria Madalena", F, "branco", False),
    (7, 24, "São Charbel Makhlouf, presbítero", MO, "branco", False),
    (8, 1, "Santo Afonso Maria de Ligório, bispo e doutor da Igreja", M, "branco", False),
    (8, 9, "Santa Teresa Benedita da Cruz, virgem e mártir", MO, "vermelho", False),
    (8, 11, "Santa Clara, virgem", M, "branco", False),
    (8, 14, "São Maximiliano Maria Kolbe, presbítero e mártir", M, "vermelho", False),
    (9, 3, "São Gregório Magno, papa e doutor da Igreja", M, "branco", False),
    (9, 13, "São João Crisóstomo, bispo e doutor da Igreja", M, "branco", False),
    (9, 16, "Santos Cornélio, papa, e Cipriano, bispo, mártires", M, "vermelho", False),
    (
        9,
        20,
        "Santos André Kim Taegon, Paulo Chong Hasang e companheiros, mártires",
        M,
        "vermelho",
        False,
    ),
    (9, 23, "São Pio de Pietrelcina, presbítero", M, "branco", False),
    (9, 26, "Santos Cosme e Damião, mártires", MO, "vermelho", False),
    (10, 16, "Santa Edwiges, religiosa", MO, "branco", False),
    (10, 17, "Santo Inácio de Antioquia, bispo e mártir", M, "vermelho", False),
    (10, 24, "Santo Antônio Maria Claret, bispo", MO, "branco", False),
    (11, 3, "São Martinho de Porres, religioso", MO, "branco", False),
    (11, 10, "São Leão Magno, papa e doutor da Igreja", M, "branco", False),
    (11, 12, "São Josafá, bispo e mártir", M, "vermelho", False),
    (11, 17, "Santa Isabel da Hungria, religiosa", M, "branco", False),
    (11, 24, "Santo André Dung-Lac e companheiros, mártires", M, "vermelho", False),
    (12, 29, "São Tomás Becket, bispo e mártir", MO, "vermelho", False),
]
_SHIFTABLE = {"São José, esposo da Virgem Maria", "Anunciação do Senhor"}


def _top_priority_days(year: int) -> dict[date, _Cel]:
    """Dias que não cedem a nada: Tríduo, oitava da Páscoa, Domingos fortes, Semana Santa, etc."""
    e = easter(year)
    out: dict[date, _Cel] = {}
    advent = first_advent(year)
    for i in range(4):
        d = advent + timedelta(days=7 * i)
        out[d] = _Cel(f"{i + 1}º Domingo do Advento", "domingo", "rosa" if i == 2 else "roxo", 1)
    for i in range(5):
        d = e - timedelta(days=42 - 7 * i)
        color = "rosa" if i == 3 else "roxo"
        out[d] = _Cel(f"{i + 1}º Domingo da Quaresma", "domingo", color, 1)
    out[e - timedelta(days=46)] = _Cel("Quarta-feira de Cinzas", "feria", "roxo", 1)
    out[e - timedelta(days=7)] = _Cel(
        "Domingo de Ramos da Paixão do Senhor", "domingo", "vermelho", 1
    )
    holy = {
        1: "Segunda-feira Santa",
        2: "Terça-feira Santa",
        3: "Quarta-feira Santa",
    }
    for off, name in holy.items():
        out[e - timedelta(days=7 - off)] = _Cel(name, "feria", "roxo", 1)
    out[e - timedelta(days=3)] = _Cel(
        "Quinta-feira Santa — Ceia do Senhor", "solenidade", "branco", 1
    )
    out[e - timedelta(days=2)] = _Cel("Sexta-feira da Paixão do Senhor", "feria", "vermelho", 1)
    out[e - timedelta(days=1)] = _Cel("Sábado Santo — Vigília Pascal", "feria", "branco", 1)
    out[e] = _Cel("Domingo de Páscoa da Ressurreição do Senhor", "solenidade", "branco", 1)
    oct_names = [
        "Segunda-feira",
        "Terça-feira",
        "Quarta-feira",
        "Quinta-feira",
        "Sexta-feira",
        "Sábado",
    ]
    for i, n in enumerate(oct_names, start=1):
        out[e + timedelta(days=i)] = _Cel(f"{n} da Oitava da Páscoa", "solenidade", "branco", 1)
    out[e + timedelta(days=7)] = _Cel(
        "2º Domingo da Páscoa (Divina Misericórdia)", "domingo", "branco", 1
    )
    for i in range(2, 6):
        out[e + timedelta(days=7 * i)] = _Cel(f"{i + 1}º Domingo da Páscoa", "domingo", "branco", 1)
    out[e + timedelta(days=42)] = _Cel("Ascensão do Senhor", "solenidade", "branco", 1)
    out[e + timedelta(days=49)] = _Cel("Domingo de Pentecostes", "solenidade", "vermelho", 1)
    out[epiphany(year)] = _Cel("Epifania do Senhor", "solenidade", "branco", 1)
    out[date(year, 12, 25)] = _Cel("Natal do Senhor", "solenidade", "branco", 1)
    return out


def _movable(year: int) -> dict[date, _Cel]:
    e = easter(year)
    pent = e + timedelta(days=49)
    out: dict[date, _Cel] = {}
    out[baptism(year)] = _Cel("Batismo do Senhor", "festa", "branco", P_LORD_FEAST)
    out[holy_family(year)] = _Cel(
        "Sagrada Família de Jesus, Maria e José", "festa", "branco", P_LORD_FEAST
    )
    out[pent + timedelta(days=1)] = _Cel(
        "Bem-aventurada Virgem Maria, Mãe da Igreja", "memoria", "branco", P_MEMORIAL
    )
    out[pent + timedelta(days=7)] = _Cel("Santíssima Trindade", "solenidade", "branco", P_SOLEMNITY)
    out[pent + timedelta(days=11)] = _Cel(
        "Santíssimo Corpo e Sangue de Cristo (Corpus Christi)", "solenidade", "branco", P_SOLEMNITY
    )
    out[pent + timedelta(days=19)] = _Cel(
        "Sagrado Coração de Jesus", "solenidade", "branco", P_SOLEMNITY
    )
    out[pent + timedelta(days=20)] = _Cel(
        "Imaculado Coração de Maria", "memoria", "branco", P_MEMORIAL
    )
    christ_king = first_advent(year) - timedelta(days=7)
    out[christ_king] = _Cel(
        "Nosso Senhor Jesus Cristo, Rei do Universo", "solenidade", "branco", P_SOLEMNITY
    )
    return out


@lru_cache(maxsize=16)
def _year_table(year: int) -> dict[date, list[_Cel]]:
    top = _top_priority_days(year)
    table: dict[date, list[_Cel]] = {}
    for d, c in top.items():
        table.setdefault(d, []).append(c)
    for d, c in _movable(year).items():
        table.setdefault(d, []).append(c)
    e = easter(year)
    palm = e - timedelta(days=7)
    for m, day, name, rank, color, lord in _FIXED:
        d = date(year, m, day)
        cel = _Cel(name, rank, color, P_LORD_FEAST if lord and rank != S else _PRIORITY[rank])
        if rank == S and name in _SHIFTABLE | {"Imaculada Conceição de Nossa Senhora"}:
            d = _transfer(d, top, palm, e, name)
        table.setdefault(d, []).append(cel)
    return table


def _transfer(d: date, top: dict[date, _Cel], palm: date, e: date, name: str) -> date:
    if name == "São José, esposo da Virgem Maria" and palm <= d <= e:
        return palm - timedelta(days=1)
    if name == "Anunciação do Senhor" and palm <= d <= e + timedelta(days=7):
        return e + timedelta(days=8)
    while d in top and top[d].rank == "domingo":
        d += timedelta(days=1)
    return d


def _weekday_name(d: date) -> str:
    return [
        "Segunda-feira",
        "Terça-feira",
        "Quarta-feira",
        "Quinta-feira",
        "Sexta-feira",
        "Sábado",
        "Domingo",
    ][d.weekday()]


class RomanBrazilCalendar:
    def day(self, d: date) -> LiturgicalInfo:
        season, week = _season_and_week(d)
        e = easter(d.year)
        advent_year = liturgical_year_start(d)
        cycle_sunday = "ABC"[(advent_year - 2022) % 3]
        cycle_weekday = "I" if (advent_year + 1) % 2 == 1 else "II"

        candidates = list(_year_table(d.year).get(d, []))
        # Sagrada Família em 30/12 não pode colidir; Natal próprio tratado em top.
        is_sunday = d.weekday() == 6
        if is_sunday and season == "comum":
            candidates.append(
                _Cel(f"{week}º Domingo do Tempo Comum", "domingo", "verde", P_SUNDAY_OT)
            )
        if is_sunday and season == "natal" and not candidates:
            candidates.append(_Cel("Domingo do Tempo do Natal", "domingo", "branco", P_SUNDAY_OT))

        no_memorials = e - timedelta(days=7) <= d <= e + timedelta(days=8) or (
            d.month == 12 and 17 <= d.day <= 24
        )
        lent = season == "quaresma"
        best: _Cel | None = None
        for c in sorted(candidates, key=lambda x: x.priority):
            if no_memorials and c.priority >= P_MEMORIAL:
                continue
            best = c
            break
        if best is not None and lent and best.priority == P_MEMORIAL:
            best = _Cel(best.name, "memoria_facultativa", best.color, P_OPTIONAL)

        if best is None:
            best = self._feria(d, season, week)
        # Memória facultativa não muda a cor do dia: vale a do tempo (roxo na Quaresma, verde no Comum).
        color = SEASON_COLORS[season] if best.rank == "memoria_facultativa" else best.color
        return LiturgicalInfo(
            date=d,
            season=season,
            week=week,
            color=color,
            celebration=best.name,
            rank=best.rank,
            cycle_sunday=cycle_sunday,
            cycle_weekday=cycle_weekday,
        )

    @staticmethod
    def _feria(d: date, season: str, week: int | None) -> _Cel:
        wd = _weekday_name(d)
        color = SEASON_COLORS[season]
        if season == "comum":
            name = f"{wd} da {week}ª semana do Tempo Comum"
        elif season == "advento":
            name = f"{wd} da {week}ª semana do Advento"
            if d.month == 12 and 17 <= d.day <= 24:
                name = f"{d.day} de dezembro — {wd} do Advento"
        elif season == "quaresma":
            name = f"{wd} depois das Cinzas" if week == 0 else f"{wd} da {week}ª semana da Quaresma"
        elif season == "pascoa":
            name = f"{wd} da {week}ª semana da Páscoa"
        elif season == "natal":
            if d.month == 12:
                name = f"{d.day} de dezembro — {wd} da Oitava do Natal"
            else:
                name = f"{wd} do Tempo do Natal"
        else:
            name = wd
        return _Cel(name, "feria", color, P_FERIA)


def get_calendar() -> LiturgicalCalendar:
    return RomanBrazilCalendar()
