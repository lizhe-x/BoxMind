import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import User
from ..services import agent, agent_destructive, agent_tools

router = APIRouter(prefix="/api", tags=["agent"])


class GPS(BaseModel):
    lat: float | None = None
    lng: float | None = None


class AgentMsg(BaseModel):
    role: str
    content: str


class AgentIn(BaseModel):
    message: str
    history: list[AgentMsg] = []
    gps: GPS | None = None


@router.post("/agent")
async def agent_endpoint(body: AgentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """自然语言操作指令 → agent 调用工具执行。返回 {type:'message'|'confirm', ...}。"""
    history = [{"role": m.role, "content": m.content} for m in body.history]
    gps = {"lat": body.gps.lat, "lng": body.gps.lng} if body.gps else None
    try:
        return await agent.run(db, user, history, body.message, gps)
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:300] if e.response is not None else str(e)
        raise HTTPException(502, f"agent_upstream_error: {detail}")


class ExecuteIn(BaseModel):
    tool: str
    args: dict = {}


@router.post("/agent/execute")
def agent_execute(body: ExecuteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """用户确认后执行破坏性操作。"""
    if body.tool not in agent_tools.DESTRUCTIVE:
        raise HTTPException(400, "该操作不需要确认执行")
    return agent_destructive.execute(db, user, body.tool, body.args)
