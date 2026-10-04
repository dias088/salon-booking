"""Пользователи и refresh-токены.

Курсовая схема держала клиентов (CLIENT) и стилистов (STYLIST) в двух
независимых таблицах без пароля — войти в систему было нельзя никому.
Здесь одна таблица личности `users` с ролью, а профиль мастера вынесен
в `masters` (см. master.py), потому что он есть только у части пользователей.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import UserRole

if TYPE_CHECKING:
    from app.db.models.appointment import Appointment
    from app.db.models.master import Master


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # CITEXT вместо VARCHAR: уникальность e-mail должна быть
    # регистронезависимой на уровне типа, а не надежды на код приложения.
    email: Mapped[str] = mapped_column(CITEXT(), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=UserRole.client,
        server_default=UserRole.client.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    master: Mapped[Master | None] = relationship(back_populates="user", uselist=False)
    appointments: Mapped[list[Appointment]] = relationship(
        back_populates="client", foreign_keys="Appointment.client_id"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"


class RefreshToken(Base):
    """Хранится только SHA-256 от токена: утечка таблицы не даёт сессий.

    Ротация: при каждом /auth/refresh старая строка помечается revoked_at,
    выдаётся новая. Повторное использование отозванного токена — 401.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("refresh_tokens_user_id_idx", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()
