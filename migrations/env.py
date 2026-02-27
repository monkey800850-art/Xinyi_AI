from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import build_db_url, load_env, get_db_config

# this is the Alembic Config object, which provides access to the values within
# the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# no models yet
target_metadata = None


def run_migrations_offline() -> None:
    load_env()
    cfg = get_db_config()
    url = build_db_url(cfg)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    load_env()
    cfg = get_db_config()
    connectable = create_engine(build_db_url(cfg), pool_pre_ping=True)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
