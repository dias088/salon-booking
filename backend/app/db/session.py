"""Асинхронный движок и фабрика сессий."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def create_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        # Serverless-Postgres (Neon) закрывает простаивающие соединения сам,
        # поэтому не держим их дольше пяти минут.
        pool_recycle=300,
    )


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
