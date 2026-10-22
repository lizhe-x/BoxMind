"""Production traces, persisted: one `agent_runs` row per model-backed request.

What a row answers: which model and prompt version handled the request, which tools ran, how long it took,
how it ended, and what the user thought of it (explicit thumbs, or the implicit "undo" of a confirmed
destructive action). `evals/export.py` turns failed rows into eval-case stubs; that is the feedback loop.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import AgentRun, User
from .trace import Trace

MAX_INPUT = 2000
FAILED_OUTCOMES = ("error", "step_cap")
CONFIRM_WINDOW = timedelta(minutes=30)


def record(db: Session, user: User, t: Trace) -> AgentRun:
    run = AgentRun(
        user_id=user.id, kind=t.kind, model=t.model or "", prompt=json.dumps(t.prompts, ensure_ascii=False),
        input=t.input[:MAX_INPUT], lang=t.lang or "",
        tool_calls=json.dumps([c.__dict__ for c in t.tool_calls], ensure_ascii=False),
        confirm=json.dumps(t.confirm, ensure_ascii=False),
        steps=t.steps, tokens=t.tokens, latency_ms=t.latency_ms, outcome=t.outcome or "ok",
        error=(t.error or None), output=json.dumps(t.output, ensure_ascii=False),
    )
    db.add(run)
    db.commit()
    return run


def latest_pending_confirm(db: Session, user: User, now: datetime | None = None) -> AgentRun | None:
    """The run whose confirm card the user is answering: newest 'confirm' run not yet confirmed, recent."""
    now = now or datetime.now(UTC)
    return db.scalar(
        select(AgentRun)
        .where(AgentRun.user_id == user.id, AgentRun.outcome == "confirm", AgentRun.confirmed == 0,
               AgentRun.created_at >= now - CONFIRM_WINDOW)
        .order_by(AgentRun.created_at.desc()).limit(1)
    )


def mark_undone(db: Session, run_id: str | None) -> None:
    run = db.get(AgentRun, run_id) if run_id else None
    if run:
        run.undone = 1


def set_feedback(db: Session, user: User, run_id: str, value: int, note: str | None = None) -> AgentRun | None:
    run = db.get(AgentRun, run_id)
    if not run or run.user_id != user.id:
        return None
    run.feedback = value
    run.feedback_note = (note or None) and note[:500]
    db.commit()
    return run


def list_runs(db: Session, user: User, limit: int = 50, failed: bool = False) -> list[AgentRun]:
    q = select(AgentRun).where(AgentRun.user_id == user.id)
    if failed:
        q = q.where(failed_filter())
    return list(db.scalars(q.order_by(AgentRun.created_at.desc()).limit(limit)))


def failed_filter():
    return or_(AgentRun.feedback == -1, AgentRun.undone == 1, AgentRun.outcome.in_(FAILED_OUTCOMES))


def is_failed(run: AgentRun) -> bool:
    return run.feedback == -1 or bool(run.undone) or run.outcome in FAILED_OUTCOMES


def to_dict(run: AgentRun) -> dict:
    return {
        "id": run.id, "kind": run.kind, "model": run.model, "prompt": _loads(run.prompt, {}),
        "input": run.input, "lang": run.lang, "tool_calls": _loads(run.tool_calls, []),
        "confirm": _loads(run.confirm, []), "steps": run.steps, "tokens": run.tokens, "latency_ms": run.latency_ms,
        "outcome": run.outcome, "error": run.error, "output": _loads(run.output, {}),
        "confirmed": bool(run.confirmed), "undone": bool(run.undone), "feedback": run.feedback,
        "feedback_note": run.feedback_note, "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def _loads(text: str | None, default):
    try:
        return json.loads(text) if text else default
    except json.JSONDecodeError:
        return default
