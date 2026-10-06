"""Сборка всех роутеров под префиксом /api."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    admin,
    appointments,
    auth,
    availability,
    health,
    master,
    masters,
    services,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(services.router)
api_router.include_router(masters.router)
api_router.include_router(availability.router)
api_router.include_router(appointments.router)
api_router.include_router(master.router)
api_router.include_router(admin.router)
