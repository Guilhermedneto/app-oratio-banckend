from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.routers import auth, comunidade, conteudos, gestor, liturgia, usuario


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Oratio API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "If-None-Match"],
    )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if settings.env != "dev":
            resp.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return resp

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Aquecimento: também acorda a conexão com o banco (Neon suspende quando ocioso)."""
        db = "ok"
        try:
            async with SessionLocal() as s:
                await s.execute(text("select 1"))
        except Exception:
            db = "unavailable"
        return {"status": "ok", "db": db}

    app.include_router(auth.router)
    app.include_router(liturgia.router)
    app.include_router(usuario.router)
    app.include_router(conteudos.router)
    app.include_router(gestor.router)
    app.include_router(comunidade.router)
    return app


app = create_app()
