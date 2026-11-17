import uuid

from fastapi import APIRouter, HTTPException, Response

from app.repositories import personal as repo
from app.repositories import users as users_repo
from app.routers.deps import CurrentUser, Session
from app.schemas.api import (
    FavoriteIn,
    FavoriteOut,
    IntentionIn,
    IntentionOut,
    IntentionPatch,
    ItemType,
    MeOut,
    NovenaIn,
    NovenaOut,
    PushSubscribeIn,
    RosaryIn,
    RosaryOut,
    SettingsOut,
    SettingsPatch,
    Slug,
    UserOut,
)
from app.services import personal as svc

router = APIRouter(tags=["usuario"])


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser, s: Session) -> MeOut:
    settings = await users_repo.get_settings(s, user.id)
    return MeOut(
        user=UserOut.model_validate(user),
        settings=SettingsOut.model_validate(settings),
        rosary_streak=await svc.streak_for(s, user.id),
    )


@router.patch("/me/settings", response_model=SettingsOut)
async def patch_settings(body: SettingsPatch, user: CurrentUser, s: Session):  # type: ignore[no-untyped-def]
    return await svc.patch_settings(s, user.id, body)


@router.get("/me/export")
async def export(user: CurrentUser, s: Session) -> dict:  # type: ignore[type-arg]
    return await svc.export_data(s, user.id)


@router.delete("/me", status_code=204)
async def delete_me(user: CurrentUser, s: Session, resp: Response) -> None:
    await svc.delete_account(s, user.id)
    resp.delete_cookie("oratio_refresh", path="/")


@router.get("/me/novenas", response_model=list[NovenaOut])
async def list_novenas(user: CurrentUser, s: Session):  # type: ignore[no-untyped-def]
    return await repo.list_novenas(s, user.id)


@router.put("/me/novenas", response_model=NovenaOut)
async def put_novena(body: NovenaIn, user: CurrentUser, s: Session):  # type: ignore[no-untyped-def]
    return await svc.put_novena(s, user.id, body)


@router.post("/me/rosario", response_model=RosaryOut, status_code=201)
async def post_rosary(body: RosaryIn, user: CurrentUser, s: Session) -> RosaryOut:
    return RosaryOut(streak=await svc.add_rosary(s, user.id, body))


@router.get("/me/favoritos", response_model=list[FavoriteOut])
async def list_favorites(user: CurrentUser, s: Session):  # type: ignore[no-untyped-def]
    return await repo.list_favorites(s, user.id)


@router.post("/me/favoritos", response_model=list[FavoriteOut], status_code=201)
async def add_favorite(body: FavoriteIn, user: CurrentUser, s: Session):  # type: ignore[no-untyped-def]
    await repo.add_favorite(s, user.id, body.item_type, body.item_slug)
    await s.commit()
    return await repo.list_favorites(s, user.id)


@router.delete("/me/favoritos/{item_type}/{item_slug}", status_code=204)
async def remove_favorite(
    item_type: ItemType, item_slug: Slug, user: CurrentUser, s: Session
) -> None:
    await repo.remove_favorite(s, user.id, item_type, item_slug)
    await s.commit()


@router.get("/me/intencoes", response_model=list[IntentionOut])
async def list_intentions(user: CurrentUser, s: Session):  # type: ignore[no-untyped-def]
    return await repo.list_intentions(s, user.id)


@router.post("/me/intencoes", response_model=IntentionOut, status_code=201)
async def create_intention(body: IntentionIn, user: CurrentUser, s: Session):  # type: ignore[no-untyped-def]
    try:
        row = await repo.create_intention(s, user.id, body.text.strip(), body.id)
    except ValueError as exc:
        raise HTTPException(409, "Identificador já utilizado") from exc
    await s.commit()
    return row


@router.patch("/me/intencoes/{iid}", response_model=IntentionOut)
async def patch_intention(iid: uuid.UUID, body: IntentionPatch, user: CurrentUser, s: Session):  # type: ignore[no-untyped-def]
    return await svc.patch_intention(s, user.id, iid, body)


@router.delete("/me/intencoes/{iid}", status_code=204)
async def delete_intention(iid: uuid.UUID, user: CurrentUser, s: Session) -> None:
    row = await repo.get_intention(s, user.id, iid)
    if row is None:
        raise HTTPException(404, "Intenção não encontrada")
    await repo.delete_intention(s, row)
    await s.commit()


@router.post("/push/subscribe", status_code=201)
async def subscribe(body: PushSubscribeIn, user: CurrentUser, s: Session) -> dict[str, bool]:
    await repo.upsert_subscription(s, user.id, body.endpoint, body.keys.p256dh, body.keys.auth)
    await s.commit()
    return {"ok": True}


@router.post("/push/test")
async def push_test(user: CurrentUser, s: Session) -> dict[str, int]:
    """Envia agora um lembrete de teste para os aparelhos assinados do usuário."""
    from app.core.config import get_settings
    from app.integrations.webpush import PushGone, Subscription, WebPushSender

    if not get_settings().vapid_private_key:
        raise HTTPException(503, "Chaves VAPID não configuradas no servidor")
    sender = WebPushSender()
    sent = 0
    for sub in await repo.list_subscriptions(s, user.id):
        try:
            await sender.send(
                Subscription(sub.endpoint, sub.p256dh, sub.auth),
                {"title": "Oratio", "body": "Lembrete de teste: tudo certo!", "url": "/"},
            )
            sent += 1
        except PushGone:
            await repo.delete_subscription_by_endpoint(s, sub.endpoint)
        except Exception as exc:
            raise HTTPException(502, f"Falha ao enviar: {exc}") from exc
    await s.commit()
    return {"sent": sent}


@router.delete("/push/subscribe", status_code=204)
async def unsubscribe(endpoint: str, user: CurrentUser, s: Session) -> None:
    await repo.delete_subscription(s, user.id, endpoint)
    await s.commit()
