"""Точка входа FastAPI."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers

DESCRIPTION = """
Онлайн-запись в салон красоты.

Защита от двойной записи реализована в PostgreSQL ограничением
`EXCLUDE USING gist (master_id WITH =, period WITH &&) WHERE (status = 'booked')`,
поэтому два клиента физически не могут занять одно время у одного мастера —
даже если запросы пришли одновременно. Нарушение превращается в `409 slot_taken`.

Все ошибки имеют единый формат: `{ "error": { "code", "message" } }`.
""".strip()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=DESCRIPTION,
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        # Обязательно: refresh-токен ходит в httpOnly cookie,
        # а значит нужны credentialed-запросы.
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
