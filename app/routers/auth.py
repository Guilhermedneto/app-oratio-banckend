from fastapi import APIRouter, Cookie, Depends, Response
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.ratelimit import rate_limit
from app.models import User
from app.routers.deps import Session
from app.schemas.api import GoogleIn, LoginIn, RegisterIn, TokenOut, UserOut
from app.services import auth as svc

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE = "oratio_refresh"


def _set_cookie(resp: Response, raw: str) -> None:
    s = get_settings()
    resp.set_cookie(
        COOKIE,
        raw,
        max_age=s.refresh_days * 86400,
        httponly=True,
        secure=s.secure_cookies,
        samesite="lax",
        path="/",
    )


def _out(resp: Response, user: User, access: str, raw: str) -> TokenOut:
    _set_cookie(resp, raw)
    return TokenOut(access_token=access, user=UserOut.model_validate(user))


@router.post(
    "/register",
    response_model=TokenOut,
    status_code=201,
    dependencies=[Depends(rate_limit("register"))],
)
async def register(body: RegisterIn, resp: Response, s: Session) -> TokenOut:
    return _out(resp, *await svc.register(s, body.email, body.password, body.name))


@router.post("/login", response_model=TokenOut, dependencies=[Depends(rate_limit("login"))])
async def login(body: LoginIn, resp: Response, s: Session) -> TokenOut:
    return _out(resp, *await svc.login(s, body.email, body.password))


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    resp: Response, s: Session, oratio_refresh: str | None = Cookie(default=None)
) -> TokenOut | JSONResponse:
    try:
        return _out(resp, *await svc.refresh(s, oratio_refresh))
    except svc.AuthError as exc:
        err = JSONResponse({"detail": exc.detail}, status_code=401)
        err.delete_cookie(COOKIE, path="/")
        return err


@router.post("/logout", status_code=204)
async def logout(
    resp: Response, s: Session, oratio_refresh: str | None = Cookie(default=None)
) -> None:
    await svc.logout(s, oratio_refresh)
    resp.delete_cookie(COOKIE, path="/")


@router.post("/google", response_model=TokenOut, dependencies=[Depends(rate_limit("google"))])
async def google(body: GoogleIn, resp: Response, s: Session) -> TokenOut:
    return _out(resp, *await svc.google_login(s, body.id_token))
