"""Админ-статистика.

Весь SQL здесь «настоящий», не собранный ORM: он лежит в db/sql/reports.sql
и использует оконные функции (SUM() OVER, LAG, RANK), которые в SQLAlchemy
выражались бы заметно хуже, чем читаются в .sql.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.stats import (
    MasterUtilization,
    MonthlyRevenue,
    StatsResponse,
    StatusBreakdown,
    TopService,
    WeekdayLoad,
)
from app.services.sql_loader import query

REPORTS = "reports.sql"

#: Сколько месяцев показывать, если период не задан явно.
DEFAULT_MONTHS = 6


def default_period(today: date | None = None) -> tuple[date, date]:
    """Текущий месяц и пять предыдущих. date_to в период не включается."""
    anchor = today or date.today()
    start = anchor.replace(day=1)
    for _ in range(DEFAULT_MONTHS - 1):
        start = (start - timedelta(days=1)).replace(day=1)
    # Первое число следующего месяца: +32 дня гарантированно перепрыгивают
    # любой месяц, после чего отрезаем день.
    end = (anchor.replace(day=1) + timedelta(days=32)).replace(day=1)
    return start, end


async def _run[Model: BaseModel](
    session: AsyncSession, name: str, params: dict[str, Any], model: type[Model]
) -> list[Model]:
    rows = (await session.execute(query(REPORTS, name), params)).mappings().all()
    return [model.model_validate(dict(row)) for row in rows]


async def collect(session: AsyncSession, *, date_from: date, date_to: date) -> StatsResponse:
    params = {"date_from": date_from, "date_to": date_to, "tz": settings.salon_tz}

    return StatsResponse(
        date_from=date_from,
        date_to=date_to,
        timezone=settings.salon_tz,
        monthly_revenue=await _run(session, "monthly_revenue", params, MonthlyRevenue),
        top_services=await _run(session, "top_services", params, TopService),
        master_utilization=await _run(session, "master_utilization", params, MasterUtilization),
        busiest_weekdays=await _run(session, "busiest_weekdays", params, WeekdayLoad),
        status_breakdown=await _run(session, "status_breakdown", params, StatusBreakdown),
    )
