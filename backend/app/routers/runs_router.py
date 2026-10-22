"""The user's own production traces: list them, rate them (thumbs up / down)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import User
from ..services import runs

router = APIRouter(prefix="/api", tags=["runs"])


class FeedbackIn(BaseModel):
    value: int = Field(ge=-1, le=1, description="1 = thumbs up, -1 = thumbs down, 0 = clear")
    note: str | None = Field(default=None, max_length=500)


@router.get("/runs")
def list_runs(limit: int = Query(50, ge=1, le=200), failed: bool = False,
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Newest first. `failed=true` keeps only thumbs-down, undone, errored or step-capped runs."""
    return {"runs": [runs.to_dict(r) for r in runs.list_runs(db, user, limit=limit, failed=failed)]}


@router.post("/runs/{run_id}/feedback")
def feedback(run_id: str, body: FeedbackIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    run = runs.set_feedback(db, user, run_id, body.value, body.note)
    if not run:
        raise HTTPException(404, "run not found")
    return {"ok": True, "run_id": run.id, "feedback": run.feedback}
