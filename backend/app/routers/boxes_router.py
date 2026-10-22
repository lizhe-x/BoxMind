from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_user
from ..db import get_db
from ..models import Box, Item, Media, User
from ..normalize import normalize_label
from ..schemas import BoxCreateIn, BoxOut, BoxUpdateIn, ItemIn, ItemOut, ItemUpdateIn
from ..services import boxes_service, embeddings, media

router = APIRouter(prefix="/api/boxes", tags=["boxes"])


class ResolveIn(BaseModel):
    code: str | None = None       # 扫到的条码/二维码值
    label: str | None = None      # 手写编号(兜底)
    create: bool = False          # 没匹配到时是否新建


def _own_box(db: Session, user: User, box_id: str) -> Box:
    box = db.scalar(
        select(Box)
        .options(selectinload(Box.items), selectinload(Box.media))
        .where(Box.id == box_id, Box.user_id == user.id)
    )
    if not box:
        raise HTTPException(404, "box not found")
    return box


@router.get("", response_model=list[BoxOut])
def list_boxes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Box)
        .options(selectinload(Box.items), selectinload(Box.media))
        .where(Box.user_id == user.id)
        .order_by(Box.updated_at.desc())
    ).all()


@router.get("/next-label")
def next_label(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"next_label": boxes_service.next_num_label(db, user)}


@router.post("/resolve")
def resolve(body: ResolveIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """扫码/手写编号 → 找到对应箱子(可关联码/新建)。返回 {box, created}。"""
    box = None
    if body.code:
        box = db.scalar(
            select(Box).options(selectinload(Box.items), selectinload(Box.media))
            .where(Box.user_id == user.id, Box.barcode == body.code)
        )
    if not box and body.label:
        box = boxes_service.find_box_by_label(db, user.id, body.label)

    created = False
    if box:
        if body.code and not box.barcode:  # 把扫到的码关联到这个箱子
            box.barcode = body.code
            db.commit()
            db.refresh(box)
    elif body.create and (body.label or body.code):
        box = boxes_service.create_box(db, user, body.label or body.code, source="scan")
        if body.code:
            box.barcode = body.code
        db.commit()
        box = _own_box(db, user, box.id)
        created = True
    else:
        raise HTTPException(404, "box not found")

    return {"box": BoxOut.model_validate(box), "created": created}


@router.get("/by-label/{raw_label}", response_model=BoxOut)
def get_by_label(raw_label: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    box = boxes_service.find_box_by_label(db, user.id, raw_label)
    if not box:
        raise HTTPException(404, "box not found")
    return box


@router.get("/{box_id}", response_model=BoxOut)
def get_box(box_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _own_box(db, user, box_id)


@router.post("", response_model=BoxOut)
def create_box(body: BoxCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if boxes_service.find_box_by_label(db, user.id, body.label):
        raise HTTPException(409, "box with this label already exists")
    box = boxes_service.create_box(
        db, user, body.label, name=body.name, location_text=body.location_text,
        gps_lat=body.gps_lat, gps_lng=body.gps_lng,
    )
    db.commit()
    return _own_box(db, user, box.id)


@router.patch("/{box_id}", response_model=BoxOut)
def update_box(
    box_id: str, body: BoxUpdateIn,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    box = _own_box(db, user, box_id)
    data = body.model_dump(exclude_unset=True)
    if "label" in data and data["label"]:
        norm, label, default_name = normalize_label(data.pop("label"), user.lang)
        other = boxes_service.find_box_by_label(db, user.id, label)
        if other and other.id != box.id:
            raise HTTPException(409, "box with this label already exists")
        box.norm_label, box.label = norm, label
        if "name" not in data:
            box.name = default_name
    for k, v in data.items():
        setattr(box, k, v)
    db.commit()
    return _own_box(db, user, box.id)


@router.delete("/{box_id}")
def delete_box(box_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    box = _own_box(db, user, box_id)
    db.delete(box)
    db.commit()
    return {"ok": True}


@router.post("/{box_id}/items", response_model=ItemOut)
async def add_item(
    box_id: str, body: ItemIn,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    box = _own_box(db, user, box_id)
    await boxes_service.add_items(db, box, [body.model_dump()])
    db.commit()
    db.refresh(box)
    item = next(it for it in box.items if it.name == body.name)
    return item


@router.post("/{box_id}/photo")
async def upload_photo(
    box_id: str,
    file: UploadFile = File(...),
    set_cover: bool = True,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传箱子照片(拍照识别图/封面)。set_cover 时同时设为封面。"""
    box = _own_box(db, user, box_id)
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    name = media.save(data, file.content_type or "image/jpeg", ".jpg")
    db.add(Media(user_id=user.id, box_id=box.id, kind="photo", filename=name))
    if set_cover:
        box.photo_url = f"/media/{name}"
    db.commit()
    return {"url": f"/media/{name}"}


class CoverIn(BaseModel):
    url: str


@router.post("/{box_id}/cover", response_model=BoxOut)
async def set_cover(box_id: str, body: CoverIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """把箱子的某张已有照片设为封面(url 必须属于该箱)。"""
    box = _own_box(db, user, box_id)
    if body.url not in box.photos:
        raise HTTPException(400, "photo does not belong to this box")
    box.photo_url = body.url
    db.commit()
    return _own_box(db, user, box.id)


@router.post("/{box_id}/audio")
async def upload_audio(
    box_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传箱子录入语音。"""
    box = _own_box(db, user, box_id)
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    name = media.save(data, file.content_type or "audio/webm", ".webm")
    db.add(Media(user_id=user.id, box_id=box.id, kind="audio", filename=name))
    db.commit()
    return {"url": f"/media/{name}"}


@router.patch("/{box_id}/items/{item_id}", response_model=ItemOut)
async def update_item(
    box_id: str, item_id: str, body: ItemUpdateIn,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """改物品名称/数量/备注。改名时重新生成 embedding 以保证检索准确。"""
    box = _own_box(db, user, box_id)
    item = db.get(Item, item_id)
    if not item or item.box_id != box.id:
        raise HTTPException(404, "item not found")
    if body.name is not None and body.name.strip() and body.name != item.name:
        item.name = body.name.strip()
        item.embedding = (await embeddings.embed([item.name]))[0]
    if body.qty_text is not None:
        item.qty_text = body.qty_text
    if body.note is not None:
        item.note = body.note
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{box_id}/items/{item_id}")
def delete_item(
    box_id: str, item_id: str,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    box = _own_box(db, user, box_id)
    item = db.get(Item, item_id)
    if not item or item.box_id != box.id:
        raise HTTPException(404, "item not found")
    db.delete(item)
    db.commit()
    return {"ok": True}
