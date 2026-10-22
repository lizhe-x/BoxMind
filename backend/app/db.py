from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    from . import models  # noqa: F401

    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
