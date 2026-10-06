"""Административные операции: справочники, мастера, графики, записи."""

from __future__ import annotations

import secrets
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, EmailTakenError, NotFoundError, UnprocessableError
from app.core.security import hash_password
from app.db.models import (
    Appointment,
    AppointmentStatus,
    Master,
    MasterService,
    Service,
    ServiceCategory,
    TimeOff,
    User,
    UserRole,
    WorkingHours,
)
from app.schemas.admin import (
    AdminAppointmentCreate,
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
from app.services.booking import create_appointment

#: Домен для клиентов, заведённых по телефону без e-mail. Такой адрес
#: заведомо недоставляем, зато уникален и сразу виден в списке.
WALK_IN_EMAIL_DOMAIN = "phone.salon.local"


def _apply(target: object, data: dict[str, object]) -> None:
    """Частичное обновление: в PATCH приходят только изменённые поля."""
    for field, value in data.items():
        setattr(target, field, value)


# --- категории -------------------------------------------------------------


async def create_category(session: AsyncSession, data: CategoryCreate) -> ServiceCategory:
    category = ServiceCategory(**data.model_dump())
    session.add(category)
    await session.commit()
    return category


async def update_category(
    session: AsyncSession, category_id: int, data: CategoryUpdate
) -> ServiceCategory:
    category = await session.get(ServiceCategory, category_id)
    if category is None:
        raise NotFoundError("Категория не найдена")
    _apply(category, data.model_dump(exclude_unset=True))
    await session.commit()
    return category


async def delete_category(session: AsyncSession, category_id: int) -> None:
    category = await session.get(ServiceCategory, category_id)
    if category is None:
        raise NotFoundError("Категория не найдена")
    # ON DELETE RESTRICT на services.category_id всё равно не дал бы удалить,
    # но внятное сообщение лучше, чем 409 от драйвера.
    used = await session.scalar(
        select(Service.id).where(Service.category_id == category_id).limit(1)
    )
    if used is not None:
        raise ConflictError(
            "В категории есть услуги — сначала перенесите или удалите их",
            code="category_not_empty",
        )
    await session.delete(category)
    await session.commit()


# --- услуги ----------------------------------------------------------------


async def create_service(session: AsyncSession, data: ServiceCreate) -> Service:
    if await session.get(ServiceCategory, data.category_id) is None:
        raise NotFoundError("Категория не найдена")
    service = Service(**data.model_dump())
    session.add(service)
    await session.commit()
    await session.refresh(service, ["category"])
    return service


async def update_service(session: AsyncSession, service_id: int, data: ServiceUpdate) -> Service:
    service = await session.scalar(
        select(Service).where(Service.id == service_id).options(selectinload(Service.category))
    )
    if service is None:
        raise NotFoundError("Услуга не найдена")
    _apply(service, data.model_dump(exclude_unset=True))
    await session.commit()
    await session.refresh(service, ["category"])
    return service


async def delete_service(session: AsyncSession, service_id: int) -> None:
    """Мягкое удаление: услугу с историей визитов физически удалять нельзя."""
    service = await session.get(Service, service_id)
    if service is None:
        raise NotFoundError("Услуга не найдена")

    used = await session.scalar(
        select(Appointment.id).where(Appointment.service_id == service_id).limit(1)
    )
    if used is not None:
        service.is_active = False
        await session.commit()
        return

    await session.execute(delete(MasterService).where(MasterService.service_id == service_id))
    await session.delete(service)
    await session.commit()


# --- мастера ---------------------------------------------------------------


async def create_master(session: AsyncSession, data: MasterCreate) -> Master:
    exists = await session.scalar(select(User.id).where(User.email == data.email))
    if exists is not None:
        raise EmailTakenError()

    user = User(
        email=str(data.email),
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
        role=UserRole.master,
    )
    session.add(user)
    await session.flush()

    master = Master(user_id=user.id, bio=data.bio, photo_url=data.photo_url, is_active=True)
    session.add(master)
    await session.commit()
    await session.refresh(master, ["user"])
    return master


async def update_master(session: AsyncSession, master_id: int, data: MasterUpdate) -> Master:
    master = await session.scalar(
        select(Master).where(Master.id == master_id).options(selectinload(Master.user))
    )
    if master is None:
        raise NotFoundError("Мастер не найден")

    changes = data.model_dump(exclude_unset=True)
    for field in ("full_name", "phone"):
        if field in changes:
            setattr(master.user, field, changes.pop(field))
    _apply(master, changes)
    await session.commit()
    return master


async def set_master_services(
    session: AsyncSession, master_id: int, links: list[MasterServiceLink]
) -> None:
    """Полная замена набора услуг мастера."""
    if await session.get(Master, master_id) is None:
        raise NotFoundError("Мастер не найден")

    service_ids = [link.service_id for link in links]
    if len(set(service_ids)) != len(service_ids):
        raise UnprocessableError("Услуга указана дважды", code="duplicate_service")

    existing = set(
        (await session.scalars(select(Service.id).where(Service.id.in_(service_ids)))).all()
    )
    missing = sorted(set(service_ids) - existing)
    if missing:
        raise NotFoundError(f"Нет услуг с id: {missing}")

    await session.execute(delete(MasterService).where(MasterService.master_id == master_id))
    session.add_all(MasterService(master_id=master_id, **link.model_dump()) for link in links)
    await session.commit()


# --- график ----------------------------------------------------------------


async def add_working_hours(
    session: AsyncSession, master_id: int, data: WorkingHoursCreate
) -> WorkingHours:
    if await session.get(Master, master_id) is None:
        raise NotFoundError("Мастер не найден")
    hours = WorkingHours(master_id=master_id, **data.model_dump())
    session.add(hours)
    # Пересечение интервалов поймает working_hours_no_overlap -> 409.
    await session.commit()
    return hours


async def delete_working_hours(session: AsyncSession, master_id: int, hours_id: int) -> None:
    hours = await session.get(WorkingHours, hours_id)
    if hours is None or hours.master_id != master_id:
        raise NotFoundError("Интервал не найден")
    await session.delete(hours)
    await session.commit()


# --- отпуска ---------------------------------------------------------------


def _time_off_out(time_off: TimeOff) -> TimeOffOut:
    assert time_off.period.lower is not None
    assert time_off.period.upper is not None
    return TimeOffOut(
        id=time_off.id,
        master_id=time_off.master_id,
        starts_at=time_off.period.lower,
        ends_at=time_off.period.upper,
        reason=time_off.reason,
    )


async def list_time_off(session: AsyncSession, master_id: int) -> list[TimeOffOut]:
    rows = await session.scalars(
        select(TimeOff).where(TimeOff.master_id == master_id).order_by(TimeOff.id)
    )
    return [_time_off_out(row) for row in rows]


async def add_time_off(session: AsyncSession, master_id: int, data: TimeOffCreate) -> TimeOffOut:
    if await session.get(Master, master_id) is None:
        raise NotFoundError("Мастер не найден")
    time_off = TimeOff(
        master_id=master_id,
        period=Range(data.starts_at, data.ends_at, bounds="[)"),
        reason=data.reason,
    )
    session.add(time_off)
    # Пересечение с другим отпуском поймает time_off_no_overlap -> 409.
    await session.commit()
    return _time_off_out(time_off)


async def delete_time_off(session: AsyncSession, master_id: int, time_off_id: int) -> None:
    time_off = await session.get(TimeOff, time_off_id)
    if time_off is None or time_off.master_id != master_id:
        raise NotFoundError("Период не найден")
    await session.delete(time_off)
    await session.commit()


# --- записи ----------------------------------------------------------------


async def resolve_client(session: AsyncSession, data: AdminAppointmentCreate) -> int:
    """Существующий клиент либо новый, заведённый прямо на телефонном звонке."""
    if data.client_id is not None:
        user = await session.get(User, data.client_id)
        if user is None:
            raise NotFoundError("Клиент не найден")
        return user.id

    assert data.client is not None  # гарантировано валидатором схемы
    email = str(data.client.email) if data.client.email else _walk_in_email(data.client.phone)

    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        return existing.id

    user = User(
        email=email,
        # Пароль случайный: клиент восстановит его сам, если захочет войти.
        password_hash=hash_password(secrets.token_urlsafe(16)),
        full_name=data.client.full_name,
        phone=data.client.phone,
        role=UserRole.client,
    )
    session.add(user)
    await session.flush()
    return user.id


def _walk_in_email(phone: str) -> str:
    digits = "".join(character for character in phone if character.isdigit())
    return f"{digits}@{WALK_IN_EMAIL_DOMAIN}"


async def create_appointment_for_client(
    session: AsyncSession, data: AdminAppointmentCreate
) -> AppointmentOut:
    client_id = await resolve_client(session, data)
    # enforce_lead_time=False: по телефону записывают и «через двадцать минут».
    return await create_appointment(
        session,
        client_id=client_id,
        master_id=data.master_id,
        service_id=data.service_id,
        starts_at=data.starts_at,
        comment=data.comment,
        enforce_lead_time=False,
    )


#: Какие переходы статуса разрешены. Запись нельзя «разотменить» или
#: завершить дважды — это ловится здесь, а не падает в БД.
ALLOWED_TRANSITIONS: dict[AppointmentStatus, frozenset[AppointmentStatus]] = {
    AppointmentStatus.booked: frozenset(
        {AppointmentStatus.completed, AppointmentStatus.no_show, AppointmentStatus.cancelled}
    ),
    AppointmentStatus.completed: frozenset({AppointmentStatus.no_show}),
    AppointmentStatus.no_show: frozenset({AppointmentStatus.completed}),
    AppointmentStatus.cancelled: frozenset(),
}


async def set_appointment_status(
    session: AsyncSession,
    appointment_id: int,
    new_status: AppointmentStatus,
    *,
    master_id: int | None = None,
) -> Appointment:
    """:param master_id: если задан, мастер меняет статус только своей записи."""
    appointment = await session.get(Appointment, appointment_id)
    if appointment is None or (master_id is not None and appointment.master_id != master_id):
        raise NotFoundError("Запись не найдена")

    if new_status is appointment.status:
        return appointment

    if new_status not in ALLOWED_TRANSITIONS[appointment.status]:
        raise ConflictError(
            f"Нельзя перевести запись из «{appointment.status.value}» в «{new_status.value}»",
            code="invalid_status_transition",
        )

    appointment.status = new_status
    # CHECK appointments_cancelled_at_consistent требует согласованности.
    appointment.cancelled_at = (
        datetime.now(tz=appointment.created_at.tzinfo)
        if new_status is AppointmentStatus.cancelled
        else None
    )
    await session.commit()
    return appointment
