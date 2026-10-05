"""Свободные слоты."""

from __future__ import annotations

from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.schemas.availability import AvailabilityResponse
from app.schemas.common import ErrorResponse
from app.services import slots

router = APIRouter(tags=["availability"])


@router.get(
    "/availability",
    response_model=AvailabilityResponse,
    responses={404: {"model": ErrorResponse, "description": "Услуга не найдена"}},
    summary="Свободные слоты на дату",
    description=(
        "Шаг сетки 15 минут. Слот предлагается, только если услуга целиком "
        "помещается до конца рабочего интервала и не пересекается с отпуском, "
        "активной записью или уже прошедшим временем.\n\n"
        "Без `master_id` возвращаются слоты всех мастеров, оказывающих услугу: "
        "поле `masters` — по каждому отдельно, поле `slots` — объединённые, "
        "для варианта «любой свободный мастер»."
    ),
)
async def get_availability(
    session: SessionDep,
    service_id: Annotated[int, Query(description="Услуга, на которую записываются")],
    date: Annotated[date_type, Query(description="Дата в часовом поясе салона, YYYY-MM-DD")],
    master_id: Annotated[int | None, Query(description="Конкретный мастер")] = None,
) -> AvailabilityResponse:
    return await slots.day_availability(
        session, service_id=service_id, day=date, master_id=master_id
    )
