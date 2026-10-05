"""Окружение Alembic (асинхронный движок + asyncpg).

URL берётся из переменной окружения через app.core.config, а не из
alembic.ini, чтобы не держать пароль в репозитории. Тесты подменяют его
переменной ALEMBIC_DATABASE_URL, чтобы накатывать схему на тестовую БД.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

# Импорт ради побочного эффекта: регистрирует все модели в Base.metadata
import app.db.models  # noqa: F401  (нужен для autogenerate)
from alembic import context
from app.core.config import settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return os.getenv("ALEMBIC_DATABASE_URL") or settings.database_url


def include_object(obj: object, name: str | None, type_: str, *_: object) -> bool:
    """Представления создаются отдельной миграцией, autogenerate их не касается."""
    return not (type_ == "table" and name is not None and name.startswith("v_"))


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(get_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
