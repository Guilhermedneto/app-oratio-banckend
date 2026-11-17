import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, ManagedContent


async def list_categories(s: AsyncSession) -> list[Category]:
    return list((await s.execute(select(Category).order_by(Category.name))).scalars())


async def get_category(s: AsyncSession, cid: uuid.UUID) -> Category | None:
    return await s.get(Category, cid)


async def category_by_slug_or_name(s: AsyncSession, slug: str, name: str) -> Category | None:
    q = select(Category).where(
        (Category.slug == slug) | (func.lower(Category.name) == name.lower())
    )
    return (await s.execute(q)).scalars().first()


async def create_category(s: AsyncSession, slug: str, name: str) -> Category:
    row = Category(slug=slug, name=name)
    s.add(row)
    await s.flush()
    await s.refresh(row)
    return row


async def category_in_use(s: AsyncSession, slug: str) -> bool:
    q = select(func.count()).where(ManagedContent.category == slug)
    return bool((await s.execute(q)).scalar_one())


async def delete_category(s: AsyncSession, row: Category) -> None:
    await s.execute(delete(Category).where(Category.id == row.id))


async def list_contents(s: AsyncSession, only_published: bool) -> list[ManagedContent]:
    q = select(ManagedContent).order_by(ManagedContent.title)
    if only_published:
        q = q.where(ManagedContent.published.is_(True))
    return list((await s.execute(q)).scalars())


async def get_content(s: AsyncSession, cid: uuid.UUID) -> ManagedContent | None:
    return await s.get(ManagedContent, cid)


async def slug_exists(s: AsyncSession, slug: str) -> bool:
    q = select(func.count()).where(ManagedContent.slug == slug)
    return bool((await s.execute(q)).scalar_one())


async def add_content(s: AsyncSession, row: ManagedContent) -> ManagedContent:
    s.add(row)
    await s.flush()
    await s.refresh(row)
    return row


async def delete_content(s: AsyncSession, row: ManagedContent) -> None:
    await s.delete(row)
    await s.flush()
