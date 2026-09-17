import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import settings
from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lang: Mapped[str] = mapped_column(String(8), default="zh")
    gps_enabled: Mapped[int] = mapped_column(Integer, default=1)
    credit_balance: Mapped[int] = mapped_column(Integer, default=settings.free_credits)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    boxes: Mapped[list["Box"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Box(Base):
    __tablename__ = "boxes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(64))  # 用户编号,必有: "1号" / "A2" / "红箱"
    norm_label: Mapped[str] = mapped_column(String(64), index=True)  # 归一化后的匹配键
    name: Mapped[str] = mapped_column(String(128))  # 显示名: "1号箱" / "A2 杂物箱"
    barcode: Mapped[str | None] = mapped_column(String(128), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    location_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    color_a: Mapped[str] = mapped_column(String(16), default="#9C7A52")
    color_b: Mapped[str] = mapped_column(String(16), default="#7A5E3E")
    source: Mapped[str] = mapped_column(String(16), default="text")  # voice | text | photo | scan
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    user: Mapped[User] = relationship(back_populates="boxes")
    items: Mapped[list["Item"]] = relationship(
        back_populates="box", cascade="all, delete-orphan", order_by="Item.created_at"
    )
    media: Mapped[list["Media"]] = relationship(
        back_populates="box", cascade="all, delete-orphan", order_by="Media.created_at"
    )

    @property
    def photos(self) -> list[str]:
        return [m.url for m in self.media if m.kind == "photo"]

    @property
    def audios(self) -> list[str]:
        return [m.url for m in self.media if m.kind == "audio"]


class Item(Base):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    box_id: Mapped[str] = mapped_column(ForeignKey("boxes.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    qty_text: Mapped[str] = mapped_column(String(64), default="×1")  # "×3" / "×2 双" / "若干"
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding = mapped_column(Vector(settings.embedding_dim), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    box: Mapped[Box] = relationship(back_populates="items")


class Media(Base):
    __tablename__ = "media"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    box_id: Mapped[str | None] = mapped_column(ForeignKey("boxes.id"), index=True, nullable=True)
    kind: Mapped[str] = mapped_column(String(16))  # photo | audio
    filename: Mapped[str] = mapped_column(String(128))  # 存储文件名 uuid.ext
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    box: Mapped["Box"] = relationship(back_populates="media")

    @property
    def url(self) -> str:
        return f"/media/{self.filename}"


class EmailCode(Base):
    __tablename__ = "email_codes"

    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    code: Mapped[str] = mapped_column(String(6))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class UndoSnapshot(Base):
    """破坏性操作前的快照(每用户保留最近一次,用于"撤销上一步")。"""
    __tablename__ = "undo_snapshots"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    label: Mapped[str] = mapped_column(String(80))  # 操作描述,如 "合并箱子"
    payload: Mapped[str] = mapped_column(Text)       # 受影响箱子的完整 JSON 快照
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class UsageLog(Base):
    __tablename__ = "usage_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(32))  # ingest | query
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
