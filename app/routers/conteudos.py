import hashlib
import json

from fastapi import APIRouter, Request, Response
from fastapi.encoders import jsonable_encoder

from app.repositories import content as repo
from app.routers.deps import Session
from app.schemas.api import CategoryOut, ContentOut

router = APIRouter(tags=["conteudos"])
CACHE = "no-cache"  # sempre revalida (ETag -> 304): o gestor vê o novo conteúdo na hora


def _respond(request: Request, payload: object) -> Response:
    body = json.dumps(jsonable_encoder(payload), ensure_ascii=False, separators=(",", ":")).encode()
    etag = '"' + hashlib.sha1(body).hexdigest() + '"'  # noqa: S324 (não é segurança)
    headers = {"ETag": etag, "Cache-Control": CACHE}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="application/json", headers=headers)


@router.get("/conteudos", response_model=list[ContentOut])
async def conteudos(request: Request, s: Session) -> Response:
    rows = await repo.list_contents(s, only_published=True)
    return _respond(request, [ContentOut.model_validate(r) for r in rows])


@router.get("/categorias", response_model=list[CategoryOut])
async def categorias(request: Request, s: Session) -> Response:
    rows = await repo.list_categories(s)
    return _respond(request, [CategoryOut.model_validate(r) for r in rows])
