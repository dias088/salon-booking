"""Записи клиента: создать, посмотреть свои, отменить."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ClientUser, CurrentUser, SessionDep
from app.schemas.appointment import AppointmentCreate, AppointmentOut, AppointmentScope
from app.schemas.common import ErrorResponse, Page
from app.services import booking

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post(
    "",
    response_model=AppointmentOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {
            "model": ErrorResponse,
            "description": "Время занято. Код slot_taken — фронтенд перезапрашивает слоты",
        },
        422: {"model": ErrorResponse, "description": "Время вне графика или вне сетки слотов"},
    },
    summary="Записаться",
    description=(
        "Время должно совпадать с одним из слотов `/api/availability`.\n\n"
        "Если тот же слот успел занять другой клиент, вернётся `409 slot_taken` — "
        "это срабатывает ограничение `appointments_no_overlap` в PostgreSQL, "
        "а не проверка в коде, поэтому гонка двух одновременных запросов "
        "невозможна в принципе."
    ),
)
async def create_appointment(
    data: AppointmentCreate, user: ClientUser, session: SessionDep
) -> AppointmentOut:
    return await booking.create_appointment(
        session,
        client_id=user.id,
        master_id=data.master_id,
        service_id=data.service_id,
        starts_at=data.starts_at,
        comment=data.comment,
    )


@router.get("/my", response_model=Page[AppointmentOut], summary="Мои записи")
async def my_appointments(
    user: CurrentUser,
    session: SessionDep,
    scope: Annotated[
        AppointmentScope, Query(description="upcoming — предстоящие, past — прошедшие")
    ] = "all",
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[AppointmentOut]:
    query = booking.appointments_query(client_id=user.id, scope=scope)
    items, total = await booking.paginate(session, query, page=page, size=size)
    return Page(items=items, total=total, page=page, size=size)


@router.get(
    "/{appointment_id}",
    response_model=AppointmentOut,
    responses={404: {"model": ErrorResponse, "description": "Нет такой записи или она чужая"}},
    summary="Одна запись",
)
async def get_appointment(
    appointment_id: int, user: CurrentUser, session: SessionDep
) -> AppointmentOut:
    return await booking.get_for_user(session, appointment_id, user)


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentOut,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Поздно отменять или запись не активна"},
    },
    summary="Отменить запись",
)
async def cancel_appointment(
    appointment_id: int, user: CurrentUser, session: SessionDep
) -> AppointmentOut:
    return await booking.cancel_appointment(session, appointment_id, user)
