"""Административное API. Всё под ролью admin."""

from __future__ import annotations

from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import AdminUser, SessionDep
from app.schemas.admin import (
    AdminAppointmentCreate,
    AppointmentStatusUpdate,
    CategoryCreate,
    CategoryUpdate,
    MasterCreate,
    MasterServiceLink,
    MasterUpdate,
    ServiceCreate,
    ServiceUpdate,
    TimeOffCreate,
    TimeOffOut,
    WorkingHoursCreate,
)
from app.schemas.appointment import AppointmentOut
from app.schemas.catalog import (
    CategoryOut,
    MasterDetailOut,
    MasterOut,
    ServiceOut,
    WorkingHoursOut,
)
from app.schemas.common import ErrorResponse, Page
from app.schemas.stats import StatsResponse
from app.services import admin, booking, catalog, stats

# Зависимость роли объявлена на уровне роутера: ни одна ручка внутри
# не может случайно оказаться публичной.
router = APIRouter(prefix="/admin", tags=["admin"])

AdminOnly = AdminUser


# --- категории -------------------------------------------------------------


@router.get("/categories", response_model=list[CategoryOut], summary="Категории")
async def list_categories(_: AdminOnly, session: SessionDep) -> list[CategoryOut]:
    catalog_data = await catalog.list_catalog(session, only_active=False)
    return [
        CategoryOut(id=item.id, name=item.name, sort_order=item.sort_order) for item in catalog_data
    ]


@router.post(
    "/categories",
    response_model=CategoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать категорию",
)
async def create_category(data: CategoryCreate, _: AdminOnly, session: SessionDep) -> CategoryOut:
    return CategoryOut.model_validate(await admin.create_category(session, data))


@router.patch("/categories/{category_id}", response_model=CategoryOut, summary="Изменить категорию")
async def update_category(
    category_id: int, data: CategoryUpdate, _: AdminOnly, session: SessionDep
) -> CategoryOut:
    return CategoryOut.model_validate(await admin.update_category(session, category_id, data))


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={409: {"model": ErrorResponse, "description": "В категории есть услуги"}},
    summary="Удалить категорию",
)
async def delete_category(category_id: int, _: AdminOnly, session: SessionDep) -> Response:
    await admin.delete_category(session, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- услуги ----------------------------------------------------------------


@router.get(
    "/services",
    response_model=Page[ServiceOut],
    summary="Услуги, включая скрытые",
)
async def list_services(
    _: AdminOnly,
    session: SessionDep,
    category_id: int | None = None,
    q: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    # Лимит выше публичного: админке нужен весь справочник одним запросом.
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[ServiceOut]:
    query = catalog.services_query(category_id=category_id, search=q, only_active=False)
    items, total = await catalog.paginate_services(session, query, page=page, size=size)
    return Page(items=items, total=total, page=page, size=size)


@router.post(
    "/services",
    response_model=ServiceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать услугу",
)
async def create_service(data: ServiceCreate, _: AdminOnly, session: SessionDep) -> ServiceOut:
    service = await admin.create_service(session, data)
    return await catalog.get_service(session, service.id)


@router.patch("/services/{service_id}", response_model=ServiceOut, summary="Изменить услугу")
async def update_service(
    service_id: int, data: ServiceUpdate, _: AdminOnly, session: SessionDep
) -> ServiceOut:
    await admin.update_service(session, service_id, data)
    return await catalog.get_service(session, service_id)


@router.delete(
    "/services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить услугу",
    description="Если по услуге были визиты, она не удаляется, а скрывается (is_active=false).",
)
async def delete_service(service_id: int, _: AdminOnly, session: SessionDep) -> Response:
    await admin.delete_service(session, service_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- мастера ---------------------------------------------------------------


@router.get("/masters", response_model=Page[MasterOut], summary="Мастера, включая неактивных")
async def list_masters(
    _: AdminOnly,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[MasterOut]:
    items, total = await catalog.list_masters(session, only_active=False, page=page, size=size)
    return Page(items=items, total=total, page=page, size=size)


@router.post(
    "/masters",
    response_model=MasterDetailOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse, "description": "E-mail занят"}},
    summary="Создать мастера вместе с учётной записью",
)
async def create_master(data: MasterCreate, _: AdminOnly, session: SessionDep) -> MasterDetailOut:
    master = await admin.create_master(session, data)
    return await catalog.get_master(session, master.id)


@router.patch("/masters/{master_id}", response_model=MasterDetailOut, summary="Изменить мастера")
async def update_master(
    master_id: int, data: MasterUpdate, _: AdminOnly, session: SessionDep
) -> MasterDetailOut:
    await admin.update_master(session, master_id, data)
    return await catalog.get_master(session, master_id)


@router.put(
    "/masters/{master_id}/services",
    response_model=MasterDetailOut,
    summary="Заменить набор услуг мастера",
)
async def set_master_services(
    master_id: int, links: list[MasterServiceLink], _: AdminOnly, session: SessionDep
) -> MasterDetailOut:
    await admin.set_master_services(session, master_id, links)
    return await catalog.get_master(session, master_id)


# --- график и отпуска ------------------------------------------------------


@router.post(
    "/masters/{master_id}/working-hours",
    response_model=WorkingHoursOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse, "description": "Интервалы в этот день пересекаются"}},
    summary="Добавить рабочий интервал",
)
async def add_working_hours(
    master_id: int, data: WorkingHoursCreate, _: AdminOnly, session: SessionDep
) -> WorkingHoursOut:
    return WorkingHoursOut.model_validate(await admin.add_working_hours(session, master_id, data))


@router.delete(
    "/masters/{master_id}/working-hours/{hours_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить рабочий интервал",
)
async def delete_working_hours(
    master_id: int, hours_id: int, _: AdminOnly, session: SessionDep
) -> Response:
    await admin.delete_working_hours(session, master_id, hours_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/masters/{master_id}/time-off", response_model=list[TimeOffOut], summary="Отпуска мастера"
)
async def list_time_off(master_id: int, _: AdminOnly, session: SessionDep) -> list[TimeOffOut]:
    return await admin.list_time_off(session, master_id)


@router.post(
    "/masters/{master_id}/time-off",
    response_model=TimeOffOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse, "description": "Периоды пересекаются"}},
    summary="Добавить период отсутствия",
)
async def add_time_off(
    master_id: int, data: TimeOffCreate, _: AdminOnly, session: SessionDep
) -> TimeOffOut:
    return await admin.add_time_off(session, master_id, data)


@router.delete(
    "/masters/{master_id}/time-off/{time_off_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить период отсутствия",
)
async def delete_time_off(
    master_id: int, time_off_id: int, _: AdminOnly, session: SessionDep
) -> Response:
    await admin.delete_time_off(session, master_id, time_off_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- записи ----------------------------------------------------------------


@router.get(
    "/appointments",
    response_model=Page[AppointmentOut],
    summary="Все записи салона",
    description="Основа календаря дня: без фильтров отдаёт всё, с `date` — один день.",
)
async def list_appointments(
    _: AdminOnly,
    session: SessionDep,
    date: Annotated[date_type | None, Query(description="Один день в поясе салона")] = None,
    master_id: int | None = None,
    client_id: int | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 100,
) -> Page[AppointmentOut]:
    query = booking.appointments_query(master_id=master_id, client_id=client_id)
    if date is not None:
        query = booking.limit_to_day(query, date)
    items, total = await booking.paginate(session, query, page=page, size=size)
    return Page(items=items, total=total, page=page, size=size)


@router.post(
    "/appointments",
    response_model=AppointmentOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse, "description": "Время занято"}},
    summary="Записать клиента (запись по телефону)",
    description=(
        "Либо `client_id` существующего клиента, либо объект `client` — тогда "
        "учётная запись создаётся на лету. Ограничение «не позднее чем за час» "
        "на администратора не распространяется."
    ),
)
async def create_appointment(
    data: AdminAppointmentCreate, _: AdminOnly, session: SessionDep
) -> AppointmentOut:
    return await admin.create_appointment_for_client(session, data)


@router.patch(
    "/appointments/{appointment_id}/status",
    response_model=AppointmentOut,
    responses={409: {"model": ErrorResponse, "description": "Недопустимый переход статуса"}},
    summary="Сменить статус записи",
)
async def set_status(
    appointment_id: int,
    data: AppointmentStatusUpdate,
    user: AdminOnly,
    session: SessionDep,
) -> AppointmentOut:
    await admin.set_appointment_status(session, appointment_id, data.status)
    return await booking.get_for_user(session, appointment_id, user)


# --- статистика ------------------------------------------------------------


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Статистика салона",
    description=(
        "Выручка по месяцам с накопительным итогом и приростом, топ услуг с "
        "рейтингом внутри категории, загрузка мастеров в процентах, "
        "дни недели и разрез по статусам. Все запросы — в db/sql/reports.sql."
    ),
)
async def get_stats(
    _: AdminOnly,
    session: SessionDep,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
) -> StatsResponse:
    default_from, default_to = stats.default_period()
    return await stats.collect(
        session,
        date_from=date_from or default_from,
        date_to=date_to or default_to,
    )
