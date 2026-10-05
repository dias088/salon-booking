"""initial schema

Схема «Онлайн-запись в салон красоты». Переработана из курсового проекта
Hair Salon Management System (см. db/course/):

  CLIENT + STYLIST.Email        -> users (единая личность + роль + пароль)
  STYLIST                       -> masters (профиль) + working_hours + time_off
  STYLIST.Specialization        -> master_services (связь M:N вместо текста)
  SERVICE.Category              -> service_categories (справочник вместо VARCHAR)
  APPOINTMENT.Date + .Time      -> appointments.period tstzrange
  APPOINTMENT_SERVICE.PriceAtBooking -> appointments.price_at_booking
  STATION / PRODUCT / PAYMENT   -> удалены (вне ТЗ)

Главное, чего в курсовой схеме не было в принципе: защита от пересечения
записей силами самой БД — ограничение EXCLUDE USING gist.

Revision ID: 0001
Revises:
Create Date: 2026-10-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = postgresql.ENUM(
    "client", "master", "admin", name="user_role", create_type=False
)
appointment_status = postgresql.ENUM(
    "booked", "completed", "cancelled", "no_show", name="appointment_status", create_type=False
)


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # Расширения и типы
    # ------------------------------------------------------------------ #
    # btree_gist даёт GiST-операторы для скалярных типов (=), без него
    # нельзя смешать "master_id WITH =" и "period WITH &&" в одном EXCLUDE.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    # citext — регистронезависимый текст для e-mail.
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.execute("CREATE TYPE user_role AS ENUM ('client', 'master', 'admin')")
    op.execute(
        "CREATE TYPE appointment_status AS ENUM "
        "('booked', 'completed', 'cancelled', 'no_show')"
    )
    # В PostgreSQL нет встроенного диапазона для time, поэтому объявляем свой:
    # он нужен, чтобы EXCLUDE ловил пересекающиеся рабочие интервалы.
    op.execute("CREATE TYPE timerange AS RANGE (subtype = time)")

    # ------------------------------------------------------------------ #
    # users / refresh_tokens
    # ------------------------------------------------------------------ #
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("role", user_role, server_default="client", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="users_pkey"),
        sa.UniqueConstraint("email", name="users_email_key"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="refresh_tokens_user_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="refresh_tokens_pkey"),
        sa.UniqueConstraint("token_hash", name="refresh_tokens_token_hash_key"),
    )
    op.create_index("refresh_tokens_user_id_idx", "refresh_tokens", ["user_id"])

    # ------------------------------------------------------------------ #
    # masters / working_hours / time_off
    # ------------------------------------------------------------------ #
    op.create_table(
        "masters",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="masters_user_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="masters_pkey"),
        sa.UniqueConstraint("user_id", name="masters_user_id_key"),
    )

    op.create_table(
        "working_hours",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("master_id", sa.BigInteger(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        # Имена CHECK короткие: Alembic берёт naming_convention из
        # target_metadata и сам добавит префикс таблицы (см. app/db/base.py).
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        sa.CheckConstraint("end_time > start_time", name="time_order"),
        sa.ForeignKeyConstraint(
            ["master_id"], ["masters.id"], name="working_hours_master_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="working_hours_pkey"),
    )
    op.create_index("working_hours_master_id_idx", "working_hours", ["master_id"])
    # Два рабочих интервала одного мастера в один день недели не пересекаются.
    op.execute(
        """
        ALTER TABLE working_hours
            ADD CONSTRAINT working_hours_no_overlap
            EXCLUDE USING gist (
                master_id WITH =,
                weekday   WITH =,
                timerange(start_time, end_time) WITH &&
            )
        """
    )

    op.create_table(
        "time_off",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("master_id", sa.BigInteger(), nullable=False),
        sa.Column("period", postgresql.TSTZRANGE(), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.CheckConstraint(
            "lower(period) IS NOT NULL AND upper(period) IS NOT NULL AND NOT isempty(period)",
            name="period_bounded",
        ),
        sa.ForeignKeyConstraint(
            ["master_id"], ["masters.id"], name="time_off_master_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="time_off_pkey"),
    )
    op.create_index("time_off_master_id_idx", "time_off", ["master_id"])
    op.execute(
        """
        ALTER TABLE time_off
            ADD CONSTRAINT time_off_no_overlap
            EXCLUDE USING gist (master_id WITH =, period WITH &&)
        """
    )

    # ------------------------------------------------------------------ #
    # каталог: service_categories / services / master_services
    # ------------------------------------------------------------------ #
    op.create_table(
        "service_categories",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="service_categories_pkey"),
        sa.UniqueConstraint("name", name="service_categories_name_key"),
    )

    op.create_table(
        "services",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint("duration_min > 0", name="duration_positive"),
        sa.CheckConstraint("price >= 0", name="price_non_negative"),
        sa.CheckConstraint("mod(duration_min, 5) = 0", name="duration_step"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["service_categories.id"],
            name="services_category_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="services_pkey"),
        sa.UniqueConstraint("name", name="services_name_key"),
    )
    op.create_index("services_category_id_idx", "services", ["category_id"])

    op.create_table(
        "master_services",
        sa.Column("master_id", sa.BigInteger(), nullable=False),
        sa.Column("service_id", sa.BigInteger(), nullable=False),
        sa.Column("price_override", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("duration_min_override", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "price_override IS NULL OR price_override >= 0",
            name="price_non_negative",
        ),
        sa.CheckConstraint(
            "duration_min_override IS NULL OR "
            "(duration_min_override > 0 AND mod(duration_min_override, 5) = 0)",
            name="duration_valid",
        ),
        sa.ForeignKeyConstraint(
            ["master_id"], ["masters.id"], name="master_services_master_id_fkey", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name="master_services_service_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("master_id", "service_id", name="master_services_pkey"),
    )
    op.create_index("master_services_service_id_idx", "master_services", ["service_id"])

    # ------------------------------------------------------------------ #
    # appointments — центральная таблица
    # ------------------------------------------------------------------ #
    op.create_table(
        "appointments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.BigInteger(), nullable=False),
        sa.Column("master_id", sa.BigInteger(), nullable=False),
        sa.Column("service_id", sa.BigInteger(), nullable=False),
        sa.Column("period", postgresql.TSTZRANGE(), nullable=False),
        sa.Column("price_at_booking", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("status", appointment_status, server_default="booked", nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "lower(period) IS NOT NULL AND upper(period) IS NOT NULL AND NOT isempty(period)",
            name="period_bounded",
        ),
        sa.CheckConstraint("price_at_booking >= 0", name="price_non_negative"),
        sa.CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)",
            name="cancelled_at_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"], ["users.id"], name="appointments_client_id_fkey", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["master_id"], ["masters.id"], name="appointments_master_id_fkey", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], name="appointments_service_id_fkey", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="appointments_pkey"),
    )

    # ================================================================== #
    #  ЯДРО ПРОЕКТА: невозможность двойной записи
    #
    #  master_id WITH =  — тот же мастер
    #  period WITH &&    — пересекающиеся интервалы времени
    #  WHERE status = 'booked' — частичное ограничение: отменённая запись
    #                            слот не держит, на него можно записаться.
    #
    #  Проверка идёт внутри GiST-индекса под блокировкой, поэтому две
    #  одновременные транзакции не могут вставить пересекающиеся строки:
    #  одна коммитится, вторая получает SQLSTATE 23P01. Приложение ловит
    #  его и отдаёт 409 "Это время уже занято" (app/core/errors.py).
    # ================================================================== #
    op.execute(
        """
        ALTER TABLE appointments
            ADD CONSTRAINT appointments_no_overlap
            EXCLUDE USING gist (master_id WITH =, period WITH &&)
            WHERE (status = 'booked')
        """
    )

    op.create_index("appointments_client_id_idx", "appointments", ["client_id"])
    op.create_index("appointments_master_id_idx", "appointments", ["master_id"])
    op.create_index("appointments_service_id_idx", "appointments", ["service_id"])
    op.create_index("appointments_status_idx", "appointments", ["status"])
    # Диапазонный поиск «записи мастера за день» и сортировка по началу визита.
    op.execute(
        "CREATE INDEX appointments_master_start_idx ON appointments (master_id, lower(period))"
    )
    op.execute("CREATE INDEX appointments_period_gist_idx ON appointments USING gist (period)")


def downgrade() -> None:
    op.drop_table("appointments")
    op.drop_table("master_services")
    op.drop_table("services")
    op.drop_table("service_categories")
    op.drop_table("time_off")
    op.drop_table("working_hours")
    op.drop_table("masters")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS timerange")
    op.execute("DROP TYPE IF EXISTS appointment_status")
    op.execute("DROP TYPE IF EXISTS user_role")
    # Расширения не трогаем: их может использовать что-то ещё в БД.
