"""Схемы ответа о свободных слотах."""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MasterSlots(BaseModel):
    """Свободное время одного мастера на выбранный день."""

    master_id: int
    master_name: str
    photo_url: str | None
    price: Decimal
    duration_min: int
    slots: list[datetime]


class AnyMasterSlot(BaseModel):
    """Слот для режима «любой свободный мастер».

    master_ids — все, кто свободен в это время; фронтенд обычно берёт
    первого, но может и предложить выбор.
    """

    starts_at: datetime
    ends_at: datetime
    master_ids: list[int]


class AvailabilityResponse(BaseModel):
    date: date_type
    service_id: int
    service_name: str
    timezone: str = Field(description="Часовой пояс салона, в котором трактуется date")
    masters: list[MasterSlots]
    slots: list[AnyMasterSlot] = Field(
        description="Объединённые слоты всех мастеров — для варианта «любой мастер»"
    )
