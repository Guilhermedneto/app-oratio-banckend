from fastapi import APIRouter

from app.routers.deps import CurrentUser
from app.schemas.api import PresenceOut
from app.services import presence

router = APIRouter(prefix="/presenca", tags=["presenca"])


@router.post("", response_model=PresenceOut)
async def avisar(user: CurrentUser) -> PresenceOut:
    return PresenceOut(online=presence.ping(user.id))


@router.get("", response_model=PresenceOut)
async def quantos(user: CurrentUser) -> PresenceOut:
    presence.ping(user.id)
    return PresenceOut(online=presence.count())
