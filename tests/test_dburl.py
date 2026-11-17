import pytest

from app.core.config import Settings, get_settings
from app.core.dburl import prepare_database_url


def test_string_do_neon_vira_asyncpg_com_ssl() -> None:
    url, args = prepare_database_url(
        "postgresql://user:pw@ep-cool-123-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    )
    assert url == "postgresql+asyncpg://user:pw@ep-cool-123-pooler.sa-east-1.aws.neon.tech/neondb"
    assert args == {"statement_cache_size": 0, "ssl": True}


@pytest.mark.parametrize("prefix", ["postgres://", "postgresql://", "postgresql+asyncpg://"])
def test_esquemas_aceitos(prefix: str) -> None:
    url, _ = prepare_database_url(f"{prefix}u:p@host:5432/db")
    assert url == "postgresql+asyncpg://u:p@host:5432/db"


def test_local_sem_ssl_e_preserva_outros_parametros() -> None:
    url, args = prepare_database_url("postgresql+asyncpg://oratio:oratio@localhost:5433/oratio")
    assert url.endswith("localhost:5433/oratio") and args == {"statement_cache_size": 0}
    url, args = prepare_database_url(
        "postgresql://u:p@h/db?sslmode=disable&application_name=oratio"
    )
    assert url == "postgresql+asyncpg://u:p@h/db?application_name=oratio"
    assert "ssl" not in args


def test_senha_com_caracteres_especiais_nao_e_alterada() -> None:
    url, _ = prepare_database_url("postgresql://u:p%40ss%2Fw@h/db?sslmode=require")
    assert url == "postgresql+asyncpg://u:p%40ss%2Fw@h/db"


def test_producao_exige_segredo_forte(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    try:
        monkeypatch.setenv("ENV", "prod")
        for bad in ("dev-secret-change-me-dev-secret-0000", "curto", ""):
            monkeypatch.setenv("JWT_SECRET", bad)
            get_settings.cache_clear()
            with pytest.raises(RuntimeError):
                get_settings()
        monkeypatch.setenv("JWT_SECRET", "x" * 40)
        get_settings.cache_clear()
        assert get_settings().env == "prod"
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        assert isinstance(get_settings(), Settings)
