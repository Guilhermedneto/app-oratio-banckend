import re
import secrets
import unicodedata
import uuid
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, ManagedContent, User
from app.repositories import content as repo
from app.schemas.api import ContentIn

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_MMDD = re.compile(r"^(\d{2})-(\d{2})$")


def slugify(text: str) -> str:
    base = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base[:50] or "item"


def _check_category(slug: str) -> str:
    slug = slug.strip().lower()
    if not _SLUG.match(slug):
        raise HTTPException(422, "Categoria inválida")
    return slug


async def create_category(s: AsyncSession, name: str) -> Category:
    name = name.strip()
    slug = slugify(name)
    if await repo.category_by_slug_or_name(s, slug, name):
        raise HTTPException(409, "Já existe uma categoria com esse nome")
    row = await repo.create_category(s, slug, name)
    await s.commit()
    return row


async def delete_category(s: AsyncSession, cid: uuid.UUID) -> None:
    row = await repo.get_category(s, cid)
    if row is None:
        raise HTTPException(404, "Categoria não encontrada")
    if await repo.category_in_use(s, row.slug):
        raise HTTPException(409, "Categoria em uso por conteúdos")
    await repo.delete_category(s, row)
    await s.commit()


def _text(v: Any, limit: int) -> str:
    return str(v or "").strip()[:limit]


def validate_data(kind: str, data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Valida e normaliza os dados estruturados de cada tipo (santo, novena, mistérios)."""
    data = data or {}
    if kind == "santo":
        m = _MMDD.match(str(data.get("date", "")))
        if not m:
            raise HTTPException(422, "Informe o dia da festa do santo (mês e dia)")
        try:
            date(2024, int(m.group(1)), int(m.group(2)))  # 2024 é bissexto: aceita 29/02
        except ValueError as exc:
            raise HTTPException(422, "Data da festa inválida") from exc
        return {"date": m.group(0)}
    if kind == "novena":
        days = data.get("days")
        if not isinstance(days, list) or len(days) != 9:
            raise HTTPException(422, "A novena precisa de exatamente 9 dias")
        out = []
        for i, d in enumerate(days, start=1):
            title, text = _text((d or {}).get("title"), 200), _text((d or {}).get("text"), 5000)
            if not text:
                raise HTTPException(422, f"Dia {i} da novena sem texto")
            out.append({"title": title or f"Dia {i}", "text": text})
        return {"days": out, "final_prayer": _text(data.get("final_prayer"), 5000)}
    if kind == "misterio":
        mys = data.get("mysteries")
        if not isinstance(mys, list) or len(mys) != 5:
            raise HTTPException(422, "O terço precisa de exatamente 5 mistérios")
        out = []
        for i, m in enumerate(mys, start=1):
            title = _text((m or {}).get("title"), 200)
            if not title:
                raise HTTPException(422, f"Mistério {i} sem título")
            out.append(
                {
                    "title": title,
                    "fruit": _text((m or {}).get("fruit"), 200),
                    "meditation": _text((m or {}).get("meditation"), 3000),
                }
            )
        weekdays = data.get("weekdays") or []
        if not isinstance(weekdays, list) or any(
            not isinstance(w, int) or isinstance(w, bool) or not 0 <= w <= 6 for w in weekdays
        ):
            raise HTTPException(422, "Dias da semana inválidos (0 = domingo … 6 = sábado)")
        return {"mysteries": out, "weekdays": sorted(set(weekdays))}
    return None


async def _unique_slug(s: AsyncSession, title: str) -> str:
    base = slugify(title)
    slug = base
    while await repo.slug_exists(s, slug):
        slug = f"{base}-{secrets.token_hex(2)}"
    return slug


async def _chosen_slug(
    s: AsyncSession, wanted: str | None, current: ManagedContent | None
) -> str | None:
    if not wanted or not wanted.strip():
        return None
    slug = wanted.strip().lower()
    if not _SLUG.match(slug) or len(slug) > 100:
        raise HTTPException(422, "Identificador inválido (use letras minúsculas, números e hífens)")
    if current is not None and current.slug == slug:
        return slug
    if await repo.slug_exists(s, slug):
        raise HTTPException(409, "Já existe um conteúdo com esse identificador")
    return slug


def _clean(v: str | None) -> str | None:
    v = (v or "").strip()
    return v or None


async def create_content(s: AsyncSession, body: ContentIn, user: User) -> ManagedContent:
    data = validate_data(body.kind, body.data)
    slug = await _chosen_slug(s, body.slug, None) or await _unique_slug(s, body.title)
    row = ManagedContent(
        slug=slug,
        kind=body.kind,
        title=body.title.strip(),
        category=_check_category(body.category),
        body=body.body.strip(),
        author=_clean(body.author),
        origin=_clean(body.origin),
        source_url=_clean(body.source_url),
        data=data,
        published=body.published,
        created_by=user.id,
    )
    out = await repo.add_content(s, row)
    await s.commit()
    return out


async def update_content(s: AsyncSession, cid: uuid.UUID, body: ContentIn) -> ManagedContent:
    row = await repo.get_content(s, cid)
    if row is None:
        raise HTTPException(404, "Conteúdo não encontrado")
    data = validate_data(body.kind, body.data)
    slug = await _chosen_slug(s, body.slug, row)
    if slug:
        row.slug = slug
    row.kind = body.kind
    row.title = body.title.strip()
    row.category = _check_category(body.category)
    row.body = body.body.strip()
    row.author = _clean(body.author)
    row.origin = _clean(body.origin)
    row.source_url = _clean(body.source_url)
    row.data = data
    row.published = body.published
    await s.commit()
    await s.refresh(row)
    return row


async def delete_content(s: AsyncSession, cid: uuid.UUID) -> None:
    row = await repo.get_content(s, cid)
    if row is None:
        raise HTTPException(404, "Conteúdo não encontrado")
    await repo.delete_content(s, row)
    await s.commit()
