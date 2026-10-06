"""Административное API."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import (
    Appointment,
    AppointmentStatus,
    Master,
    Service,
    User,
    WorkingHours,
)
from app.services import booking
from tests.conftest import auth_header, login

pytestmark = pytest.mark.integration

TZ = settings.salon_timezone


def next_monday() -> date:
    today = datetime.now(TZ).date()
    return today + timedelta(days=(7 - today.weekday()) or 7)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=TZ)


# ---------------------------------------------------------------------------
# Доступ
# ---------------------------------------------------------------------------

ADMIN_ENDPOINTS = [
    ("GET", "/api/admin/categories"),
    ("GET", "/api/admin/services"),
    ("GET", "/api/admin/masters"),
    ("GET", "/api/admin/appointments"),
    ("GET", "/api/admin/stats"),
]


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
async def test_client_cannot_reach_admin_endpoints(
    client: AsyncClient, client_user: User, method: str, path: str
) -> None:
    token = await login(client, client_user.email)

    response = await client.request(method, path, headers=auth_header(token))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
async def test_master_cannot_reach_admin_endpoints(
    client: AsyncClient, master_user: User, method: str, path: str
) -> None:
    token = await login(client, master_user.email)

    assert (await client.request(method, path, headers=auth_header(token))).status_code == 403


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
async def test_anonymous_cannot_reach_admin_endpoints(
    client: AsyncClient, method: str, path: str
) -> None:
    assert (await client.request(method, path)).status_code == 401


# ---------------------------------------------------------------------------
# Справочники
# ---------------------------------------------------------------------------


async def test_category_crud(client: AsyncClient, admin_user: User) -> None:
    token = await login(client, admin_user.email)

    created = await client.post(
        "/api/admin/categories",
        json={"name": "Брови и ресницы", "sort_order": 40},
        headers=auth_header(token),
    )
    assert created.status_code == 201
    category_id = created.json()["id"]

    renamed = await client.patch(
        f"/api/admin/categories/{category_id}",
        json={"name": "Взгляд"},
        headers=auth_header(token),
    )
    assert renamed.json()["name"] == "Взгляд"
    assert renamed.json()["sort_order"] == 40, "PATCH не должен обнулять незаданные поля"

    assert (
        await client.delete(f"/api/admin/categories/{category_id}", headers=auth_header(token))
    ).status_code == 204


async def test_category_with_services_cannot_be_deleted(
    client: AsyncClient, admin_user: User, master: Master
) -> None:
    token = await login(client, admin_user.email)

    response = await client.delete("/api/admin/categories/1", headers=auth_header(token))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "category_not_empty"


async def test_service_crud_and_validation(
    client: AsyncClient, admin_user: User, master: Master
) -> None:
    token = await login(client, admin_user.email)

    created = await client.post(
        "/api/admin/services",
        json={
            "category_id": 1,
            "name": "Ботокс для волос",
            "duration_min": 90,
            "price": "18000.00",
        },
        headers=auth_header(token),
    )
    assert created.status_code == 201
    service_id = created.json()["id"]
    assert created.json()["category_name"] == "Стрижки"

    bad = await client.post(
        "/api/admin/services",
        json={"category_id": 1, "name": "Кривая", "duration_min": 37, "price": "100"},
        headers=auth_header(token),
    )
    assert bad.status_code == 422, "длительность должна быть кратна пяти минутам"

    assert (
        await client.delete(f"/api/admin/services/{service_id}", headers=auth_header(token))
    ).status_code == 204


async def test_service_with_history_is_hidden_not_deleted(
    client: AsyncClient,
    session: AsyncSession,
    admin_user: User,
    master: Master,
    client_user: User,
) -> None:
    """Удалить услугу, по которой были визиты, нельзя — она скрывается."""
    from sqlalchemy.dialects.postgresql import Range

    session.add(
        Appointment(
            client_id=client_user.id,
            master_id=master.id,
            service_id=1,
            period=Range(at(next_monday(), 11), at(next_monday(), 12), bounds="[)"),
            price_at_booking=9000,
            status=AppointmentStatus.booked,
        )
    )
    await session.commit()

    token = await login(client, admin_user.email)
    assert (
        await client.delete("/api/admin/services/1", headers=auth_header(token))
    ).status_code == 204

    service = await session.get(Service, 1)
    assert service is not None, "услуга должна остаться в базе ради истории"
    await session.refresh(service)
    assert service.is_active is False


# ---------------------------------------------------------------------------
# Мастера, графики, отпуска
# ---------------------------------------------------------------------------


async def test_create_master_with_account(client: AsyncClient, admin_user: User) -> None:
    token = await login(client, admin_user.email)

    created = await client.post(
        "/api/admin/masters",
        json={
            "email": "newmaster@salon.dev",
            "password": "masterpass1",
            "full_name": "Новый Мастер",
            "phone": "+7 701 222 33 44",
            "bio": "Колорист",
        },
        headers=auth_header(token),
    )

    assert created.status_code == 201
    assert created.json()["full_name"] == "Новый Мастер"

    # Учётная запись действительно работает.
    master_token = await login(client, "newmaster@salon.dev", "masterpass1")
    me = await client.get("/api/auth/me", headers=auth_header(master_token))
    assert me.json()["role"] == "master"


async def test_overlapping_working_hours_rejected_by_database(
    client: AsyncClient, admin_user: User, master: Master
) -> None:
    """Пересечение рабочих интервалов ловит ограничение working_hours_no_overlap."""
    token = await login(client, admin_user.email)

    response = await client.post(
        f"/api/admin/masters/{master.id}/working-hours",
        json={"weekday": 0, "start_time": "12:00:00", "end_time": "20:00:00"},
        headers=auth_header(token),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "working_hours_overlap"


async def test_non_overlapping_working_hours_accepted(
    client: AsyncClient, admin_user: User, master: Master
) -> None:
    token = await login(client, admin_user.email)

    response = await client.post(
        f"/api/admin/masters/{master.id}/working-hours",
        json={"weekday": 5, "start_time": "10:00:00", "end_time": "16:00:00"},
        headers=auth_header(token),
    )

    assert response.status_code == 201


async def test_overlapping_time_off_rejected_by_database(
    client: AsyncClient, admin_user: User, master: Master
) -> None:
    token = await login(client, admin_user.email)
    day = next_monday()
    payload = {
        "starts_at": at(day, 0).isoformat(),
        "ends_at": at(day + timedelta(days=7), 0).isoformat(),
        "reason": "Отпуск",
    }

    assert (
        await client.post(
            f"/api/admin/masters/{master.id}/time-off",
            json=payload,
            headers=auth_header(token),
        )
    ).status_code == 201

    overlapping = await client.post(
        f"/api/admin/masters/{master.id}/time-off",
        json={**payload, "reason": "Ещё отпуск"},
        headers=auth_header(token),
    )

    assert overlapping.status_code == 409
    assert overlapping.json()["error"]["code"] == "time_off_overlap"


async def test_time_off_requires_correct_order(
    client: AsyncClient, admin_user: User, master: Master
) -> None:
    token = await login(client, admin_user.email)
    day = next_monday()

    response = await client.post(
        f"/api/admin/masters/{master.id}/time-off",
        json={"starts_at": at(day, 12).isoformat(), "ends_at": at(day, 10).isoformat()},
        headers=auth_header(token),
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Запись за клиента
# ---------------------------------------------------------------------------


async def test_admin_books_for_new_client_by_phone(
    client: AsyncClient, session: AsyncSession, admin_user: User, master: Master
) -> None:
    token = await login(client, admin_user.email)

    response = await client.post(
        "/api/admin/appointments",
        json={
            "service_id": 1,
            "master_id": master.id,
            "starts_at": at(next_monday(), 11).isoformat(),
            "client": {"full_name": "Гульнара Ким", "phone": "+7 707 999 88 77"},
            "comment": "записалась по телефону",
        },
        headers=auth_header(token),
    )

    assert response.status_code == 201, response.text
    assert response.json()["client_name"] == "Гульнара Ким"

    created_client = await session.scalar(select(User).where(User.full_name == "Гульнара Ким"))
    assert created_client is not None
    assert created_client.email.endswith("@phone.salon.local")
    assert created_client.role.value == "client"


async def test_admin_books_for_existing_client(
    client: AsyncClient, admin_user: User, master: Master, client_user: User
) -> None:
    token = await login(client, admin_user.email)

    response = await client.post(
        "/api/admin/appointments",
        json={
            "service_id": 1,
            "master_id": master.id,
            "starts_at": at(next_monday(), 11).isoformat(),
            "client_id": client_user.id,
        },
        headers=auth_header(token),
    )

    assert response.status_code == 201
    assert response.json()["client_id"] == client_user.id


async def test_admin_booking_requires_exactly_one_client_source(
    client: AsyncClient, admin_user: User, master: Master, client_user: User
) -> None:
    token = await login(client, admin_user.email)
    base = {
        "service_id": 1,
        "master_id": master.id,
        "starts_at": at(next_monday(), 11).isoformat(),
    }

    neither = await client.post("/api/admin/appointments", json=base, headers=auth_header(token))
    both = await client.post(
        "/api/admin/appointments",
        json={
            **base,
            "client_id": client_user.id,
            "client": {"full_name": "Кто-то Ещё", "phone": "+7 707 000 00 00"},
        },
        headers=auth_header(token),
    )

    assert neither.status_code == 422
    assert both.status_code == 422


async def test_admin_can_book_ignoring_lead_time(
    client: AsyncClient,
    session: AsyncSession,
    admin_user: User,
    master: Master,
    client_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Клиенту нужен час запаса до начала, администратору по телефону — нет.

    «Сейчас» подменяется фиксированным понедельником в полдень. Без этого
    тест зависел бы от времени прогона: смена на пять часов, начатая
    в 22:45, вышла бы за полночь, а схема такого не допускает
    (CHECK working_hours_time_order).
    """
    now = at(next_monday(), 12)
    monkeypatch.setattr(booking, "_now", lambda: now)

    shift_start = now
    for hours in master.working_hours:
        await session.delete(hours)
    await session.flush()
    session.add(
        WorkingHours(
            master_id=master.id,
            weekday=now.weekday(),
            start_time=shift_start.time(),
            end_time=(shift_start + timedelta(hours=5)).time(),
        )
    )
    await session.commit()

    soon = shift_start + timedelta(minutes=15)
    assert soon - now < timedelta(minutes=settings.min_lead_time_min), "запас меньше часа"
    payload = {
        "service_id": 1,
        "master_id": master.id,
        "starts_at": soon.isoformat(),
    }

    client_token = await login(client, client_user.email)
    as_client = await client.post(
        "/api/appointments", json=payload, headers=auth_header(client_token)
    )
    assert as_client.status_code == 422
    assert as_client.json()["error"]["code"] == "too_late_to_book"

    admin_token = await login(client, admin_user.email)
    as_admin = await client.post(
        "/api/admin/appointments",
        json={**payload, "client_id": client_user.id},
        headers=auth_header(admin_token),
    )
    assert as_admin.status_code == 201, as_admin.text


# ---------------------------------------------------------------------------
# Календарь дня и статусы
# ---------------------------------------------------------------------------


async def test_day_calendar_filters_by_date(
    client: AsyncClient, admin_user: User, master: Master, client_user: User
) -> None:
    token = await login(client, admin_user.email)
    day = next_monday()
    await client.post(
        "/api/admin/appointments",
        json={
            "service_id": 1,
            "master_id": master.id,
            "starts_at": at(day, 11).isoformat(),
            "client_id": client_user.id,
        },
        headers=auth_header(token),
    )

    same_day = await client.get(
        "/api/admin/appointments", params={"date": day.isoformat()}, headers=auth_header(token)
    )
    other_day = await client.get(
        "/api/admin/appointments",
        params={"date": (day + timedelta(days=1)).isoformat()},
        headers=auth_header(token),
    )

    assert same_day.json()["total"] == 1
    assert other_day.json()["total"] == 0


@pytest.mark.parametrize("new_status", ["completed", "no_show", "cancelled"])
async def test_admin_changes_status(
    client: AsyncClient,
    admin_user: User,
    master: Master,
    client_user: User,
    new_status: str,
) -> None:
    token = await login(client, admin_user.email)
    created = await client.post(
        "/api/admin/appointments",
        json={
            "service_id": 1,
            "master_id": master.id,
            "starts_at": at(next_monday(), 11).isoformat(),
            "client_id": client_user.id,
        },
        headers=auth_header(token),
    )
    appointment_id = created.json()["id"]

    response = await client.patch(
        f"/api/admin/appointments/{appointment_id}/status",
        json={"status": new_status},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == new_status
    # CHECK appointments_cancelled_at_consistent требует согласованности.
    assert (response.json()["cancelled_at"] is not None) == (new_status == "cancelled")


async def test_cancelled_appointment_cannot_be_revived(
    client: AsyncClient, admin_user: User, master: Master, client_user: User
) -> None:
    token = await login(client, admin_user.email)
    created = await client.post(
        "/api/admin/appointments",
        json={
            "service_id": 1,
            "master_id": master.id,
            "starts_at": at(next_monday(), 11).isoformat(),
            "client_id": client_user.id,
        },
        headers=auth_header(token),
    )
    appointment_id = created.json()["id"]

    await client.patch(
        f"/api/admin/appointments/{appointment_id}/status",
        json={"status": "cancelled"},
        headers=auth_header(token),
    )
    revive = await client.patch(
        f"/api/admin/appointments/{appointment_id}/status",
        json={"status": "booked"},
        headers=auth_header(token),
    )

    assert revive.status_code == 409
    assert revive.json()["error"]["code"] == "invalid_status_transition"


async def test_admin_sees_all_appointments(
    client: AsyncClient, session: AsyncSession, admin_user: User, master: Master, client_user: User
) -> None:
    from sqlalchemy.dialects.postgresql import Range

    session.add(
        Appointment(
            client_id=client_user.id,
            master_id=master.id,
            service_id=1,
            period=Range(at(next_monday(), 11), at(next_monday(), 12), bounds="[)"),
            price_at_booking=9000,
            status=AppointmentStatus.booked,
        )
    )
    await session.commit()

    token = await login(client, admin_user.email)
    listing = await client.get("/api/admin/appointments", headers=auth_header(token))

    assert listing.json()["total"] == 1
    total_in_db = await session.scalar(select(func.count()).select_from(Appointment))
    assert listing.json()["total"] == total_in_db
