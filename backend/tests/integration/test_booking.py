"""Запись, отмена и защита от двойной брони."""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.models import Appointment, AppointmentStatus, Master, MasterService, User
from app.db.session import get_session
from app.main import app
from tests.conftest import UserFactory, auth_header, login

pytestmark = pytest.mark.integration

TZ = settings.salon_timezone


def next_monday() -> date:
    today = datetime.now(TZ).date()
    return today + timedelta(days=(7 - today.weekday()) or 7)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=TZ)


def booking_payload(
    master: Master, when: datetime, comment: str | None = None
) -> dict[str, object]:
    return {
        "service_id": 1,
        "master_id": master.id,
        "starts_at": when.isoformat(),
        "comment": comment,
    }


def make_appointment(
    *,
    client_id: int,
    master_id: int,
    starts_at: datetime,
    status: AppointmentStatus = AppointmentStatus.booked,
) -> Appointment:
    """Запись напрямую в БД — минуя проверки API, чтобы готовить состояние."""
    return Appointment(
        client_id=client_id,
        master_id=master_id,
        service_id=1,
        period=Range(starts_at, starts_at + timedelta(hours=1), bounds="[)"),
        price_at_booking=Decimal("9000.00"),
        status=status,
    )


# ---------------------------------------------------------------------------
# Создание
# ---------------------------------------------------------------------------


async def test_client_can_book_a_free_slot(
    client: AsyncClient, master: Master, client_user: User
) -> None:
    token = await login(client, client_user.email)
    when = at(next_monday(), 11, 0)

    response = await client.post(
        "/api/appointments",
        json=booking_payload(master, when, "первый раз"),
        headers=auth_header(token),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "booked"
    assert body["duration_min"] == 60
    assert body["price_at_booking"] == "9000.00"
    assert body["client_name"] == client_user.full_name
    assert body["service_name"] == "Женская стрижка"
    assert body["comment"] == "первый раз"
    assert body["can_cancel"] is True


async def test_price_is_frozen_at_booking_time(
    client: AsyncClient, session: AsyncSession, master: Master, client_user: User
) -> None:
    """Идея PriceAtBooking из курсовой схемы: переоценка прайса не трогает брони."""
    token = await login(client, client_user.email)
    created = await client.post(
        "/api/appointments",
        json=booking_payload(master, at(next_monday(), 11, 0)),
        headers=auth_header(token),
    )
    appointment_id = created.json()["id"]

    link = await session.get(MasterService, (master.id, 1))
    assert link is not None
    link.price_override = Decimal("99999.00")
    await session.commit()

    body = (
        await client.get(f"/api/appointments/{appointment_id}", headers=auth_header(token))
    ).json()
    assert body["price_at_booking"] == "9000.00"


async def test_booking_requires_authentication(client: AsyncClient, master: Master) -> None:
    response = await client.post(
        "/api/appointments", json=booking_payload(master, at(next_monday(), 11, 0))
    )

    assert response.status_code == 401


async def test_master_cannot_book_for_himself(
    client: AsyncClient, master: Master, master_user: User
) -> None:
    """Запись создаёт клиент. Мастеру и админу — отдельные ручки."""
    token = await login(client, master_user.email)

    response = await client.post(
        "/api/appointments",
        json=booking_payload(master, at(next_monday(), 11, 0)),
        headers=auth_header(token),
    )

    assert response.status_code == 403


async def test_booking_on_taken_time_returns_409(
    client: AsyncClient, session: AsyncSession, master: Master, client_user: User
) -> None:
    token = await login(client, client_user.email)
    when = at(next_monday(), 11, 0)
    session.add(make_appointment(client_id=client_user.id, master_id=master.id, starts_at=when))
    await session.commit()

    response = await client.post(
        "/api/appointments", json=booking_payload(master, when), headers=auth_header(token)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "slot_taken"


async def test_cancelled_appointment_frees_the_slot(
    client: AsyncClient, master: Master, client_user: User
) -> None:
    token = await login(client, client_user.email)
    when = at(next_monday(), 11, 0)

    first = await client.post(
        "/api/appointments", json=booking_payload(master, when), headers=auth_header(token)
    )
    assert first.status_code == 201

    blocked = await client.post(
        "/api/appointments", json=booking_payload(master, when), headers=auth_header(token)
    )
    assert blocked.status_code == 409

    cancelled = await client.post(
        f"/api/appointments/{first.json()['id']}/cancel", headers=auth_header(token)
    )
    assert cancelled.status_code == 200

    again = await client.post(
        "/api/appointments", json=booking_payload(master, when), headers=auth_header(token)
    )
    assert again.status_code == 201, "отменённая запись не должна держать слот"


@pytest.mark.parametrize(
    ("hour", "minute", "expected_code"),
    [
        (9, 0, "outside_working_hours"),  # смена начинается в 10:00
        (17, 30, "outside_working_hours"),  # часовая услуга не влезает до 18:00
        (11, 7, "not_a_valid_slot"),  # мимо сетки в 15 минут
    ],
)
async def test_invalid_times_are_rejected_with_reasons(
    client: AsyncClient,
    master: Master,
    client_user: User,
    hour: int,
    minute: int,
    expected_code: str,
) -> None:
    token = await login(client, client_user.email)

    response = await client.post(
        "/api/appointments",
        json=booking_payload(master, at(next_monday(), hour, minute)),
        headers=auth_header(token),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == expected_code


async def test_cannot_book_in_the_past(
    client: AsyncClient, master: Master, client_user: User
) -> None:
    token = await login(client, client_user.email)
    past = at(next_monday() - timedelta(days=7), 11, 0)

    response = await client.post(
        "/api/appointments", json=booking_payload(master, past), headers=auth_header(token)
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "slot_in_past"


async def test_master_must_offer_the_service(
    client: AsyncClient, session: AsyncSession, master: Master, client_user: User
) -> None:
    link = await session.get(MasterService, (master.id, 1))
    assert link is not None
    await session.delete(link)
    await session.commit()

    token = await login(client, client_user.email)
    response = await client.post(
        "/api/appointments",
        json=booking_payload(master, at(next_monday(), 11, 0)),
        headers=auth_header(token),
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Главный тест этапа: гонка
# ---------------------------------------------------------------------------


async def test_parallel_bookings_of_one_slot_leave_exactly_one_winner(
    session_factory: async_sessionmaker[AsyncSession],
    session: AsyncSession,
    master: Master,
    client_user: User,
) -> None:
    """Пять одновременных попыток занять один слот: ровно одна проходит.

    Проверка в коде тут принципиально бессильна — между «слот свободен» и
    INSERT есть окно. Единственное, что держит инвариант, — ограничение
    appointments_no_overlap в PostgreSQL: оно проверяется под блокировкой
    GiST-индекса, поэтому вторая и последующие транзакции получают 23P01.
    """
    parallel = 5
    when = at(next_monday(), 11, 0)

    async def override_get_session():  # type: ignore[no-untyped-def]
        async with session_factory() as db_session:
            yield db_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        # Отдельный HTTP-клиент на каждую попытку: своя сессия, своё соединение.
        clients = [
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            for _ in range(parallel)
        ]
        token = await login(clients[0], client_user.email)

        responses = await asyncio.gather(
            *(
                http.post(
                    "/api/appointments",
                    json=booking_payload(master, when),
                    headers=auth_header(token),
                )
                for http in clients
            )
        )
        for http in clients:
            await http.aclose()
    finally:
        app.dependency_overrides.clear()

    statuses = Counter(response.status_code for response in responses)
    assert statuses[201] == 1, f"победителей должно быть ровно 1, получено {statuses}"
    assert statuses[409] == parallel - 1, f"остальные должны получить 409: {statuses}"

    for response in responses:
        if response.status_code == 409:
            assert response.json()["error"]["code"] == "slot_taken"

    booked = await session.scalar(
        select(func.count())
        .select_from(Appointment)
        .where(Appointment.status == AppointmentStatus.booked)
    )
    assert booked == 1, "в базе не должно остаться двух пересекающихся записей"


# ---------------------------------------------------------------------------
# Свои записи и чужие
# ---------------------------------------------------------------------------


async def test_client_sees_only_own_appointments(
    client: AsyncClient,
    session: AsyncSession,
    master: Master,
    client_user: User,
    make_user: UserFactory,
) -> None:
    stranger = await make_user(email="stranger@test.dev")
    when = at(next_monday(), 11, 0)
    session.add(make_appointment(client_id=stranger.id, master_id=master.id, starts_at=when))
    await session.commit()
    stranger_appointment = await session.scalar(select(Appointment.id))

    token = await login(client, client_user.email)

    listing = (await client.get("/api/appointments/my", headers=auth_header(token))).json()
    assert listing["total"] == 0, "чужая запись не должна попадать в «мои»"

    direct = await client.get(
        f"/api/appointments/{stranger_appointment}", headers=auth_header(token)
    )
    assert direct.status_code == 404, "чужая запись маскируется под отсутствующую"


async def test_my_appointments_split_by_scope(
    client: AsyncClient, master: Master, client_user: User
) -> None:
    token = await login(client, client_user.email)
    await client.post(
        "/api/appointments",
        json=booking_payload(master, at(next_monday(), 11, 0)),
        headers=auth_header(token),
    )

    upcoming = (
        await client.get(
            "/api/appointments/my", params={"scope": "upcoming"}, headers=auth_header(token)
        )
    ).json()
    past = (
        await client.get(
            "/api/appointments/my", params={"scope": "past"}, headers=auth_header(token)
        )
    ).json()

    assert upcoming["total"] == 1
    assert past["total"] == 0


# ---------------------------------------------------------------------------
# Отмена
# ---------------------------------------------------------------------------


async def test_cancel_too_late_is_rejected(
    client: AsyncClient, session: AsyncSession, master: Master, client_user: User
) -> None:
    """Отменить можно не позже чем за два часа до начала."""
    soon = datetime.now(TZ) + timedelta(minutes=settings.cancel_deadline_min - 30)
    session.add(make_appointment(client_id=client_user.id, master_id=master.id, starts_at=soon))
    await session.commit()
    appointment_id = await session.scalar(select(Appointment.id))

    token = await login(client, client_user.email)
    response = await client.post(
        f"/api/appointments/{appointment_id}/cancel", headers=auth_header(token)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "cancel_too_late"

    detail = (
        await client.get(f"/api/appointments/{appointment_id}", headers=auth_header(token))
    ).json()
    assert detail["can_cancel"] is False, "клиенту заранее видно, что кнопку показывать нельзя"


async def test_admin_can_cancel_at_any_time(
    client: AsyncClient,
    session: AsyncSession,
    master: Master,
    client_user: User,
    admin_user: User,
) -> None:
    """Дедлайн — правило для клиента. Админ отменяет по звонку в любой момент."""
    soon = datetime.now(TZ) + timedelta(minutes=10)
    session.add(make_appointment(client_id=client_user.id, master_id=master.id, starts_at=soon))
    await session.commit()
    appointment_id = await session.scalar(select(Appointment.id))

    token = await login(client, admin_user.email)
    response = await client.post(
        f"/api/appointments/{appointment_id}/cancel", headers=auth_header(token)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["cancelled_at"] is not None


async def test_cancelling_twice_is_rejected(
    client: AsyncClient, master: Master, client_user: User
) -> None:
    token = await login(client, client_user.email)
    created = await client.post(
        "/api/appointments",
        json=booking_payload(master, at(next_monday(), 11, 0)),
        headers=auth_header(token),
    )
    appointment_id = created.json()["id"]

    assert (
        await client.post(f"/api/appointments/{appointment_id}/cancel", headers=auth_header(token))
    ).status_code == 200

    repeat = await client.post(
        f"/api/appointments/{appointment_id}/cancel", headers=auth_header(token)
    )
    assert repeat.status_code == 409
    assert repeat.json()["error"]["code"] == "already_cancelled"


async def test_client_cannot_cancel_someone_elses_appointment(
    client: AsyncClient,
    master: Master,
    client_user: User,
    make_user: UserFactory,
) -> None:
    owner_token = await login(client, client_user.email)
    created = await client.post(
        "/api/appointments",
        json=booking_payload(master, at(next_monday(), 11, 0)),
        headers=auth_header(owner_token),
    )
    appointment_id = created.json()["id"]

    await make_user(email="other@test.dev")
    other_token = await login(client, "other@test.dev")

    response = await client.post(
        f"/api/appointments/{appointment_id}/cancel", headers=auth_header(other_token)
    )

    assert response.status_code == 404
