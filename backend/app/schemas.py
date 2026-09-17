from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceAuthIn(BaseModel):
    device_id: str = Field(min_length=8, max_length=128)


class RequestCodeIn(BaseModel):
    email: str = Field(min_length=5, max_length=255)


class VerifyCodeIn(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    code: str = Field(min_length=4, max_length=8)


class TokenOut(BaseModel):
    token: str
    user_id: str
    email: str | None = None


class ItemOut(BaseModel):
    id: str
    name: str
    qty_text: str
    note: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BoxOut(BaseModel):
    id: str
    label: str
    name: str
    barcode: str | None
    photo_url: str | None
    location_text: str | None
    gps_lat: float | None
    gps_lng: float | None
    color_a: str
    color_b: str
    source: str
    created_at: datetime
    updated_at: datetime
    items: list[ItemOut] = []
    photos: list[str] = []
    audios: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class BoxCreateIn(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    name: str | None = None
    location_text: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None


class BoxUpdateIn(BaseModel):
    label: str | None = None
    name: str | None = None
    barcode: str | None = None
    location_text: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    qty_text: str = "×1"
    note: str | None = None


class ItemUpdateIn(BaseModel):
    name: str | None = None
    qty_text: str | None = None
    note: str | None = None


class InterpretIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    target_box_id: str | None = None  # 「录入到此箱」时由前端带上


class InterpretOut(BaseModel):
    intent: str  # ingest | query
    box_label: str | None
    box: BoxOut | None  # 已存在的匹配箱子
    items: list[ItemIn]
    location_text: str | None
    language: str
    next_label: str  # askbox 兜底用的推荐新编号,如 "4号"


class IngestIn(BaseModel):
    box_id: str | None = None  # 选了已有箱子
    box_label: str | None = None  # 或新建/匹配编号
    items: list[ItemIn]
    location_text: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    raw_text: str | None = None
    source: str = "text"


class IngestOut(BaseModel):
    box: BoxOut
    created: bool
    credits_left: int


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class MeOut(BaseModel):
    user_id: str
    email: str | None = None
    lang: str
    gps_enabled: bool
    credit_balance: int
    used: int
    box_count: int
    item_count: int


class SettingsIn(BaseModel):
    lang: str | None = None
    gps_enabled: bool | None = None
