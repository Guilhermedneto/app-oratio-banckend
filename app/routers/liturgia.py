import hashlib
import json
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder

from app.core.config import get_settings
from app.integrations.base import LiturgySource
from app.routers.deps import Session, get_sources
from app.schemas.api import LiturgyDayOut, NovenaSuggestionOut
from app.services import novena_dates
from app.services.liturgy import LiturgyService

router = APIRouter(tags=["liturgia"])
Sources = Annotated[list[LiturgySource], Depends(get_sources)]
CACHE = "public, max-age=300, stale-while-revalidate=3600"


def _respond(request: Request, payload: object) -> Response:
    body = json.dumps(jsonable_encoder(payload), ensure_ascii=False, separators=(",", ":")).encode()
    etag = '"' + hashlib.sha1(body).hexdigest() + '"'  # noqa: S324 (não é segurança)
    headers = {"ETag": etag, "Cache-Control": CACHE}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="application/json", headers=headers)


def _today(tz: str | None) -> date:
    name = tz or get_settings().default_tz
    try:
        return datetime.now(ZoneInfo(name)).date()
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(422, "Fuso horário inválido") from exc


@router.get("/liturgia/hoje", response_model=LiturgyDayOut)
async def hoje(request: Request, s: Session, sources: Sources, tz: str | None = None) -> Response:
    return _respond(request, await LiturgyService(s, sources).get_day(_today(tz)))


@router.get("/liturgia/semana", response_model=list[LiturgyDayOut])
async def semana(
    request: Request, s: Session, sources: Sources, de: date | None = None, tz: str | None = None
) -> Response:
    start = de or _today(tz)
    return _respond(request, await LiturgyService(s, sources).week(start))


@router.get("/liturgia/{data}", response_model=LiturgyDayOut)
async def por_data(data: str, request: Request, s: Session, sources: Sources) -> Response:
    try:
        d = date.fromisoformat(data)
    except ValueError as exc:
        raise HTTPException(422, "Data inválida; use AAAA-MM-DD") from exc
    if not (1970 <= d.year <= 2100):
        raise HTTPException(422, "Data fora do intervalo suportado")
    return _respond(request, await LiturgyService(s, sources).get_day(d))


@router.get("/novenas/sugestoes", response_model=list[NovenaSuggestionOut])
async def sugestoes(tz: str | None = Query(default=None)) -> list[NovenaSuggestionOut]:
    return novena_dates.suggestions(_today(tz))
