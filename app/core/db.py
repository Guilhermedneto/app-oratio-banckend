from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.dburl import prepare_database_url

_settings = get_settings()
_url, _connect_args = prepare_database_url(_settings.database_url)

# statement_cache_size=0 (obrigatório atrás do pooler do Neon) e ssl vêm de prepare_database_url.
engine = create_async_engine(
    _url,
    connect_args=_connect_args,
    poolclass=NullPool if _settings.null_pool else None,
    pool_recycle=240,  # recicla antes do Neon/pgbouncer derrubar conexões ociosas
    pool_pre_ping=False,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
