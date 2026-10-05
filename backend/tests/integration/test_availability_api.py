"""Слоты через API: данные берутся из БД, арифметика — из чистого модуля."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import (
    Appointment,
    AppointmentStatus,
    Master,
    MasterService,
    Service,
    TimeOff,
    User,
    UserRole,
    WorkingHours,
)

pytestmark = pytest.mark.integration

TZ = settings.salon_timezone


def next_monday(reference: date | None = None) -> date:
    """Ближайший будущий понедельник — чтобы тесты не зависели от дня прогона."""
    today = reference or datetime.now(TZ).date()
    return today + timedelta(days=(7 - today.weekday()) or 7)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=TZ)


def slot_times(payload: dict[str, Any], master_index: int = 0) -> list[str]:
    return [
        datetime.fromisoformat(value).astimezone(TZ).strftime("%H:%M")
        for value in payload["masters"][master_index]["slots"]
    ]


async def test_slots_follow_working_hours(client: AsyncClient, master: Master) -> None:
    day = next_monday()

    response = await client.get(
        "/api/availability", params={"service_id": 1, "date": day.isoformat()}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == settings.salon_tz
    assert body["service_name"] == "Женская стрижка"
    # График пн-пт 10:00-18:00, услуга 60 минут -> последний слот 17:00.
    assert slot_times(body)[0] == "10:00"
    assert slot_times(body)[-1] == "17:00"


async def test_day_off_has_no_slots(client: AsyncClient, master: Master) -> None:
    """Фикстура даёт график только пн-пт, значит в воскресенье пусто."""
    sunday = next_monday() - timedelta(days=1)

    body = (
        await client.get("/api/availability", params={"service_id": 1, "date": sunday.isoformat()})
    ).json()

    assert slot_times(body) == []
    assert body["slots"] == []


async def test_existing_appointment_blocks_its_time(
    client: AsyncClient, session: AsyncSession, master: Master, client_user: User
) -> None:
    day = next_monday()
    session.add(
        Appointment(
            client_id=client_user.id,
            master_id=master.id,
            service_id=1,
            period=Range(at(day, 12, 0), at(day, 13, 0), bounds="[)"),
            price_at_booking=Decimal("9000.00"),
            status=AppointmentStatus.booked,
        )
    )
    await session.commit()

    body = (
        await client.get("/api/availability", params={"service_id": 1, "date": day.isoformat()})
    ).json()

    assert "12:00" not in slot_times(body)
    assert "11:15" not in slot_times(body), "часовая услуга в 11:15 наехала бы на запись"
    assert "11:00" in slot_times(body), "а в 11:00 заканчивается ровно к началу записи"
    assert "13:00" in slot_times(body), "сразу после записи время свободно"


async def test_cancelled_appointment_frees_the_slot(
    client: AsyncClient, session: AsyncSession, master: Master, client_user: User
) -> None:
    day = next_monday()
    session.add(
        Appointment(
            client_id=client_user.id,
            master_id=master.id,
            service_id=1,
            period=Range(at(day, 12, 0), at(day, 13, 0), bounds="[)"),
            price_at_booking=Decimal("9000.00"),
            status=AppointmentStatus.cancelled,
            cancelled_at=datetime.now(TZ),
        )
    )
    await session.commit()

    body = (
        await client.get("/api/availability", params={"service_id": 1, "date": day.isoformat()})
    ).json()

    assert "12:00" in slot_times(body)


async def test_time_off_removes_the_whole_day(
    client: AsyncClient, session: AsyncSession, master: Master
) -> None:
    day = next_monday()
    session.add(
        TimeOff(
            master_id=master.id,
            period=Range(at(day, 0, 0), at(day + timedelta(days=1), 0, 0), bounds="[)"),
            reason="Отпуск",
        )
    )
    await session.commit()

    body = (
        await client.get("/api/availability", params={"service_id": 1, "date": day.isoformat()})
    ).json()

    assert slot_times(body) == []


async def test_lunch_break_creates_a_gap(
    client: AsyncClient, session: AsyncSession, master: Master
) -> None:
    """Меняем график на два интервала с обедом 14:00-15:00."""
    for hours in master.working_hours:
        await session.delete(hours)
    await session.flush()
    for weekday in range(5):
        session.add_all(
            [
                WorkingHours(
                    master_id=master.id,
                    weekday=weekday,
                    start_time=time(10, 0),
                    end_time=time(14, 0),
                ),
                WorkingHours(
                    master_id=master.id,
                    weekday=weekday,
                    start_time=time(15, 0),
                    end_time=time(19, 0),
                ),
            ]
        )
    await session.commit()

    day = next_monday()
    body = (
        await client.get("/api/availability", params={"service_id": 1, "date": day.isoformat()})
    ).json()

    assert "13:00" in slot_times(body)
    assert "13:15" not in slot_times(body)
    assert "14:00" not in slot_times(body)
    assert "15:00" in slot_times(body)
    assert slot_times(body)[-1] == "18:00"


async def test_past_time_is_not_offered(client: AsyncClient, master: Master) -> None:
    """На сегодня слоты раньше «сейчас + час» не предлагаются."""
    today = datetime.now(TZ)
    if today.weekday() > 4:
        pytest.skip("мастер работает только пн-пт")

    body = (
        await client.get(
            "/api/availability", params={"service_id": 1, "date": today.date().isoformat()}
        )
    ).json()

    earliest_allowed = today + timedelta(minutes=settings.min_lead_time_min)
    for value in body["masters"][0]["slots"]:
        assert datetime.fromisoformat(value) >= earliest_allowed


async def test_any_master_mode_merges_slots(
    client: AsyncClient, session: AsyncSession, master: Master
) -> None:
    """Без master_id возвращаются слоты всех мастеров, оказывающих услугу."""
    second_user = User(
        email="second@test.dev",
        password_hash="x",
        full_name="Второй Мастер",
        phone="+7 700 111 11 11",
        role=UserRole.master,
    )
    session.add(second_user)
    await session.flush()
    second = Master(user_id=second_user.id, is_active=True)
    second.services.append(MasterService(service_id=1, duration_min_override=30))
    # Работает только во второй половине дня.
    for weekday in range(5):
        second.working_hours.append(
            WorkingHours(weekday=weekday, start_time=time(16, 0), end_time=time(20, 0))
        )
    session.add(second)
    await session.commit()

    day = next_monday()
    body = (
        await client.get("/api/availability", params={"service_id": 1, "date": day.isoformat()})
    ).json()

    assert len(body["masters"]) == 2
    merged = {
        datetime.fromisoformat(slot["starts_at"]).astimezone(TZ).strftime("%H:%M"): slot[
            "master_ids"
        ]
        for slot in body["slots"]
    }
    assert len(merged["16:00"]) == 2, "в 16:00 свободны оба мастера"
    assert merged["10:00"] == [master.id], "в 10:00 только первый"
    assert merged["19:00"] == [second.id], "в 19:00 только второй"


async def test_filter_by_master(client: AsyncClient, master: Master) -> None:
    day = next_monday()

    body = (
        await client.get(
            "/api/availability",
            params={"service_id": 1, "date": day.isoformat(), "master_id": master.id},
        )
    ).json()

    assert len(body["masters"]) == 1
    assert body["masters"][0]["master_id"] == master.id


async def test_unknown_service_is_404(client: AsyncClient) -> None:
    response = await client.get(
        "/api/availability", params={"service_id": 999, "date": next_monday().isoformat()}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_master_specific_duration_shortens_slots(
    client: AsyncClient, session: AsyncSession, master: Master
) -> None:
    link = await session.get(MasterService, (master.id, 1))
    assert link is not None
    link.duration_min_override = 30
    await session.commit()

    day = next_monday()
    body = (
        await client.get("/api/availability", params={"service_id": 1, "date": day.isoformat()})
    ).json()

    assert body["masters"][0]["duration_min"] == 30
    # 30-минутная услуга успевает начаться и в 17:30.
    assert slot_times(body)[-1] == "17:30"


async def test_service_must_exist_and_be_active(
    client: AsyncClient, session: AsyncSession, master: Master
) -> None:
    service = await session.get(Service, 1)
    assert service is not None
    service.is_active = False
    await session.commit()

    response = await client.get(
        "/api/availability", params={"service_id": 1, "date": next_monday().isoformat()}
    )

    assert response.status_code == 404
