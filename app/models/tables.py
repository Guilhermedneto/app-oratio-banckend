import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

TS = DateTime(timezone=True)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role in ('user','manager')", name="ck_user_role"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(
        String(10), default="user", server_default="user", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TS)


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        CheckConstraint("theme in ('auto','claro','escuro','sepia')", name="ck_settings_theme"),
        CheckConstraint("font_scale between 0.8 and 1.6", name="ck_settings_font"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    theme: Mapped[str] = mapped_column(String(10), default="auto", nullable=False)
    font_scale: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    notify_time: Mapped[time | None] = mapped_column(Time)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Sao_Paulo", nullable=False)
    rite_prefs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    notify_community: Mapped[bool] = mapped_column(
        default=True, server_default="true", nullable=False
    )
    community_seen_at: Mapped[datetime | None] = mapped_column(TS)


class LiturgicalDay(Base):
    __tablename__ = "liturgical_days"
    __table_args__ = (
        CheckConstraint(
            "season in ('advento','natal','comum','quaresma','triduo','pascoa')",
            name="ck_day_season",
        ),
        CheckConstraint(
            "color in ('verde','roxo','branco','vermelho','rosa','preto')", name="ck_day_color"
        ),
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    season: Mapped[str] = mapped_column(String(12), nullable=False)
    week: Mapped[int | None] = mapped_column(Integer)
    color: Mapped[str] = mapped_column(String(10), nullable=False)
    celebration: Mapped[str] = mapped_column(String(200), nullable=False)
    rank: Mapped[str] = mapped_column(String(24), nullable=False)
    cycle_sunday: Mapped[str] = mapped_column(String(1), nullable=False)
    cycle_weekday: Mapped[str] = mapped_column(String(2), nullable=False)
    source: Mapped[str | None] = mapped_column(String(40))
    fetched_at: Mapped[datetime | None] = mapped_column(TS)
    # None = ainda não coletado; [] = coletado sem orações
    prayers: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB)


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (
        CheckConstraint(
            "kind in ('primeira','salmo','segunda','aclamacao','evangelho')", name="ck_reading_kind"
        ),
        UniqueConstraint("date", "kind", name="uq_reading_date_kind"),
        Index("ix_readings_date", "date"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(ForeignKey("liturgical_days.date", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    reference: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(40), nullable=False)


class NovenaProgress(Base):
    __tablename__ = "novena_progress"
    __table_args__ = (
        CheckConstraint("current_day between 1 and 9", name="ck_novena_day"),
        UniqueConstraint("user_id", "novena_slug", "started_on", name="uq_novena_start"),
        Index("ix_novena_progress_user", "user_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    novena_slug: Mapped[str] = mapped_column(String(60), nullable=False)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    current_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    completed_at: Mapped[datetime | None] = mapped_column(TS)


class RosaryLog(Base):
    __tablename__ = "rosary_log"
    __table_args__ = (
        UniqueConstraint("user_id", "client_id", name="uq_rosary_client"),
        Index("ix_rosary_log_user_date", "user_id", "date"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    mystery_set: Mapped[str] = mapped_column(String(60), nullable=False)
    completed: Mapped[bool] = mapped_column(nullable=False, default=True)


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        CheckConstraint(
            "item_type in ('oracao','novena','rito','reflexao')", name="ck_favorite_type"
        ),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    item_type: Mapped[str] = mapped_column(String(12), primary_key=True)
    item_slug: Mapped[str] = mapped_column(String(80), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)


class Intention(Base):
    __tablename__ = "intentions"
    __table_args__ = (CheckConstraint("length(text) > 0", name="ck_intention_text"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(TS)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(String(200), nullable=False)
    auth: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)


class ManagedContent(Base):
    __tablename__ = "managed_contents"
    __table_args__ = (
        CheckConstraint(
            "kind in ('oracao','texto','reflexao','rito','terco','hora','santo','novena','misterio')",
            name="ck_content_kind",
        ),
        CheckConstraint("length(title) > 0 and length(body) > 0", name="ck_content_nonempty"),
        Index("ix_managed_contents_kind", "kind"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(String(200))
    origin: Mapped[str | None] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(String(500))
    # dados estruturados por tipo: santo {date}, novena {days, final_prayer}, misterio {weekdays, mysteries}
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    published: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TS, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PrayerRequest(Base):
    __tablename__ = "prayer_requests"
    __table_args__ = (
        CheckConstraint("length(text) between 1 and 1000", name="ck_request_text"),
        Index("ix_prayer_requests_created", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    anonymous: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(TS)
    removed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class PrayerPrayed(Base):
    __tablename__ = "prayer_prayed"
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prayer_requests.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)


class PrayerComment(Base):
    __tablename__ = "prayer_comments"
    __table_args__ = (
        CheckConstraint("length(text) between 1 and 500", name="ck_comment_text"),
        Index("ix_prayer_comments_request", "request_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prayer_requests.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(TS)
    removed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
