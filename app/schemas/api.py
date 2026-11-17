import uuid
from datetime import date, datetime, time
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

Theme = Literal["auto", "claro", "escuro", "sepia"]
MysterySet = Annotated[str, StringConstraints(min_length=1, max_length=60, pattern=r"^[a-z0-9-]+$")]
ItemType = Literal["oracao", "novena", "rito", "reflexao"]
Slug = Annotated[str, StringConstraints(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GoogleIn(BaseModel):
    id_token: str = Field(min_length=10)


class UserOut(ORM):
    id: uuid.UUID
    email: str
    name: str
    role: Literal["user", "manager"] = "user"


class SettingsOut(ORM):
    theme: Theme
    font_scale: float
    notify_time: time | None
    timezone: str
    rite_prefs: dict[str, Any]
    notify_community: bool = True


class SettingsPatch(BaseModel):
    theme: Theme | None = None
    font_scale: float | None = Field(default=None, ge=0.8, le=1.6)
    notify_time: time | None = None
    clear_notify_time: bool = False
    timezone: str | None = Field(default=None, max_length=64)
    rite_prefs: dict[str, Any] | None = None
    notify_community: bool | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut


class MeOut(BaseModel):
    user: UserOut
    settings: SettingsOut
    rosary_streak: int


# ---- liturgia
class ReadingOut(ORM):
    kind: str
    reference: str
    title: str
    text: str


class PrayerOut(BaseModel):
    kind: str
    title: str
    text: str


class LiturgyDayOut(BaseModel):
    date: date
    season: str
    season_label: str
    week: int | None
    color: str
    celebration: str
    rank: str
    cycle_sunday: str
    cycle_weekday: str
    status: Literal["ok", "partial"]
    source: str | None
    credits: str | None
    readings: list[ReadingOut]
    prayers: list[PrayerOut] = []


class NovenaSuggestionOut(BaseModel):
    slug: str
    start: date
    feast: date


# ---- pessoal
class NovenaIn(BaseModel):
    novena_slug: Slug
    started_on: date
    current_day: int = Field(ge=1, le=9)
    completed: bool = False


class NovenaOut(ORM):
    novena_slug: str
    started_on: date
    current_day: int
    completed_at: datetime | None


class RosaryIn(BaseModel):
    client_id: uuid.UUID
    date: date
    mystery_set: MysterySet
    completed: bool = True


class RosaryOut(BaseModel):
    streak: int


class FavoriteIn(BaseModel):
    item_type: ItemType
    item_slug: Slug


class FavoriteOut(ORM):
    item_type: str
    item_slug: str
    created_at: datetime


class IntentionIn(BaseModel):
    id: uuid.UUID | None = None
    text: str = Field(min_length=1, max_length=2000)


class IntentionPatch(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    answered: bool | None = None


class IntentionOut(ORM):
    id: uuid.UUID
    text: str
    created_at: datetime
    answered_at: datetime | None


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=100)


class PushSubscribeIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000)
    keys: PushKeys


# ---- conteúdo gerido
ContentKind = Literal[
    "oracao", "texto", "reflexao", "rito", "terco", "hora", "santo", "novena", "misterio"
]


class CategoryOut(ORM):
    id: uuid.UUID
    slug: str
    name: str


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class ContentIn(BaseModel):
    slug: str | None = Field(default=None, max_length=100)
    data: dict[str, Any] | None = None
    kind: ContentKind
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=60)
    body: str = Field(min_length=1, max_length=20000)
    author: str | None = Field(default=None, max_length=200)
    origin: str | None = Field(default=None, max_length=300)
    source_url: str | None = Field(default=None, max_length=500)
    published: bool = True


class ContentOut(ORM):
    id: uuid.UUID
    slug: str
    kind: ContentKind
    title: str
    category: str
    body: str
    author: str | None
    origin: str | None
    source_url: str | None
    data: dict[str, Any] | None
    published: bool
    updated_at: datetime


# ---- comunidade
class PrayerRequestIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    anonymous: bool = False


class PrayerRequestOut(BaseModel):
    id: uuid.UUID
    text: str
    author_name: str | None
    mine: bool
    created_at: datetime
    prayed_count: int
    comment_count: int
    i_prayed: bool


class PrayerFeedOut(BaseModel):
    items: list[PrayerRequestOut]
    next_before: datetime | None


class PrayerCommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class PrayerCommentOut(BaseModel):
    id: uuid.UUID
    text: str
    author_name: str
    mine: bool
    created_at: datetime


class PrayedOut(BaseModel):
    prayed_count: int
    i_prayed: bool


class NewRequestsOut(BaseModel):
    count: int
    latest_id: uuid.UUID | None
    latest_text: str | None
