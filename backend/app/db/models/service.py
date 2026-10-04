"""Каталог услуг.

Из курсовой SERVICE вынесена категория: там она была SERVICE.Category
VARCHAR(30) и дублировалась в каждой строке ('Hair', 'Nails', 'Skin'),
что позволяло опечатки и мешало построить каталог. Теперь это справочник
service_categories, а SERVICE.Category стала FK.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.appointment import Appointment
    from app.db.models.master import Master


class ServiceCategory(Base):
    __tablename__ = "service_categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    #: Порядок вывода в каталоге; при равных значениях сортируем по имени.
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    services: Mapped[list[Service]] = relationship(
        back_populates="category", order_by="Service.name"
    )

    def __repr__(self) -> str:
        return f"<ServiceCategory id={self.id} name={self.name!r}>"


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        # Оба CHECK перенесены из курсовой схемы без изменений.
        # Имена короткие: соглашение из base.py само добавит префикс таблицы.
        CheckConstraint("duration_min > 0", name="duration_positive"),
        CheckConstraint("price >= 0", name="price_non_negative"),
        # Длительность кратна пяти минутам — иначе границы визитов разъезжаются
        # с сеткой слотов и расписание становится нечитаемым.
        # mod(), а не оператор %: знак процента пришлось бы экранировать
        # в DDL под paramstyle-ом некоторых драйверов.
        CheckConstraint("mod(duration_min, 5) = 0", name="duration_step"),
        Index("services_category_id_idx", "category_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("service_categories.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    category: Mapped[ServiceCategory] = relationship(back_populates="services")
    masters: Mapped[list[MasterService]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )
    appointments: Mapped[list[Appointment]] = relationship(back_populates="service")

    def __repr__(self) -> str:
        return f"<Service id={self.id} name={self.name!r} {self.duration_min}min>"


class MasterService(Base):
    """Какие услуги оказывает мастер (M:N) + необязательные свои цена и длительность.

    Составной первичный ключ (master_id, service_id) — ровно как в
    курсовой APPOINTMENT_SERVICE была UNIQUE(AppointmentID, ServiceID),
    только тут это и есть PK, без лишнего суррогатного id.

    NULL в *_override означает «брать из services». Эффективные значения
    считаются через COALESCE: в SQL — во представлении v_master_service_offer,
    в коде — свойствами effective_price / effective_duration_min ниже.
    """

    __tablename__ = "master_services"
    __table_args__ = (
        CheckConstraint(
            "price_override IS NULL OR price_override >= 0",
            name="price_non_negative",
        ),
        CheckConstraint(
            "duration_min_override IS NULL OR "
            "(duration_min_override > 0 AND mod(duration_min_override, 5) = 0)",
            name="duration_valid",
        ),
        Index("master_services_service_id_idx", "service_id"),
    )

    master_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("masters.id", ondelete="CASCADE"), primary_key=True
    )
    service_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("services.id", ondelete="CASCADE"), primary_key=True
    )
    price_override: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    duration_min_override: Mapped[int | None] = mapped_column(Integer)

    master: Mapped[Master] = relationship(back_populates="services")
    service: Mapped[Service] = relationship(back_populates="masters")

    @property
    def effective_price(self) -> Decimal:
        return self.price_override if self.price_override is not None else self.service.price

    @property
    def effective_duration_min(self) -> int:
        return (
            self.duration_min_override
            if self.duration_min_override is not None
            else self.service.duration_min
        )

    def __repr__(self) -> str:
        return f"<MasterService master_id={self.master_id} service_id={self.service_id}>"
