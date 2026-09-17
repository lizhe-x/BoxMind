"""用户媒体(图片/音频)文件存储。落盘到 settings.media_dir,文件名用 uuid 防猜。"""
import uuid
from pathlib import Path

from ..config import settings

_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}


def _dir() -> Path:
    p = Path(settings.media_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def save(data: bytes, content_type: str, default_ext: str) -> str:
    """保存文件,返回存储文件名(uuid.ext)。"""
    ext = _EXT.get((content_type or "").split(";")[0].strip(), default_ext)
    name = f"{uuid.uuid4().hex}{ext}"
    (_dir() / name).write_bytes(data)
    return name


def delete(filename: str) -> None:
    try:
        (_dir() / filename).unlink(missing_ok=True)
    except OSError:
        pass
