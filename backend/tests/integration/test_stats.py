"""Статистика: оконные запросы из db/sql/reports.sql на живой БД."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Appointment, AppointmentStatus, Master, User
from app.services.sql_loader import SQL_DIR, load_file, parse_blocks
from tests.conftest import auth_header, login

pytestmark = pytest.mark.integration

TZ = settings.salon_timezone

EXPECTED_QUERIES = {
    "monthly_revenue",
    "top_services",
    "master_utilization",
    "busiest_weekdays",
    "status_breakdown",
}


def at(day: date, hour: int) -> datetime:
    return datetime.combine(day, time(hour), tzinfo=TZ)


def completed(client_id: int, master_id: int, when: datetime, price: str) -> Appointment:
    return Appointment(
        client_id=client_id,
        master_id=master_id,
        service_id=1,
        period=Range(when, when + timedelta(hours=1), bounds="[)"),
        price_at_booking=Decimal(price),
        status=AppointmentStatus.completed,
    )


# ---------------------------------------------------------------------------
# Загрузчик SQL
# ---------------------------------------------------------------------------


def test_sql_loader_splits_named_blocks() -> None:
    blocks = parse_blocks("-- шапка\n-- name: first\nSELECT 1;\n\n-- name: second\nSELECT 2;\n")

    assert blocks == {"first": "SELECT 1", "second": "SELECT 2"}


def test_reports_file_contains_all_expected_queries() -> None:
    assert set(load_file("reports.sql")) >= EXPECTED_QUERIES


def test_report_params_use_cast_not_double_colon() -> None:
    """:param::type SQLAlchemy параметром не считает — только CAST(:param AS type)."""
    raw = (SQL_DIR / "reports.sql").read_text(encoding="utf-8")
    code = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("--"))

    assert ":date_from::" not in code
    assert ":date_to::" not in code
    assert ":tz::" not in code


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


async def test_stats_requires_admin(client: AsyncClient, client_user: User) -> None:
    token = await login(client, client_user.email)

    assert (await client.get("/api/admin/stats", headers=auth_header(token))).status_code == 403


async def test_all_report_queries_run_on_empty_database(
    client: AsyncClient, admin_user: User
) -> None:
    """Пустая база — отдельный случай: NULLIF и LAG не должны ломать запросы."""
    token = await login(client, admin_user.email)

    response = await client.get("/api/admin/stats", headers=auth_header(token))

    assert response.status_code == 200, response.text
    body = response.json()
    for key in EXPECTED_QUERIES:
        assert body[key] == [], f"{key} должен вернуть пустой список"


async def test_monthly_revenue_window_functions(
    client: AsyncClient, session: AsyncSession, admin_user: User, master: Master, client_user: User
) -> None:
    """SUM() OVER даёт накопительный итог, LAG — прирост к прошлому месяцу."""
    this_month = date.today().replace(day=1)
    prev_month = (this_month - timedelta(days=1)).replace(day=1)

    session.add(
        completed(client_user.id, master.id, at(prev_month + timedelta(days=5), 11), "10000")
    )
    session.add(
        completed(client_user.id, master.id, at(prev_month + timedelta(days=6), 11), "10000")
    )
    session.add(
        completed(client_user.id, master.id, at(this_month + timedelta(days=1), 11), "30000")
    )
    await session.commit()

    token = await login(client, admin_user.email)
    body = (
        await client.get(
            "/api/admin/stats",
            params={
                "date_from": prev_month.isoformat(),
                "date_to": (this_month + timedelta(days=40)).replace(day=1).isoformat(),
            },
            headers=auth_header(token),
        )
    ).json()

    months = body["monthly_revenue"]
    assert len(months) == 2

    first, second = months
    assert Decimal(first["revenue"]) == Decimal("20000.00")
    assert Decimal(first["revenue_cumulative"]) == Decimal("20000.00")
    assert first["revenue_prev_month"] is None, "у первого месяца нет предыдущего"

    assert Decimal(second["revenue"]) == Decimal("30000.00")
    assert Decimal(second["revenue_cumulative"]) == Decimal("50000.00"), "накопительный итог"
    assert Decimal(second["revenue_prev_month"]) == Decimal("20000.00")
    assert Decimal(second["revenue_growth_pct"]) == Decimal("50.0"), "рост на 50%"


async def test_only_completed_appointments_count_as_revenue(
    client: AsyncClient, session: AsyncSession, admin_user: User, master: Master, client_user: User
) -> None:
    day = date.today().replace(day=1) + timedelta(days=1)
    paid = completed(client_user.id, master.id, at(day, 11), "10000")
    cancelled = completed(client_user.id, master.id, at(day, 13), "99999")
    cancelled.status = AppointmentStatus.cancelled
    cancelled.cancelled_at = datetime.now(TZ)
    session.add_all([paid, cancelled])
    await session.commit()

    token = await login(client, admin_user.email)
    body = (await client.get("/api/admin/stats", headers=auth_header(token))).json()

    revenue = sum(Decimal(month["revenue"]) for month in body["monthly_revenue"])
    assert revenue == Decimal("10000.00"), "отменённая запись не должна попадать в выручку"

    statuses = {row["status"]: row["appointments"] for row in body["status_breakdown"]}
    assert statuses == {"completed": 1, "cancelled": 1}


async def test_top_services_ranking(
    client: AsyncClient, session: AsyncSession, admin_user: User, master: Master, client_user: User
) -> None:
    day = date.today().replace(day=1) + timedelta(days=1)
    session.add(completed(client_user.id, master.id, at(day, 11), "10000"))
    session.add(completed(client_user.id, master.id, at(day, 13), "20000"))
    await session.commit()

    token = await login(client, admin_user.email)
    body = (await client.get("/api/admin/stats", headers=auth_header(token))).json()

    top = body["top_services"]
    assert len(top) == 1
    assert top[0]["revenue_rank"] == 1
    assert top[0]["rank_in_category"] == 1
    assert Decimal(top[0]["revenue_share_pct"]) == Decimal("100.0")
    assert Decimal(top[0]["avg_price"]) == Decimal("15000.00")


async def test_master_utilization_is_a_percentage(
    client: AsyncClient, session: AsyncSession, admin_user: User, master: Master, client_user: User
) -> None:
    """Мастер работает 8 часов пять дней в неделю; одна часовая запись — малая доля."""
    day = date.today().replace(day=1) + timedelta(days=1)
    session.add(completed(client_user.id, master.id, at(day, 11), "10000"))
    await session.commit()

    token = await login(client, admin_user.email)
    body = (await client.get("/api/admin/stats", headers=auth_header(token))).json()

    rows = body["master_utilization"]
    assert len(rows) == 1
    row = rows[0]
    assert row["master_id"] == master.id
    assert Decimal(row["booked_min"]) == Decimal("60")
    assert Decimal(row["capacity_min"]) > 0
    assert 0 < Decimal(row["utilization_pct"]) < 100
    assert row["utilization_rank"] == 1


async def test_busiest_weekdays_uses_salon_timezone(
    client: AsyncClient, session: AsyncSession, admin_user: User, master: Master, client_user: User
) -> None:
    day = date.today().replace(day=1) + timedelta(days=1)
    session.add(completed(client_user.id, master.id, at(day, 11), "10000"))
    await session.commit()

    token = await login(client, admin_user.email)
    body = (await client.get("/api/admin/stats", headers=auth_header(token))).json()

    weekdays = body["busiest_weekdays"]
    assert len(weekdays) == 1
    assert weekdays[0]["weekday"] == day.weekday(), "0 — понедельник, как в working_hours"
    assert Decimal(weekdays[0]["share_pct"]) == Decimal("100.0")
