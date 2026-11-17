import uuid

from fastapi import APIRouter

from app.repositories import content as repo
from app.routers.deps import CurrentManager, Session
from app.schemas.api import CategoryIn, CategoryOut, ContentIn, ContentOut
from app.services import content as svc

router = APIRouter(prefix="/gestor", tags=["gestor"])


@router.get("/conteudos", response_model=list[ContentOut])
async def listar(_: CurrentManager, s: Session):  # type: ignore[no-untyped-def]
    return await repo.list_contents(s, only_published=False)


@router.post("/conteudos", response_model=ContentOut, status_code=201)
async def criar(body: ContentIn, user: CurrentManager, s: Session):  # type: ignore[no-untyped-def]
    return await svc.create_content(s, body, user)


@router.put("/conteudos/{cid}", response_model=ContentOut)
async def editar(cid: uuid.UUID, body: ContentIn, _: CurrentManager, s: Session):  # type: ignore[no-untyped-def]
    return await svc.update_content(s, cid, body)


@router.delete("/conteudos/{cid}", status_code=204)
async def excluir(cid: uuid.UUID, _: CurrentManager, s: Session) -> None:
    await svc.delete_content(s, cid)


@router.post("/categorias", response_model=CategoryOut, status_code=201)
async def criar_categoria(body: CategoryIn, _: CurrentManager, s: Session):  # type: ignore[no-untyped-def]
    return await svc.create_category(s, body.name)


@router.delete("/categorias/{cid}", status_code=204)
async def excluir_categoria(cid: uuid.UUID, _: CurrentManager, s: Session) -> None:
    await svc.delete_category(s, cid)
