"""Асинхронный движок и фабрика сессий."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

#: Признаки того, что соединение идёт через пул транзакционного режима.
#: Neon отдаёт такой хост с суффиксом -pooler, Supabase — через pgbouncer.
POOLER_HOST_MARKERS = ("-pooler.", "pgbouncer")


def is_transaction_pooler(url: str) -> bool:
    return any(marker in url for marker in POOLER_HOST_MARKERS)


def engine_options(url: str, *, echo: bool = False) -> tuple[str, dict[str, Any]]:
    """Итоговые URL и аргументы движка. Вынесено отдельно ради тестируемости.

    За транзакционным пулом соединение между запросами не закреплено:
    следующий запрос может уйти в другой бэкенд, где подготовленного
    выражения нет. asyncpg по умолчанию активно их кэширует, и это даёт
    плавающие ошибки `prepared statement "__asyncpg_stmt_x__" does not
    exist` — обычно уже на проде и под нагрузкой.

    Поэтому за пулером кэш выключается, а именам выражений даётся
    уникальный суффикс: так они не сталкиваются между соединениями.
    """
    kwargs: dict[str, Any] = {
        "echo": echo,
        "pool_pre_ping": True,
        # Serverless-Postgres закрывает простаивающие соединения сам,
        # поэтому не держим их дольше пяти минут.
        "pool_recycle": 300,
    }

    if is_transaction_pooler(url):
        # prepared_statement_cache_size — параметр диалекта, он читается
        # только из query-строки URL, аргументом create_engine его не взять.
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}prepared_statement_cache_size=0"
        kwargs["connect_args"] = {
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
        }

    return url, kwargs


def create_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    """Движок, пригодный и для прямого подключения, и для PgBouncer."""
    final_url, kwargs = engine_options(url, echo=echo)
    return create_async_engine(final_url, **kwargs)


engine: AsyncEngine = create_engine(settings.database_url, echo=settings.debug)

SessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI-зависимость: сессия на один запрос.

    Коммитят сами обработчики — так видно, где заканчивается транзакция.
    """
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
