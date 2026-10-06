"""Сборка свободных слотов: данные из БД -> чистый алгоритм -> ответ API.

Разделение намеренное. Здесь только запросы и перевод дат в часовой пояс
салона; вся арифметика интервалов живёт в availability.py и покрыта
юнит-тестами без базы.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date as date_type
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError
from app.db.models import Appointment, AppointmentStatus, Service, TimeOff, WorkingHours
from app.db.views import master_service_offer
from app.schemas.availability import AnyMasterSlot, AvailabilityResponse, MasterSlots
from app.services.availability import Interval, free_slots

#: Отменённые записи слот не держат — это и есть смысл частичного
#: EXCLUDE-ограничения appointments_no_overlap в БД.
BLOCKING_STATUSES = [
    status for status in AppointmentStatus if status is not AppointmentStatus.cancelled
]


class Offer(NamedTuple):
    """Предложение услуги конкретным мастером с эффективными ценой и длительностью."""

    master_id: int
    master_name: str
    photo_url: str | None
    price: Decimal
    duration_min: int


def today_in_salon() -> date_type:
    """Сегодня по часовому поясу салона, а не по времени сервера."""
    return datetime.now(settings.salon_timezone).date()


def day_bounds(day: date_type) -> tuple[datetime, datetime]:
    """Границы местных суток салона в виде aware datetime.

    Считать слоты в UTC нельзя: день «10 октября» для клиента в Алматы
    начинается в 19:00 UTC предыдущего дня.
    """
    tz = settings.salon_timezone
    start = datetime.combine(day, time.min, tzinfo=tz)
    return start, start + timedelta(days=1)


async def load_offers(
    session: AsyncSession, service_id: int, master_id: int | None = None
) -> list[Offer]:
    query = select(
        master_service_offer.c.master_id,
        master_service_offer.c.master_name,
        master_service_offer.c.master_photo_url,
        master_service_offer.c.price,
        master_service_offer.c.duration_min,
    ).where(
        master_service_offer.c.service_id == service_id,
        master_service_offer.c.service_is_active.is_(True),
        master_service_offer.c.master_is_active.is_(True),
    )
    if master_id is not None:
        query = query.where(master_service_offer.c.master_id == master_id)

    rows = (await session.execute(query.order_by(master_service_offer.c.master_name))).all()
    return [Offer(*row) for row in rows]


async def busy_by_master(
    session: AsyncSession, master_ids: list[int], window: Interval
) -> dict[int, list[Interval]]:
    """Занятое время: активные визиты плюс периоды отсутствия."""
    busy: dict[int, list[Interval]] = defaultdict(list)
    if not master_ids:
        return busy

    window_range = Range(window.start, window.end, bounds="[)")

    appointments = await session.execute(
        select(Appointment.master_id, Appointment.period).where(
            Appointment.master_id.in_(master_ids),
            Appointment.status.in_(BLOCKING_STATUSES),
            Appointment.period.op("&&")(window_range),
        )
    )
    time_off = await session.execute(
        select(TimeOff.master_id, TimeOff.period).where(
            TimeOff.master_id.in_(master_ids),
            TimeOff.period.op("&&")(window_range),
        )
    )

    for master_id, period in list(appointments) + list(time_off):
        if period.lower is not None and period.upper is not None:
            busy[master_id].append(Interval(period.lower, period.upper))
    return busy


async def work_intervals_by_master(
    session: AsyncSession, master_ids: list[int], day: date_type
) -> dict[int, list[Interval]]:
    """Рабочие интервалы на конкретную дату из недельного графика."""
    intervals: dict[int, list[Interval]] = defaultdict(list)
    if not master_ids:
        return intervals

    tz = settings.salon_timezone
    rows = await session.scalars(
        select(WorkingHours).where(
            WorkingHours.master_id.in_(master_ids),
            WorkingHours.weekday == day.weekday(),
        )
    )
    for hours in rows:
        intervals[hours.master_id].append(
            Interval(
                datetime.combine(day, hours.start_time, tzinfo=tz),
                datetime.combine(day, hours.end_time, tzinfo=tz),
            )
        )
    return intervals


class MasterDayContext(NamedTuple):
    """Всё, что нужно знать о дне одного мастера, чтобы посчитать слоты."""

    work_intervals: list[Interval]
    busy: list[Interval]


async def master_day_context(
    session: AsyncSession, master_id: int, day: date_type
) -> MasterDayContext:
    """График и занятость одного мастера за день.

    Используется и поиском слотов, и созданием записи: так проверка при
    бронировании гарантированно совпадает с тем, что показал /availability.
    """
    window_start, window_end = day_bounds(day)
    window = Interval(window_start, window_end)
    work = await work_intervals_by_master(session, [master_id], day)
    busy = await busy_by_master(session, [master_id], window)
    return MasterDayContext(work.get(master_id, []), busy.get(master_id, []))


async def day_availability(
    session: AsyncSession,
    *,
    service_id: int,
    day: date_type,
    master_id: int | None = None,
    now: datetime | None = None,
) -> AvailabilityResponse:
    service = await session.get(Service, service_id)
    if service is None or not service.is_active:
        raise NotFoundError("Услуга не найдена")

    moment = now or datetime.now(settings.salon_timezone)
    # Записаться впритык нельзя: мастеру нужен запас на подготовку.
    not_before = moment + timedelta(minutes=settings.min_lead_time_min)
    step = timedelta(minutes=settings.slot_step_min)

    offers = await load_offers(session, service_id, master_id)
    master_ids = [offer.master_id for offer in offers]

    window_start, window_end = day_bounds(day)
    window = Interval(window_start, window_end)
    work_intervals = await work_intervals_by_master(session, master_ids, day)
    busy = await busy_by_master(session, master_ids, window)

    per_master: list[MasterSlots] = []
    by_start: dict[datetime, list[int]] = defaultdict(list)

    for offer in offers:
        duration = timedelta(minutes=offer.duration_min)
        starts = free_slots(
            work_intervals=work_intervals.get(offer.master_id, []),
            busy=busy.get(offer.master_id, []),
            duration=duration,
            step=step,
            not_before=not_before,
        )
        per_master.append(
            MasterSlots(
                master_id=offer.master_id,
                master_name=offer.master_name,
                photo_url=offer.photo_url,
                price=offer.price,
                duration_min=offer.duration_min,
                slots=starts,
            )
        )
        for start in starts:
            by_start[start].append(offer.master_id)

    durations = {offer.master_id: offer.duration_min for offer in offers}
    combined = [
        AnyMasterSlot(
            starts_at=start,
            # Длительность может отличаться у разных мастеров — для сводного
            # списка берём минимальную, её хватает всем свободным.
            ends_at=start + timedelta(minutes=min(durations[m] for m in ids)),
            master_ids=sorted(ids),
        )
        for start, ids in sorted(by_start.items())
    ]

    return AvailabilityResponse(
        date=day,
        service_id=service.id,
        service_name=service.name,
        timezone=settings.salon_tz,
        masters=per_master,
        slots=combined,
    )
