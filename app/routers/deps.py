from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.integrations.base import LiturgySource
from app.integrations.registry import build_sources
from app.integrations.webpush import PushSender, WebPushSender
from app.models import User
from app.repositories import users as users_repo
from app.services.auth import user_id_from_token

Session = Annotated[AsyncSession, Depends(get_session)]


def get_sources() -> list[LiturgySource]:
    return build_sources()


async def current_user(session: Session, authorization: str | None = Header(default=None)) -> User:
    scheme, _, token = (authorization or "").partition(" ")
    uid = user_id_from_token(token) if scheme.lower() == "bearer" else None
    user = await users_repo.get_by_id(session, uid) if uid else None
    if user is None:
        raise HTTPException(401, "Não autenticado", headers={"WWW-Authenticate": "Bearer"})
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def current_manager(user: CurrentUser) -> User:
    if user.role != "manager":
        raise HTTPException(403, "Acesso restrito ao gestor")
    return user


CurrentManager = Annotated[User, Depends(current_manager)]


def get_push_sender() -> PushSender:
    return WebPushSender()


Sender = Annotated[PushSender, Depends(get_push_sender)]
