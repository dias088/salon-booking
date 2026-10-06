"""Схемы админ-статистики.

Поля повторяют колонки запросов из db/sql/reports.sql один в один.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class MonthlyRevenue(BaseModel):
    month: date
    appointments: int
    revenue: Decimal
    revenue_cumulative: Decimal = Field(description="Накопительно с начала периода, SUM() OVER")
    revenue_prev_month: Decimal | None = Field(description="LAG() по предыдущему месяцу")
    revenue_growth_pct: Decimal | None = Field(description="Прирост к прошлому месяцу, %")


class TopService(BaseModel):
    service_id: int
    service_name: str
    category_name: str
    appointments: int
    revenue: Decimal
    avg_price: Decimal
    revenue_rank: int = Field(description="RANK() по всей выручке периода")
    rank_in_category: int = Field(description="RANK() внутри категории")
    revenue_share_pct: Decimal | None


class MasterUtilization(BaseModel):
    master_id: int
    master_name: str
    capacity_min: Decimal = Field(description="Рабочие минуты по графику за вычетом отпусков")
    booked_min: Decimal
    appointments: int
    revenue: Decimal
    utilization_pct: Decimal | None = Field(description="booked_min / capacity_min в процентах")
    utilization_rank: int


class WeekdayLoad(BaseModel):
    weekday: int = Field(ge=0, le=6)
    weekday_name: str
    appointments: int
    share_pct: Decimal | None


class StatusBreakdown(BaseModel):
    status: str
    appointments: int
    amount: Decimal
    share_pct: Decimal | None


class StatsResponse(BaseModel):
    date_from: date
    date_to: date = Field(description="Не включается в период")
    timezone: str
    monthly_revenue: list[MonthlyRevenue]
    top_services: list[TopService]
    master_utilization: list[MasterUtilization]
    busiest_weekdays: list[WeekdayLoad]
    status_breakdown: list[StatusBreakdown]
