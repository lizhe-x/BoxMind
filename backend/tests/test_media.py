"""Media storage: extension mapping and uuid filenames."""
from pathlib import Path

from app.config import settings
from app.services import media


def test_save_maps_content_type_to_extension() -> None:
    name = media.save(b"\xff\xd8\xff", "image/jpeg", ".bin")
    assert name.endswith(".jpg")
    assert (Path(settings.media_dir) / name).read_bytes() == b"\xff\xd8\xff"


def test_save_strips_charset_parameter() -> None:
    assert media.save(b"x", "audio/webm; codecs=opus", ".bin").endswith(".webm")


def test_save_falls_back_to_default_extension() -> None:
    assert media.save(b"x", "application/octet-stream", ".dat").endswith(".dat")
    assert media.save(b"x", "", ".m4a").endswith(".m4a")


def test_filenames_are_unique_and_unguessable() -> None:
    a, b = media.save(b"1", "image/png", ".png"), media.save(b"2", "image/png", ".png")
    assert a != b
    assert len(a) == 32 + len(".png")


def test_delete_is_idempotent() -> None:
    name = media.save(b"x", "image/png", ".png")
    media.delete(name)
    assert not (Path(settings.media_dir) / name).exists()
    media.delete(name)  # second delete must not raise
