"""Представления БД как объекты SQLAlchemy.

Отдельная MetaData — намеренно: представления создаются миграцией
0002_views, и Alembic не должен пытаться выводить их из моделей.
Зато запросы к ним можно собирать обычным select(), а не склеивать строки.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import ENUM

view_metadata = MetaData()

#: Мастер x услуга с уже посчитанными COALESCE-ценой и длительностью.
#: Избавляет от повторения «цена мастера либо общая» в каждом запросе.
master_service_offer = Table(
    "v_master_service_offer",
    view_metadata,
    Column("master_id", BigInteger, primary_key=True),
    Column("master_name", String),
    Column("master_photo_url", String),
    Column("master_is_active", Boolean),
    Column("service_id", BigInteger, primary_key=True),
    Column("service_name", String),
    Column("service_is_active", Boolean),
    Column("category_id", BigInteger),
    Column("category_name", String),
    Column("category_sort_order", Integer),
    Column("price", Numeric(10, 2)),
    Column("duration_min", Integer),
    Column("has_custom_price", Boolean),
    Column("has_custom_duration", Boolean),
)

#: Визит со всеми именами и границами периода — основа админ-календаря
#: и расписания мастера. Заменяет пять JOIN в каждом запросе.
appointment_details = Table(
    "v_appointment_details",
    view_metadata,
    Column("id", BigInteger, primary_key=True),
    Column("status", ENUM(name="appointment_status", create_type=False)),
    Column("starts_at", DateTime(timezone=True)),
    Column("ends_at", DateTime(timezone=True)),
    Column("duration_min", Integer),
    Column("price_at_booking", Numeric(10, 2)),
    Column("comment", Text),
    Column("created_at", DateTime(timezone=True)),
    Column("cancelled_at", DateTime(timezone=True)),
    Column("client_id", BigInteger),
    Column("client_name", String),
    Column("client_phone", String),
    Column("client_email", String),
    Column("master_id", BigInteger),
    Column("master_name", String),
    Column("service_id", BigInteger),
    Column("service_name", String),
    Column("category_id", BigInteger),
    Column("category_name", String),
)
