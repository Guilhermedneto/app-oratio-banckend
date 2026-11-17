import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.core.ratelimit import rate_limit
from app.routers.deps import CurrentUser, Sender, Session
from app.schemas.api import (
    NewRequestsOut,
    PrayedOut,
    PrayerCommentIn,
    PrayerCommentOut,
    PrayerFeedOut,
    PrayerRequestIn,
    PrayerRequestOut,
)
from app.services import community as svc

router = APIRouter(prefix="/comunidade", tags=["comunidade"])


@router.get("/pedidos", response_model=PrayerFeedOut)
async def feed(
    user: CurrentUser,
    s: Session,
    before: datetime | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    mine: bool = False,
) -> PrayerFeedOut:
    return await svc.feed(s, user, before, limit, mine)


@router.post(
    "/pedidos",
    response_model=PrayerRequestOut,
    status_code=201,
    dependencies=[Depends(rate_limit("pedido"))],
)
async def criar(
    body: PrayerRequestIn,
    user: CurrentUser,
    s: Session,
    tasks: BackgroundTasks,
    sender: Sender,
) -> PrayerRequestOut:
    out, rid = await svc.create_request(s, user, body.text, body.anonymous)
    tasks.add_task(svc.notify_new_request, rid, user.id, sender)
    return out


@router.delete("/pedidos/{rid}", status_code=204)
async def remover(rid: uuid.UUID, user: CurrentUser, s: Session) -> None:
    await svc.delete_request(s, user, rid)


@router.put("/pedidos/{rid}/oracao", response_model=PrayedOut)
async def orei(rid: uuid.UUID, user: CurrentUser, s: Session) -> PrayedOut:
    return await svc.set_prayed(s, user, rid, True)


@router.delete("/pedidos/{rid}/oracao", response_model=PrayedOut)
async def desmarcar(rid: uuid.UUID, user: CurrentUser, s: Session) -> PrayedOut:
    return await svc.set_prayed(s, user, rid, False)


@router.get("/pedidos/{rid}/comentarios", response_model=list[PrayerCommentOut])
async def comentarios(rid: uuid.UUID, user: CurrentUser, s: Session) -> list[PrayerCommentOut]:
    return await svc.list_comments(s, user, rid)


@router.post(
    "/pedidos/{rid}/comentarios",
    response_model=PrayerCommentOut,
    status_code=201,
    dependencies=[Depends(rate_limit("comentario"))],
)
async def comentar(
    rid: uuid.UUID, body: PrayerCommentIn, user: CurrentUser, s: Session
) -> PrayerCommentOut:
    return await svc.add_comment(s, user, rid, body.text)


@router.delete("/comentarios/{cid}", status_code=204)
async def remover_comentario(cid: uuid.UUID, user: CurrentUser, s: Session) -> None:
    await svc.delete_comment(s, user, cid)


@router.get("/novos", response_model=NewRequestsOut)
async def novos(user: CurrentUser, s: Session) -> NewRequestsOut:
    return await svc.new_since_last_visit(s, user)


@router.post("/visto", status_code=204)
async def visto(user: CurrentUser, s: Session) -> None:
    await svc.mark_seen(s, user)
