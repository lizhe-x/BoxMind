import base64

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..i18n import tr
from ..models import User
from ..services import boxes_service, runs, trace
from ..services.llm import llm
from ..services.prompts import VISION

router = APIRouter(prefix="/api", tags=["vision"])


@router.post("/recognize")
async def recognize(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """拍照识别:图片 → 物品清单 + 手写编号。不入库(前端确认后走 /api/ingest)。"""
    img = await file.read()
    if not img:
        raise HTTPException(400, "empty image")
    mime = file.content_type or "image/jpeg"
    t = trace.start("recognize", model=llm.model_name, prompts={"vision": VISION.ref},
                    input=f"{mime} {len(img)} bytes", lang=user.lang)
    try:
        result = await llm.recognize_image(base64.b64encode(img).decode(), mime, user.lang)
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:300] if e.response is not None else str(e)
        t.error = detail
        runs.record(db, user, t.finish("error"))
        raise HTTPException(502, f"vision_upstream_error: {detail}") from e
    except Exception as e:  # noqa: BLE001
        t.error = str(e)
        runs.record(db, user, t.finish("error"))
        raise HTTPException(502, f"vision_error: {e}") from e
    run_id = runs.record(db, user, t.finish("ok", parsed=result)).id

    box_label = result.get("box_label")
    box = boxes_service.find_box_by_label(db, user.id, box_label) if box_label else None
    some = tr(user.lang, "qty_some")
    items = [
        {
            "name": it.get("name", ""),
            "qty_text": it.get("qty_text") or some,
            "confidence": it.get("confidence") or "medium",
        }
        for it in result.get("items", [])
        if it.get("name")
    ]
    return {
        "box_label": box_label,
        "box_exists": box is not None,
        "items": items,
        "next_label": boxes_service.next_num_label(db, user),
        "run_id": run_id,
    }
