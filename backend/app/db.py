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
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.commit()
    from . import models  # noqa: F401

    Base.metadata.create_all(engine)
    with engine.begin() as conn:  # columns added after a table first shipped (no migration tool in this project)
        conn.execute(text("ALTER TABLE undo_snapshots ADD COLUMN IF NOT EXISTS run_id VARCHAR(32)"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
