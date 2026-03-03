import os
from typing import Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import build_db_url, get_db_config


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
    return create_engine(db_url, pool_pre_ping=True)


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
