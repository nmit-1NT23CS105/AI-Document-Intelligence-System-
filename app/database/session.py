from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.database.models import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


class SessionFactoryProxy:
    def __call__(self) -> Session:
        return get_session_factory()()


SessionLocal = SessionFactoryProxy()


def _engine_options(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


def configure_database(database_url: str | None = None) -> None:
    global _engine, _session_factory

    if _engine:
        _engine.dispose()

    resolved_url = database_url or get_settings().database_url
    _engine = create_engine(resolved_url, **_engine_options(resolved_url))
    _session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_engine,
    )


def get_engine() -> Engine:
    if _engine is None:
        configure_database()
    assert _engine is not None
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        configure_database()
    assert _session_factory is not None
    return _session_factory


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
