"""Записи на приём — центральная таблица проекта.

Отличия от курсовой APPOINTMENT:

1. ``AppointmentDate DATE`` + ``AppointmentTime TIME`` заменены на одно поле
   ``period tstzrange``. Причина принципиальная: из даты и времени начала
   нельзя вывести конец визита, а значит нельзя и спросить у БД «пересекаются
   ли две записи». С диапазоном это один оператор ``&&``.
2. ``Status VARCHAR(20) CHECK (...)`` -> ENUM ``appointment_status``.
3. ``StationID`` убран (кабинеты вне ТЗ), а ``PriceAtBooking`` из
   APPOINTMENT_SERVICE переехал сюда: одна запись = одна услуга.
4. Добавлено ``cancelled_at`` — чтобы отличать «отменили» от «никогда не было».
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TSTZRANGE, ExcludeConstraint, Range
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import AppointmentStatus

if TYPE_CHECKING:
    from app.db.models.master import Master
    from app.db.models.service import Service
    from app.db.models.user import User


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        # Диапазон обязан быть замкнутым с двух сторон и непустым, иначе
        # «бесконечная» запись заблокировала бы мастеру всё расписание.
        CheckConstraint(
            "lower(period) IS NOT NULL AND upper(period) IS NOT NULL AND NOT isempty(period)",
            name="period_bounded",
        ),
        CheckConstraint("price_at_booking >= 0", name="price_non_negative"),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)",
            name="cancelled_at_consistent",
        ),
        # ──────────────────────────────────────────────────────────────────
        # ЯДРО ПРОЕКТА. Два активных визита одного мастера не могут
        # пересечься по времени — это гарантирует PostgreSQL, а не питон.
        # Проверка выполняется под блокировкой индекса GiST, поэтому
        # параллельные транзакции не могут «проскочить» обе: вторая получает
        # 23P01 exclusion_violation. Условие WHERE делает ограничение
        # частичным — отменённая запись слот не держит.
        # ──────────────────────────────────────────────────────────────────
        ExcludeConstraint(
            ("master_id", "="),
            ("period", "&&"),
            name="appointments_no_overlap",
            using="gist",
            where=text("status = 'booked'"),
        ),
        Index("appointments_client_id_idx", "client_id"),
        Index("appointments_master_id_idx", "master_id"),
        Index("appointments_service_id_idx", "service_id"),
        Index("appointments_status_idx", "status"),
        Index("appointments_period_gist_idx", "period", postgresql_using="gist"),
        # Главный рабочий индекс: «записи мастера за день» + сортировка
        # по началу визита. Выражение lower(period) делает индекс
        # функциональным, поэтому он объявлен через text().
        Index("appointments_master_start_idx", "master_id", text("lower(period)")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    client_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    master_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("masters.id", ondelete="RESTRICT"), nullable=False
    )
    service_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("services.id", ondelete="RESTRICT"), nullable=False
    )
    #: Полуинтервал [начало, конец): визит 10:00-11:00 и визит 11:00-12:00
    #: НЕ пересекаются, что и нужно для записей «впритык».
    period: Mapped[Range[datetime]] = mapped_column(TSTZRANGE, nullable=False)
    #: Цена фиксируется в момент брони (идея PriceAtBooking из курса):
    #: переоценка прайса не должна менять сумму уже сделанных записей.
    price_at_booking: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(
            AppointmentStatus,
            name="appointment_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=AppointmentStatus.booked,
        server_default=AppointmentStatus.booked.value,
    )
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    client: Mapped[User] = relationship(back_populates="appointments", foreign_keys=[client_id])
    master: Mapped[Master] = relationship(back_populates="appointments")
    service: Mapped[Service] = relationship(back_populates="appointments")

    @property
    def starts_at(self) -> datetime:
        assert self.period.lower is not None  # гарантировано CHECK в БД
        return self.period.lower

    @property
    def ends_at(self) -> datetime:
        assert self.period.upper is not None  # гарантировано CHECK в БД
        return self.period.upper

    def __repr__(self) -> str:
        return (
            f"<Appointment id={self.id} master_id={self.master_id} "
            f"{self.period} {self.status.value}>"
        )
