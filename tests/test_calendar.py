from datetime import date

import pytest

from app.services.calendar import RomanBrazilCalendar, easter

cal = RomanBrazilCalendar()


@pytest.mark.parametrize(
    "year,expected",
    [
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
    ],
)
def test_easter(year: int, expected: date) -> None:
    assert easter(year) == expected


def test_pascoa() -> None:
    i = cal.day(date(2026, 4, 5))
    assert (i.season, i.color, i.rank) == ("pascoa", "branco", "solenidade")
    assert i.week == 1
    assert cal.day(date(2026, 4, 4)).season == "triduo"  # Sábado Santo ainda é Tríduo
    assert "Páscoa" in i.celebration


def test_cinzas() -> None:
    i = cal.day(date(2026, 2, 18))
    assert i.celebration == "Quarta-feira de Cinzas"
    assert (i.season, i.color) == ("quaresma", "roxo")


def test_pentecostes() -> None:
    i = cal.day(date(2026, 5, 24))
    assert i.celebration == "Domingo de Pentecostes"
    assert i.color == "vermelho"


def test_advento() -> None:
    i = cal.day(date(2026, 11, 29))
    assert i.season == "advento" and i.week == 1 and i.color == "roxo"
    assert i.cycle_sunday == "B"
    gaudete = cal.day(date(2026, 12, 13))
    assert gaudete.color == "rosa"


def test_natal() -> None:
    i = cal.day(date(2026, 12, 25))
    assert (i.season, i.rank, i.color) == ("natal", "solenidade", "branco")


def test_aparecida_brasil() -> None:
    i = cal.day(date(2026, 10, 12))
    assert "Aparecida" in i.celebration and i.rank == "solenidade"
    assert i.season == "comum" and i.color == "branco"


def test_aparecida_vence_domingo_comum() -> None:
    # 12/10/2025 é domingo
    assert "Aparecida" in cal.day(date(2025, 10, 12)).celebration


def test_tempo_comum_semanas() -> None:
    assert cal.day(date(2026, 11, 22)).celebration.startswith("Nosso Senhor Jesus Cristo, Rei")
    assert cal.day(date(2026, 11, 16)).week == 33
    assert cal.day(date(2026, 1, 12)).week == 1
    assert cal.day(date(2026, 1, 18)).celebration == "2º Domingo do Tempo Comum"


def test_ciclos() -> None:
    assert cal.day(date(2026, 3, 1)).cycle_sunday == "A"
    assert cal.day(date(2026, 3, 1)).cycle_weekday == "II"
    assert cal.day(date(2027, 3, 1)).cycle_sunday == "B"
    assert cal.day(date(2027, 3, 1)).cycle_weekday == "I"


def test_epifania_ascensao_brasil() -> None:
    assert "Epifania" in cal.day(date(2026, 1, 4)).celebration
    assert "Ascensão" in cal.day(date(2026, 5, 17)).celebration
    assert "Corpus Christi" in cal.day(date(2026, 6, 4)).celebration


def test_sao_jose_domingo_quaresma_transfere() -> None:
    # 19/03/2028 cai num domingo da Quaresma -> segunda 20
    assert "São José" in cal.day(date(2028, 3, 20)).celebration
    assert "São José" not in cal.day(date(2028, 3, 19)).celebration


def test_memoria_vira_facultativa_na_quaresma() -> None:
    i = cal.day(date(2026, 3, 17))  # São Patrício, facultativa de qualquer modo
    assert i.rank == "memoria_facultativa"
    j = cal.day(date(2026, 3, 4))
    assert j.season == "quaresma"


def test_sem_memoria_na_semana_santa() -> None:
    assert cal.day(date(2026, 4, 1)).celebration == "Quarta-feira Santa"


def test_todos_os_dias_de_varios_anos_sao_validos() -> None:
    d = date(2024, 1, 1)
    seen = set()
    while d.year < 2032:
        i = cal.day(d)
        assert i.color in {"verde", "roxo", "branco", "vermelho", "rosa", "preto"}
        assert i.celebration
        seen.add(i.season)
        d = date.fromordinal(d.toordinal() + 1)
    assert seen == {"advento", "natal", "comum", "quaresma", "triduo", "pascoa"}


def test_memoria_facultativa_mantem_a_cor_do_tempo() -> None:
    quaresma = cal.day(date(2026, 3, 17))  # São Patrício, dentro da Quaresma
    assert quaresma.rank == "memoria_facultativa" and quaresma.color == "roxo"
    comum = cal.day(date(2026, 1, 20))  # São Sebastião, facultativa no Tempo Comum
    assert comum.rank == "memoria_facultativa" and comum.color == "verde"
    obrigatoria = cal.day(date(2026, 1, 21))  # Santa Inês: memória obrigatória mantém a cor própria
    assert obrigatoria.color == "vermelho"


def test_calendario_geral_mais_completo() -> None:
    i = cal.day(date(2026, 11, 17))
    assert i.celebration.startswith("Santa Isabel da Hungria") and i.rank == "memoria"
    assert cal.day(date(2026, 7, 22)).rank == "festa"  # Santa Maria Madalena
    assert cal.day(date(2026, 9, 26)).rank == "memoria_facultativa"  # Cosme e Damião
    # nada colide com a Semana Santa: memória obrigatória some no Tríduo/Semana Santa
    assert cal.day(date(2026, 4, 2)).season == "triduo"
