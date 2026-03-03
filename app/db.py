import os
from threading import Lock
from typing import Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import build_db_url, get_db_config


_engine_cache = {}
_engine_lock = Lock()


def _error_summary(err: Exception) -> str:
    return f"{type(err).__name__}: {err}"


def format_db_error(host: str, port: str, name: str, err: Exception) -> str:
    return (
        "Database connection failed: "
        f"host={host}, port={port}, db_name={name}, error={_error_summary(err)}"
    )


def get_engine():
    db_url = str(os.getenv("DATABASE_URL", "")).strip()
    if not db_url:
        cfg = get_db_config()
        db_url = build_db_url(cfg)
    with _engine_lock:
        engine = _engine_cache.get(db_url)
        if engine is None:
            pool_size = int(str(os.getenv("DB_POOL_SIZE", "20")).strip() or "20")
            max_overflow = int(str(os.getenv("DB_MAX_OVERFLOW", "30")).strip() or "30")
            pool_timeout = int(str(os.getenv("DB_POOL_TIMEOUT", "30")).strip() or "30")
            pool_recycle = int(str(os.getenv("DB_POOL_RECYCLE", "1800")).strip() or "1800")
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=max(1, pool_size),
                max_overflow=max(0, max_overflow),
                pool_timeout=max(1, pool_timeout),
                pool_recycle=max(60, pool_recycle),
            )
            _engine_cache[db_url] = engine
        return engine


def test_db_connection() -> Tuple[str, str, str]:
    db_url = str(os.getenv("DATABASE_URL", "")).strip()
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except (SQLAlchemyError, Exception) as err:
        if db_url:
            raise RuntimeError(f"Database connection failed: database_url={db_url}, error={_error_summary(err)}") from err
        cfg = get_db_config()
        raise RuntimeError(format_db_error(cfg.host, cfg.port, cfg.name, err)) from err

    if db_url:
        return "DATABASE_URL", "", db_url
    cfg = get_db_config()
    return cfg.host, cfg.port, cfg.name
