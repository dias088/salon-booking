"""Создание, просмотр и отмена записей.

Проверка «можно ли занять это время» делается дважды, и это намеренно:

1. В приложении — чтобы вернуть внятную причину отказа: мастер не работает
   в это время, он в отпуске, слот уже прошёл.
2. В PostgreSQL — ограничением appointments_no_overlap. Это единственная
   проверка, которой можно доверять под нагрузкой: между шагом 1 и вставкой
   есть окно, в которое успевает влезть параллельный запрос. База такой
   гонки не допустит, а приложение превратит её 23P01 в 409 slot_taken.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    SlotTakenError,
    UnprocessableError,
)
from app.db.models import Appointment, AppointmentStatus, User, UserRole
from app.db.views import appointment_details
from app.schemas.appointment import AppointmentOut, AppointmentScope
from app.services.availability import Interval, free_slots
from app.services.slots import day_bounds, load_offers, master_day_context


class BookingNotAllowedError(UnprocessableError):
    code = "booking_not_allowed"


def _now() -> datetime:
    return datetime.now(settings.salon_timezone)


def can_cancel(starts_at: datetime, status: AppointmentStatus, now: datetime | None = None) -> bool:
    """Отменить можно только активную запись и не позже чем за два часа."""
    if status is not AppointmentStatus.booked:
        return False
    moment = now or _now()
    return starts_at - moment >= timedelta(minutes=settings.cancel_deadline_min)


def _row_to_out(row: dict[str, Any], now: datetime) -> AppointmentOut:
    return AppointmentOut(
        **row,
        can_cancel=can_cancel(row["starts_at"], AppointmentStatus(row["status"]), now),
    )


async def _fetch_details(session: AsyncSession, appointment_id: int) -> AppointmentOut:
    """Собранная запись из представления — чтобы не делать пять JOIN вручную."""
    row = (
        (
            await session.execute(
                select(appointment_details).where(appointment_details.c.id == appointment_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise NotFoundError("Запись не найдена")
    return _row_to_out(dict(row), _now())


async def create_appointment(
    session: AsyncSession,
    *,
    client_id: int,
    master_id: int,
    service_id: int,
    starts_at: datetime,
    comment: str | None = None,
    enforce_lead_time: bool = True,
) -> AppointmentOut:
    """Записывает клиента.

    :param enforce_lead_time: администратор записывает по телефону и может
        поставить визит хоть через пять минут; клиент — нет.
    """
    offers = await load_offers(session, service_id, master_id)
    if not offers:
        raise NotFoundError("Этот мастер не оказывает выбранную услугу")
    offer = offers[0]

    now = _now()
    starts_at = starts_at.astimezone(settings.salon_timezone)
    duration = timedelta(minutes=offer.duration_min)
    ends_at = starts_at + duration

    context = await master_day_context(session, master_id, starts_at.date())
    _assert_slot_is_bookable(
        starts_at=starts_at,
        duration=duration,
        context_work=context.work_intervals,
        context_busy=context.busy,
        now=now,
        enforce_lead_time=enforce_lead_time,
    )

    appointment = Appointment(
        client_id=client_id,
        master_id=master_id,
        service_id=service_id,
        period=Range(starts_at, ends_at, bounds="[)"),
        price_at_booking=offer.price,
        status=AppointmentStatus.booked,
        comment=comment,
    )
    session.add(appointment)
    # Ошибку 23P01 отсюда ловит общий обработчик IntegrityError и отдаёт 409.
    await session.flush()
    await session.commit()
    return await _fetch_details(session, appointment.id)


def _assert_slot_is_bookable(
    *,
    starts_at: datetime,
    duration: timedelta,
    context_work: list[Interval],
    context_busy: list[Interval],
    now: datetime,
    enforce_lead_time: bool,
) -> None:
    """Причина отказа понятным текстом. Финальное слово всё равно за БД."""
    requested = Interval(starts_at, starts_at + duration)

    if starts_at <= now:
        raise BookingNotAllowedError("Нельзя записаться на прошедшее время", code="slot_in_past")

    lead = timedelta(minutes=settings.min_lead_time_min if enforce_lead_time else 0)
    if starts_at < now + lead:
        raise BookingNotAllowedError(
            f"Записаться можно не позднее чем за {settings.min_lead_time_min} минут до начала",
            code="too_late_to_book",
        )

    if not any(work.contains(requested) for work in context_work):
        raise BookingNotAllowedError(
            "Мастер не работает в это время или услуга не помещается до конца смены",
            code="outside_working_hours",
        )

    if any(busy.overlaps(requested) for busy in context_busy):
        # Отличаем «уже занято» от «не работает»: клиенту это разные истории.
        raise SlotTakenError()

    # Последняя проверка — попадание в сетку слотов. Она же гарантирует, что
    # забронировать можно ровно то, что показывает /api/availability.
    offered = free_slots(
        work_intervals=context_work,
        busy=context_busy,
        duration=duration,
        step=timedelta(minutes=settings.slot_step_min),
        not_before=now + lead,
    )
    if starts_at not in offered:
        raise BookingNotAllowedError(
            "Это время не входит в сетку свободных слотов", code="not_a_valid_slot"
        )


def appointments_query(
    *,
    client_id: int | None = None,
    master_id: int | None = None,
    scope: AppointmentScope = "all",
    now: datetime | None = None,
) -> Select[Any]:
    query = select(appointment_details)
    if client_id is not None:
        query = query.where(appointment_details.c.client_id == client_id)
    if master_id is not None:
        query = query.where(appointment_details.c.master_id == master_id)

    moment = now or _now()
    if scope == "upcoming":
        query = query.where(
            appointment_details.c.starts_at >= moment,
            appointment_details.c.status == AppointmentStatus.booked,
        )
        return query.order_by(appointment_details.c.starts_at)
    if scope == "past":
        query = query.where(
            (appointment_details.c.starts_at < moment)
            | (appointment_details.c.status != AppointmentStatus.booked)
        )
    return query.order_by(appointment_details.c.starts_at.desc())


def limit_to_day(query: Select[Any], day: date) -> Select[Any]:
    """Сужает выборку до одних суток в часовом поясе салона.

    Границы считаются в местном времени, а не в UTC: «6 октября» для
    Алматы начинается в 19:00 UTC пятого числа.
    """
    return limit_to_range(query, day, day + timedelta(days=1))


def limit_to_range(query: Select[Any], day_from: date, day_to: date) -> Select[Any]:
    """Полуоткрытый диапазон дней [day_from, day_to) в поясе салона."""
    start, _ = day_bounds(day_from)
    end, _ = day_bounds(day_to)
    return query.where(
        appointment_details.c.starts_at >= start,
        appointment_details.c.starts_at < end,
    ).order_by(appointment_details.c.starts_at)


async def paginate(
    session: AsyncSession, query: Select[Any], *, page: int, size: int
) -> tuple[list[AppointmentOut], int]:
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (await session.execute(query.offset((page - 1) * size).limit(size))).mappings().all()
    now = _now()
    return [_row_to_out(dict(row), now) for row in rows], total


async def get_for_user(session: AsyncSession, appointment_id: int, user: User) -> AppointmentOut:
    """Чужая запись — 404, а не 403: существование чужих записей не раскрываем."""
    appointment = await session.get(Appointment, appointment_id)
    if appointment is None:
        raise NotFoundError("Запись не найдена")
    if user.role is UserRole.client and appointment.client_id != user.id:
        raise NotFoundError("Запись не найдена")
    return await _fetch_details(session, appointment_id)


async def cancel_appointment(
    session: AsyncSession, appointment_id: int, user: User
) -> AppointmentOut:
    appointment = await session.get(Appointment, appointment_id)
    if appointment is None:
        raise NotFoundError("Запись не найдена")

    is_owner = appointment.client_id == user.id
    if user.role is UserRole.client and not is_owner:
        raise NotFoundError("Запись не найдена")
    if user.role is UserRole.master:
        raise ForbiddenError("Мастер не отменяет записи, только отмечает их статус")

    if appointment.status is AppointmentStatus.cancelled:
        raise ConflictError("Запись уже отменена", code="already_cancelled")
    if appointment.status is not AppointmentStatus.booked:
        raise ConflictError("Завершённую запись отменить нельзя", code="not_cancellable")

    # Дедлайн действует только для клиента: администратор отменяет по звонку.
    if user.role is UserRole.client and not can_cancel(appointment.starts_at, appointment.status):
        raise ConflictError(
            f"Отменить можно не позднее чем за {settings.cancel_deadline_min // 60} часа "
            "до начала. Позвоните в салон",
            code="cancel_too_late",
        )

    appointment.status = AppointmentStatus.cancelled
    appointment.cancelled_at = datetime.now(UTC)
    await session.commit()
    return await _fetch_details(session, appointment_id)
