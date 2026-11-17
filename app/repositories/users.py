import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RefreshToken, User, UserSettings


async def get_by_email(s: AsyncSession, email: str) -> User | None:
    return (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def get_by_google_sub(s: AsyncSession, sub: str) -> User | None:
    return (await s.execute(select(User).where(User.google_sub == sub))).scalar_one_or_none()


async def get_by_id(s: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await s.get(User, user_id)


async def create_user(
    s: AsyncSession, email: str, name: str, password_hash: str | None, google_sub: str | None
) -> User:
    user = User(email=email, name=name, password_hash=password_hash, google_sub=google_sub)
    s.add(user)
    await s.flush()
    s.add(UserSettings(user_id=user.id))
    await s.flush()
    return user


async def get_settings(s: AsyncSession, user_id: uuid.UUID) -> UserSettings:
    row = await s.get(UserSettings, user_id)
    if row is None:
        row = UserSettings(user_id=user_id)
        s.add(row)
        await s.flush()
    return row


async def add_refresh(
    s: AsyncSession, user_id: uuid.UUID, token_hash: str, expires_at: datetime
) -> None:
    s.add(RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at))
    await s.flush()


async def get_refresh(s: AsyncSession, token_hash: str) -> RefreshToken | None:
    q = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    return (await s.execute(q)).scalar_one_or_none()


async def revoke_refresh(s: AsyncSession, token: RefreshToken) -> None:
    token.revoked_at = datetime.now(UTC)
    await s.flush()


async def revoke_all_refresh(s: AsyncSession, user_id: uuid.UUID) -> None:
    await s.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def delete_user(s: AsyncSession, user_id: uuid.UUID) -> None:
    await s.execute(delete(User).where(User.id == user_id))
