"""Health-check. Нужен Render для проверки живости контейнера."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session

router = APIRouter(tags=["meta"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok", "unavailable"]
    salon_tz: str
    environment: str


@router.get("/health", response_model=HealthResponse)
async def health(session: Annotated[AsyncSession, Depends(get_session)]) -> HealthResponse:
    try:
        await session.execute(text("SELECT 1"))
        database: Literal["ok", "unavailable"] = "ok"
    except Exception:  # health-check не должен падать сам
        database = "unavailable"
    return HealthResponse(
        status="ok",
        database=database,
        salon_tz=settings.salon_tz,
        environment=settings.environment,
    )
