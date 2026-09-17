from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .routers import (
    agent_router,
    ask_router,
    asr_router,
    auth_router,
    boxes_router,
    ingest_router,
    me_router,
    tts_router,
    vision_router,
)
from .services import embeddings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    embeddings.warmup()
    yield


app = FastAPI(title="BoxMind API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # 本机 + 局域网(192.168.x.x / 10.x.x.x)任意端口,便于手机走局域网测试
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(boxes_router.router)
app.include_router(ingest_router.router)
app.include_router(ask_router.router)
app.include_router(asr_router.router)
app.include_router(vision_router.router)
app.include_router(tts_router.router)
app.include_router(agent_router.router)
app.include_router(me_router.router)


# 用户媒体静态服务(uuid 文件名防猜;<img>/<audio> 可直接引用)
Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")


@app.get("/api/health")
def health():
    return {"ok": True}


# 生产构建存在则由后端直接托管前端(/ 挂在最后,/api 与 /media 优先匹配)。
# 单进程对外,免去单独的 vite preview + 反代,部署更稳。
_dist = Path(settings.frontend_dist)
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
