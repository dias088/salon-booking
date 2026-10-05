"""Прямая проверка ограничения appointments_no_overlap.

Тесты в test_booking.py проверяют поведение, видимое пользователю: при гонке
ровно один получает 201. Но 409 там мог бы прийти и от предварительной
проверки в коде — коды ответа одинаковые намеренно.

Здесь API не участвует: две сессии пишут в БД напрямую, минуя всю логику
приложения. Если ограничения не будет, эти тесты упадут — а значит они и
есть доказательство, что инвариант держит именно PostgreSQL.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.errors import (
    SQLSTATE_EXCLUSION_VIOLATION,
    constraint_name_of,
    sqlstate_of,
    translate_integrity_error,
)
from app.db.models import Appointment, AppointmentStatus, Master, User

pytestmark = pytest.mark.integration

TZ = settings.salon_timezone


def row(
    *,
    client_id: int,
    master_id: int,
    starts_at: datetime,
    minutes: int = 60,
    status: AppointmentStatus = AppointmentStatus.booked,
) -> Appointment:
    return Appointment(
        client_id=client_id,
        master_id=master_id,
        service_id=1,
        period=Range(starts_at, starts_at + timedelta(minutes=minutes), bounds="[)"),
        price_at_booking=Decimal("9000.00"),
        status=status,
        cancelled_at=datetime.now(TZ) if status is AppointmentStatus.cancelled else None,
    )


async def test_constraint_exists_in_the_test_database(session: AsyncSession) -> None:
    """Защита от «тесты зелёные, потому что ограничения просто нет»."""
    definition = await session.scalar(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'appointments_no_overlap'"
        )
    )

    assert definition is not None, "ограничение не создано — миграции накатились не полностью"
    assert "EXCLUDE USING gist" in definition
    assert "master_id WITH =" in definition
    assert "period WITH &&" in definition
    assert "status = 'booked'" in definition, "ограничение должно быть частичным"


async def test_overlapping_insert_raises_23p01(
    session: AsyncSession, master: Master, client_user: User
) -> None:
    start = datetime.now(TZ) + timedelta(days=3)
    session.add(row(client_id=client_user.id, master_id=master.id, starts_at=start))
    await session.commit()

    session.add(
        row(client_id=client_user.id, master_id=master.id, starts_at=start + timedelta(minutes=30))
    )
    with pytest.raises(IntegrityError) as caught:
        await session.commit()

    assert sqlstate_of(caught.value) == SQLSTATE_EXCLUSION_VIOLATION
    assert constraint_name_of(caught.value) == "appointments_no_overlap"
    error = translate_integrity_error(caught.value)
    assert (error.status_code, error.code) == (409, "slot_taken")


async def test_adjacent_rows_are_allowed(
    session: AsyncSession, master: Master, client_user: User
) -> None:
    """[10:00,11:00) и [11:00,12:00) не пересекаются — визиты впритык законны."""
    start = datetime.now(TZ) + timedelta(days=3)
    session.add(row(client_id=client_user.id, master_id=master.id, starts_at=start))
    session.add(
        row(client_id=client_user.id, master_id=master.id, starts_at=start + timedelta(hours=1))
    )

    await session.commit()

    assert await session.scalar(select(func.count()).select_from(Appointment)) == 2


async def test_cancelled_row_does_not_hold_the_slot(
    session: AsyncSession, master: Master, client_user: User
) -> None:
    """Частичность ограничения: WHERE status = 'booked'."""
    start = datetime.now(TZ) + timedelta(days=3)
    session.add(
        row(
            client_id=client_user.id,
            master_id=master.id,
            starts_at=start,
            status=AppointmentStatus.cancelled,
        )
    )
    await session.commit()

    session.add(row(client_id=client_user.id, master_id=master.id, starts_at=start))
    await session.commit()

    booked = await session.scalar(
        select(func.count())
        .select_from(Appointment)
        .where(Appointment.status == AppointmentStatus.booked)
    )
    assert booked == 1


async def test_different_masters_may_work_at_the_same_time(
    session: AsyncSession, master: Master, client_user: User
) -> None:
    """Ограничение про пересечение у ОДНОГО мастера, а не про время вообще."""
    start = datetime.now(TZ) + timedelta(days=3)
    session.add(row(client_id=client_user.id, master_id=master.id, starts_at=start))
    await session.commit()

    second_master_id = master.id + 1000
    session.add(row(client_id=client_user.id, master_id=second_master_id, starts_at=start))
    with pytest.raises(IntegrityError) as caught:
        await session.commit()

    # Падает по внешнему ключу (мастера с таким id нет), а не по пересечению —
    # то есть само время конфликтом не считается.
    assert sqlstate_of(caught.value) != SQLSTATE_EXCLUSION_VIOLATION


async def test_two_concurrent_transactions_only_one_commits(
    session_factory: async_sessionmaker[AsyncSession], master: Master, client_user: User
) -> None:
    """Две настоящие параллельные транзакции на один слот.

    Вот ради чего всё затевалось. Проверка «свободно ли» в коде тут не
    поможет: обе транзакции видят пустую таблицу. Конфликт обнаруживается
    при вставке в GiST-индекс, под блокировкой, — вторая ждёт первую и
    получает 23P01 ровно в тот момент, когда первая коммитится.
    """
    start = datetime.now(TZ) + timedelta(days=3)

    async def insert() -> str:
        async with session_factory() as db_session:
            db_session.add(row(client_id=client_user.id, master_id=master.id, starts_at=start))
            try:
                await db_session.commit()
            except IntegrityError as exc:
                return f"{sqlstate_of(exc)}:{constraint_name_of(exc)}"
            return "ok"

    results = await asyncio.gather(insert(), insert())

    assert sorted(results) == [
        "23P01:appointments_no_overlap",
        "ok",
    ], f"ожидали одного победителя и один конфликт, получили {results}"

    async with session_factory() as check:
        total = await check.scalar(select(func.count()).select_from(Appointment))
    assert total == 1
