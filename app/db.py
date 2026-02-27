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
    cfg = get_db_config()
    db_url = build_db_url(cfg)
    return create_engine(db_url, pool_pre_ping=True)


def test_db_connection() -> Tuple[str, str, str]:
    cfg = get_db_config()
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except (SQLAlchemyError, Exception) as err:
        raise RuntimeError(format_db_error(cfg.host, cfg.port, cfg.name, err)) from err

    return cfg.host, cfg.port, cfg.name
