"""Мастера, их рабочие часы и периоды отсутствия.

`working_hours` и `time_off` в курсовой схеме отсутствовали вовсе — именно
поэтому поиск свободного времени там был невозможен. Это две половины ответа
на вопрос «когда мастер доступен»: регулярная сетка по дням недели и вычеты
из неё конкретными датами.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import TSTZRANGE, ExcludeConstraint, Range
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.appointment import Appointment
    from app.db.models.service import MasterService
    from app.db.models.user import User


class Master(Base):
    """Профиль мастера. Заменяет курсовую STYLIST.

    Поле Specialization VARCHAR(50) из курса выкинуто: это был текстовый
    пересказ того, какие услуги человек делает. Теперь связь настоящая —
    через master_services (см. service.py).
    """

    __tablename__ = "masters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    bio: Mapped[str | None] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(String(500))
    # Мастер не удаляется, а деактивируется: его прошлые записи должны
    # остаться в статистике (в курсе тут стоял ON DELETE RESTRICT — идея та же).
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    user: Mapped[User] = relationship(back_populates="master")
    services: Mapped[list[MasterService]] = relationship(
        back_populates="master", cascade="all, delete-orphan"
    )
    working_hours: Mapped[list[WorkingHours]] = relationship(
        back_populates="master", cascade="all, delete-orphan"
    )
    time_off: Mapped[list[TimeOff]] = relationship(
        back_populates="master", cascade="all, delete-orphan"
    )
    appointments: Mapped[list[Appointment]] = relationship(back_populates="master")

    def __repr__(self) -> str:
        return f"<Master id={self.id} user_id={self.user_id} active={self.is_active}>"


class WorkingHours(Base):
    """Регулярный рабочий интервал мастера в конкретный день недели.

    Строк на один день может быть несколько — так выражается обед:
    (пн, 10:00-14:00) и (пн, 15:00-19:00). Пересекаться они не должны,
    и это проверяет БД, а не код: см. working_hours_no_overlap.
    """

    __tablename__ = "working_hours"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint("end_time > start_time", name="time_order"),
        # В PostgreSQL нет встроенного range-типа для time, поэтому в миграции
        # создаётся свой: CREATE TYPE timerange AS RANGE (subtype = time).
        # Операторы = по master_id/weekday доступны благодаря btree_gist.
        ExcludeConstraint(
            ("master_id", "="),
            ("weekday", "="),
            (text("timerange(start_time, end_time)"), "&&"),
            name="working_hours_no_overlap",
            using="gist",
        ),
        Index("working_hours_master_id_idx", "master_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    master_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("masters.id", ondelete="CASCADE"), nullable=False
    )
    #: 0 = понедельник ... 6 = воскресенье (ISO, как в Python weekday()).
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    master: Mapped[Master] = relationship(back_populates="working_hours")

    def __repr__(self) -> str:
        return (
            f"<WorkingHours master_id={self.master_id} weekday={self.weekday} "
            f"{self.start_time}-{self.end_time}>"
        )


class TimeOff(Base):
    """Отпуск, больничный, разовый выходной — произвольный период отсутствия."""

    __tablename__ = "time_off"
    __table_args__ = (
        CheckConstraint(
            "lower(period) IS NOT NULL AND upper(period) IS NOT NULL AND NOT isempty(period)",
            name="period_bounded",
        ),
        # У одного мастера два отпуска не могут пересекаться.
        ExcludeConstraint(
            ("master_id", "="),
            ("period", "&&"),
            name="time_off_no_overlap",
            using="gist",
        ),
        Index("time_off_master_id_idx", "master_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    master_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("masters.id", ondelete="CASCADE"), nullable=False
    )
    period: Mapped[Range[datetime]] = mapped_column(TSTZRANGE, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200))

    master: Mapped[Master] = relationship(back_populates="time_off")

    def __repr__(self) -> str:
        return f"<TimeOff master_id={self.master_id} period={self.period}>"
