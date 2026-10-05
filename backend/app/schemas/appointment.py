"""Схемы записи на приём."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import AppointmentStatus

Comment = Annotated[str | None, Field(default=None, max_length=500)]


class AppointmentCreate(BaseModel):
    service_id: int
    master_id: int = Field(
        description="Конкретный мастер. Для режима «любой» фронтенд подставляет "
        "первого из master_ids выбранного слота."
    )
    starts_at: datetime = Field(
        description="Начало визита. Должно совпадать с одним из слотов /api/availability."
    )
    comment: Comment = None


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: AppointmentStatus
    starts_at: datetime
    ends_at: datetime
    duration_min: int
    price_at_booking: Decimal
    comment: str | None
    created_at: datetime
    cancelled_at: datetime | None

    client_id: int
    client_name: str
    client_phone: str

    master_id: int
    master_name: str

    service_id: int
    service_name: str
    category_name: str

    #: Можно ли отменить прямо сейчас — считается на сервере, чтобы фронтенд
    #: не повторял правило «не позже чем за два часа».
    can_cancel: bool = False


AppointmentScope = Literal["upcoming", "past", "all"]
