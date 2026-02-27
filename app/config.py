import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: str
    name: str
    user: str
    password: str


class DatabaseConfigError(ValueError):
    pass


def load_env() -> str:
    # Load base .env first, then env-specific overrides
    load_dotenv()
    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env == "development":
        load_dotenv(".env.dev", override=True)
    elif app_env == "test":
        load_dotenv(".env.test", override=True)
    elif app_env == "production":
        load_dotenv(".env.prod", override=True)
    return app_env


def get_db_config() -> DbConfig:
    host = os.getenv("DB_HOST", "")
    port = os.getenv("DB_PORT", "")
    name = os.getenv("DB_NAME", "")
    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")

    missing: List[str] = []
    if not host:
        missing.append("DB_HOST")
    if not port:
        missing.append("DB_PORT")
    if not name:
        missing.append("DB_NAME")
    if not user:
        missing.append("DB_USER")
    if not password:
        missing.append("DB_PASSWORD")

    if missing:
        raise DatabaseConfigError(
            "Missing required database config fields: " + ", ".join(missing)
        )

    return DbConfig(host=host, port=port, name=name, user=user, password=password)


def build_db_url(cfg: DbConfig) -> str:
    from urllib.parse import quote_plus

    user_enc = quote_plus(cfg.user)
    password_enc = quote_plus(cfg.password)
    return (
        f"mysql+pymysql://{user_enc}:{password_enc}"
        f"@{cfg.host}:{cfg.port}/{cfg.name}?charset=utf8mb4"
    )
