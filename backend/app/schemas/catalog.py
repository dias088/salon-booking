"""Схемы публичного каталога: категории, услуги, мастера."""

from __future__ import annotations

from datetime import time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

ORM = ConfigDict(from_attributes=True)


class CategoryOut(BaseModel):
    model_config = ORM

    id: int
    name: str
    sort_order: int


class ServiceOut(BaseModel):
    model_config = ORM

    id: int
    name: str
    description: str | None
    duration_min: int
    price: Decimal
    is_active: bool
    category_id: int
    category_name: str


class CategoryWithServices(BaseModel):
    """Категория вместе со своими услугами — форма под страницу каталога."""

    id: int
    name: str
    sort_order: int
    services: list[ServiceOut]


class MasterServiceOut(BaseModel):
    """Услуга в исполнении конкретного мастера.

    price и duration_min — уже эффективные: если у мастера свои значения,
    подставлены они (COALESCE считается в представлении v_master_service_offer).
    """

    service_id: int
    service_name: str
    category_id: int
    category_name: str
    price: Decimal
    duration_min: int
    has_custom_price: bool
    has_custom_duration: bool


class MasterOut(BaseModel):
    id: int
    full_name: str
    bio: str | None
    photo_url: str | None
    is_active: bool
    services: list[MasterServiceOut] = Field(default_factory=list)


class WorkingHoursOut(BaseModel):
    model_config = ORM

    id: int
    weekday: int = Field(ge=0, le=6, description="0 — понедельник, 6 — воскресенье")
    start_time: time
    end_time: time


class MasterDetailOut(MasterOut):
    working_hours: list[WorkingHoursOut] = Field(default_factory=list)
