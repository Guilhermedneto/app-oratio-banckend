"""Normaliza a DATABASE_URL para o asyncpg (aceita a string pronta do Neon, Render, Heroku etc.)."""

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_SSL_ON = {"require", "verify-ca", "verify-full", "true", "1"}
_DROP = {"sslmode", "ssl", "channel_binding", "sslrootcert", "options"}


def prepare_database_url(url: str) -> tuple[str, dict[str, Any]]:
    """Devolve (url para o SQLAlchemy async, connect_args).

    - `postgres://` e `postgresql://` viram `postgresql+asyncpg://`;
    - `sslmode=require` (padrão do Neon) vira `ssl=True`, pois o asyncpg não entende `sslmode`;
    - `statement_cache_size=0` é obrigatório atrás do pooler (pgbouncer) do Neon.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix) :]
            break
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    wants_ssl = any(k in ("sslmode", "ssl") and v.lower() in _SSL_ON for k, v in query)
    kept = [(k, v) for k, v in query if k not in _DROP]
    clean = urlunsplit(parts._replace(query=urlencode(kept)))
    args: dict[str, Any] = {"statement_cache_size": 0}
    if wants_ssl:
        args["ssl"] = True
    return clean, args
