import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.integrations import google as google_integration
from app.models import User
from app.repositories import users as repo


class AuthError(HTTPException):
    def __init__(self, detail: str = "Credenciais inválidas") -> None:
        super().__init__(status_code=401, detail=detail)


async def _issue(s: AsyncSession, user: User) -> tuple[str, str]:
    if user.email.lower() in get_settings().manager_list and user.role != "manager":
        user.role = "manager"
    raw, hashed = security.new_refresh_token()
    expires = datetime.now(UTC) + timedelta(days=get_settings().refresh_days)
    await repo.add_refresh(s, user.id, hashed, expires)
    await s.commit()
    return security.create_access_token(str(user.id)), raw


async def register(s: AsyncSession, email: str, password: str, name: str) -> tuple[User, str, str]:
    email = email.lower()
    if await repo.get_by_email(s, email):
        raise HTTPException(409, "E-mail já cadastrado")
    try:
        user = await repo.create_user(
            s, email, name.strip(), security.hash_password(password), None
        )
    except IntegrityError as exc:
        await s.rollback()
        raise HTTPException(409, "E-mail já cadastrado") from exc
    access, refresh = await _issue(s, user)
    return user, access, refresh


async def login(s: AsyncSession, email: str, password: str) -> tuple[User, str, str]:
    user = await repo.get_by_email(s, email.lower())
    ok = security.verify_password(password, user.password_hash if user else None)
    if user is None or not ok:
        raise AuthError()
    access, refresh = await _issue(s, user)
    return user, access, refresh


async def refresh(s: AsyncSession, raw: str | None) -> tuple[User, str, str]:
    if not raw:
        raise AuthError("Sessão expirada")
    token = await repo.get_refresh(s, security.hash_token(raw))
    if token is None:
        raise AuthError("Sessão expirada")
    if token.revoked_at is not None:
        await repo.revoke_all_refresh(s, token.user_id)
        await s.commit()
        raise AuthError("Sessão encerrada")
    if token.expires_at <= datetime.now(UTC):
        raise AuthError("Sessão expirada")
    user = await repo.get_by_id(s, token.user_id)
    if user is None:
        raise AuthError("Sessão expirada")
    await repo.revoke_refresh(s, token)
    access, new_raw = await _issue(s, user)
    return user, access, new_raw


async def logout(s: AsyncSession, raw: str | None) -> None:
    if not raw:
        return
    token = await repo.get_refresh(s, security.hash_token(raw))
    if token is not None and token.revoked_at is None:
        await repo.revoke_refresh(s, token)
        await s.commit()


async def google_login(s: AsyncSession, id_token: str) -> tuple[User, str, str]:
    client_id = get_settings().google_client_id
    if not client_id:
        raise HTTPException(503, "Login com Google não está configurado")
    try:
        info = await google_integration.verify_google_token(id_token, client_id)
    except ValueError as exc:
        raise AuthError("Token do Google inválido") from exc
    sub, email = str(info.get("sub", "")), str(info.get("email", "")).lower()
    if not sub or not email or info.get("email_verified") is False:
        raise AuthError("Token do Google inválido")
    user = await repo.get_by_google_sub(s, sub)
    if user is None:
        user = await repo.get_by_email(s, email)
        if user is not None:
            user.google_sub = sub
        else:
            name = str(info.get("name") or email.split("@")[0])[:120]
            user = await repo.create_user(s, email, name, None, sub)
    access, refresh_raw = await _issue(s, user)
    return user, access, refresh_raw


def user_id_from_token(token: str) -> uuid.UUID | None:
    sub = security.decode_access_token(token)
    try:
        return uuid.UUID(sub) if sub else None
    except ValueError:
        return None
