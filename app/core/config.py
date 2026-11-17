from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+asyncpg://oratio:oratio@localhost:5433/oratio"
    jwt_secret: str = "dev-secret-change-me-dev-secret-0000"
    jwt_access_min: int = 15
    refresh_days: int = 30
    google_client_id: str = ""
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@example.com"
    cors_origins: str = "http://localhost:5173"
    liturgy_sources: str = "railway"
    rate_limit_enabled: bool = True
    rate_limit_max: int = 10
    rate_limit_window_s: int = 60
    default_tz: str = "America/Sao_Paulo"
    null_pool: bool = False
    manager_emails: str = ""
    community_post_limit: int = 10
    community_post_window_s: int = 3600

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def manager_list(self) -> set[str]:
        return {e.strip().lower() for e in self.manager_emails.split(",") if e.strip()}

    @property
    def source_list(self) -> list[str]:
        return [s.strip() for s in self.liturgy_sources.split(",") if s.strip()]

    @property
    def secure_cookies(self) -> bool:
        return self.env != "dev"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.env == "prod" and (
        s.jwt_secret.startswith("dev-secret-change-me") or len(s.jwt_secret) < 32
    ):
        raise RuntimeError("JWT_SECRET deve ser definido em produção (mínimo de 32 caracteres)")
    return s
