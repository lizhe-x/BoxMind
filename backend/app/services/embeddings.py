"""Embedding 提供方: local(fastembed,进程内) / remote(网关 /v1/embeddings)。

网关开通 embedding 模型后,把 BOXMIND_EMBEDDING_PROVIDER=remote、
BOXMIND_EMBEDDING_MODEL 与 BOXMIND_EMBEDDING_DIM 改到 .env 即可切换。
"""

import asyncio

import httpx

from ..config import settings

_model = None
_lock = asyncio.Lock()


def _get_local_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name=settings.embedding_model)
    return _model


def _embed_local_sync(texts: list[str]) -> list[list[float]]:
    model = _get_local_model()
    return [list(map(float, v)) for v in model.embed(texts)]


async def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if settings.embedding_provider == "remote":
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{settings.llm_base_url}/embeddings",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={"model": settings.embedding_model, "input": texts},
            )
            r.raise_for_status()
            data = sorted(r.json()["data"], key=lambda d: d["index"])
            return [d["embedding"] for d in data]
    async with _lock:  # fastembed 模型非线程安全,串行化
        return await asyncio.to_thread(_embed_local_sync, texts)


def warmup() -> None:
    """启动时预加载本地模型(首次会下载权重)。"""
    if settings.embedding_provider == "local":
        _get_local_model()
