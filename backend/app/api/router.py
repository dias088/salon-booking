"""Сборка всех роутеров под префиксом /api."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import health

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)

# Остальные роутеры (auth, services, masters, availability, appointments,
# admin, master) подключаются на следующих этапах.
