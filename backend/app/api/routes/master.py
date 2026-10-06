"""Кабинет мастера: своё расписание и отметки о визитах."""

from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentMaster, SessionDep
from app.core.errors import ForbiddenError
from app.db.models.enums import AppointmentStatus
from app.schemas.admin import AppointmentStatusUpdate
from app.schemas.appointment import AppointmentOut
from app.schemas.common import ErrorResponse, Page
from app.services import admin, booking
from app.services.slots import today_in_salon

router = APIRouter(prefix="/master", tags=["master"])

#: Мастер отмечает только факт визита. Отмена — к администратору:
#: за ней тянутся возврат и разговор с клиентом.
MASTER_ALLOWED_STATUSES = frozenset({AppointmentStatus.completed, AppointmentStatus.no_show})


@router.get(
    "/schedule",
    response_model=Page[AppointmentOut],
    summary="Своё расписание",
    description=(
        "Без параметров — сегодня. `date` — конкретный день, "
        "`date_from`/`date_to` — произвольный интервал (для недельного вида)."
    ),
)
async def my_schedule(
    master: CurrentMaster,
    session: SessionDep,
    date: Annotated[date_type | None, Query(description="Один день")] = None,
    date_from: date_type | None = None,
    date_to: Annotated[date_type | None, Query(description="Включительно")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 100,
) -> Page[AppointmentOut]:
    query = booking.appointments_query(master_id=master.id)

    if date_from is not None or date_to is not None:
        start = date_from or today_in_salon()
        end = date_to or start
        query = booking.limit_to_range(query, start, end + timedelta(days=1))
    else:
        query = booking.limit_to_day(query, date or today_in_salon())

    items, total = await booking.paginate(session, query, page=page, size=size)
    return Page(items=items, total=total, page=page, size=size)


@router.patch(
    "/appointments/{appointment_id}/status",
    response_model=AppointmentOut,
    responses={
        403: {"model": ErrorResponse, "description": "Мастеру доступны completed и no_show"},
        404: {"model": ErrorResponse, "description": "Чужая запись маскируется под отсутствующую"},
        409: {"model": ErrorResponse, "description": "Недопустимый переход статуса"},
    },
    summary="Отметить визит как состоявшийся или неявку",
)
async def set_status(
    appointment_id: int,
    data: AppointmentStatusUpdate,
    master: CurrentMaster,
    session: SessionDep,
) -> AppointmentOut:
    if data.status not in MASTER_ALLOWED_STATUSES:
        raise ForbiddenError(
            "Мастер может ставить только completed или no_show", code="status_not_allowed"
        )

    # master_id ограничивает выборку своими записями: чужая отдаст 404.
    await admin.set_appointment_status(session, appointment_id, data.status, master_id=master.id)
    return await booking.get_for_user(session, appointment_id, master.user)
