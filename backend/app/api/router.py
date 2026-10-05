"""Сборка всех роутеров под префиксом /api."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import auth, health

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)

# Остальные роутеры (services, masters, availability, appointments,
# admin, master) подключаются на следующих этапах.
