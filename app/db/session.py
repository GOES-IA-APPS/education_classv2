from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings


def build_engine(database_url: str):
    kwargs: dict = {"echo": settings.sql_echo, "future": True}

    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in database_url:
            kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_pre_ping"] = True

    return create_engine(database_url, **kwargs)


engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def reset_engine(database_url: str) -> None:
    global engine
    engine.dispose()
    engine = build_engine(database_url)
    SessionLocal.configure(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
