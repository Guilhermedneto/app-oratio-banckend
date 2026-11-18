import uuid

import httpx

from app.services import presence

Headers = dict[str, str]


async def test_presenca_exige_login(client: httpx.AsyncClient) -> None:
    assert (await client.get("/presenca")).status_code == 401
    assert (await client.post("/presenca")).status_code == 401


async def test_conta_quem_avisou(client: httpx.AsyncClient, auth: Headers, user_b: Headers) -> None:
    presence.reset()
    assert (await client.post("/presenca", headers=auth)).json() == {"online": 1}
    assert (await client.post("/presenca", headers=auth)).json() == {"online": 1}
    assert (await client.post("/presenca", headers=user_b)).json() == {"online": 2}
    assert (await client.get("/presenca", headers=auth)).json() == {"online": 2}


def test_expira_depois_do_prazo() -> None:
    presence.reset()
    a, b = uuid.uuid4(), uuid.uuid4()
    presence.ping(a, now=0)
    assert presence.ping(b, now=100) == 2
    assert presence.count(now=130) == 1  # a passou de 120 s sem avisar
    assert presence.count(now=300) == 0
