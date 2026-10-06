"""Кабинет мастера: своё расписание и отметки о визитах."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Appointment, AppointmentStatus, Master, MasterService, User, UserRole
from tests.conftest import UserFactory, auth_header, login

pytestmark = pytest.mark.integration

TZ = settings.salon_timezone


def next_monday() -> date:
    today = datetime.now(TZ).date()
    return today + timedelta(days=(7 - today.weekday()) or 7)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=TZ)


def appointment(client_id: int, master_id: int, when: datetime) -> Appointment:
    return Appointment(
        client_id=client_id,
        master_id=master_id,
        service_id=1,
        period=Range(when, when + timedelta(hours=1), bounds="[)"),
        price_at_booking=9000,
        status=AppointmentStatus.booked,
    )


async def test_schedule_shows_only_own_appointments(
    client: AsyncClient,
    session: AsyncSession,
    master: Master,
    master_user: User,
    client_user: User,
    make_user: UserFactory,
) -> None:
    other_user = await make_user(email="other-master@test.dev", role=UserRole.master)
    other = Master(user_id=other_user.id, is_active=True)
    other.services.append(MasterService(service_id=1))
    session.add(other)
    await session.flush()

    day = next_monday()
    session.add(appointment(client_user.id, master.id, at(day, 11)))
    session.add(appointment(client_user.id, other.id, at(day, 11)))
    await session.commit()

    token = await login(client, master_user.email)
    schedule = await client.get(
        "/api/master/schedule", params={"date": day.isoformat()}, headers=auth_header(token)
    )

    assert schedule.status_code == 200
    assert schedule.json()["total"] == 1, "чужие записи в расписание попадать не должны"
    assert schedule.json()["items"][0]["master_id"] == master.id


async def test_schedule_supports_week_range(
    client: AsyncClient,
    session: AsyncSession,
    master: Master,
    master_user: User,
    client_user: User,
) -> None:
    day = next_monday()
    session.add(appointment(client_user.id, master.id, at(day, 11)))
    session.add(appointment(client_user.id, master.id, at(day + timedelta(days=2), 11)))
    session.add(appointment(client_user.id, master.id, at(day + timedelta(days=10), 11)))
    await session.commit()

    token = await login(client, master_user.email)
    week = await client.get(
        "/api/master/schedule",
        params={"date_from": day.isoformat(), "date_to": (day + timedelta(days=6)).isoformat()},
        headers=auth_header(token),
    )

    assert week.json()["total"] == 2, "третья запись лежит за пределами недели"


async def test_schedule_is_closed_for_clients(client: AsyncClient, client_user: User) -> None:
    token = await login(client, client_user.email)

    assert (await client.get("/api/master/schedule", headers=auth_header(token))).status_code == 403


@pytest.mark.parametrize("new_status", ["completed", "no_show"])
async def test_master_marks_visit(
    client: AsyncClient,
    session: AsyncSession,
    master: Master,
    master_user: User,
    client_user: User,
    new_status: str,
) -> None:
    session.add(appointment(client_user.id, master.id, at(next_monday(), 11)))
    await session.commit()
    appointment_id = (await session.scalars(select(Appointment.id))).one()

    token = await login(client, master_user.email)
    response = await client.patch(
        f"/api/master/appointments/{appointment_id}/status",
        json={"status": new_status},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == new_status


async def test_master_cannot_cancel_through_status(
    client: AsyncClient,
    session: AsyncSession,
    master: Master,
    master_user: User,
    client_user: User,
) -> None:
    """Отмена — к администратору: за ней тянутся возврат и разговор с клиентом."""
    session.add(appointment(client_user.id, master.id, at(next_monday(), 11)))
    await session.commit()
    appointment_id = (await session.scalars(select(Appointment.id))).one()

    token = await login(client, master_user.email)
    response = await client.patch(
        f"/api/master/appointments/{appointment_id}/status",
        json={"status": "cancelled"},
        headers=auth_header(token),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "status_not_allowed"


async def test_master_cannot_touch_someone_elses_appointment(
    client: AsyncClient,
    session: AsyncSession,
    master: Master,
    master_user: User,
    client_user: User,
    make_user: UserFactory,
) -> None:
    other_user = await make_user(email="other-master@test.dev", role=UserRole.master)
    other = Master(user_id=other_user.id, is_active=True)
    session.add(other)
    await session.flush()
    session.add(appointment(client_user.id, other.id, at(next_monday(), 11)))
    await session.commit()
    appointment_id = (await session.scalars(select(Appointment.id))).one()

    token = await login(client, master_user.email)
    response = await client.patch(
        f"/api/master/appointments/{appointment_id}/status",
        json={"status": "completed"},
        headers=auth_header(token),
    )

    assert response.status_code == 404, "чужая запись маскируется под отсутствующую"
