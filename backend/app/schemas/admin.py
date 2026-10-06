"""Схемы административной части."""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.db.models.enums import AppointmentStatus
from app.schemas.auth import FullName, Phone

ORM = ConfigDict(from_attributes=True)

Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
DurationMin = Annotated[int, Field(gt=0, le=600, multiple_of=5)]


# --- категории -------------------------------------------------------------


class CategoryCreate(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=80)]
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: Annotated[str | None, Field(min_length=2, max_length=80)] = None
    sort_order: int | None = None


# --- услуги ----------------------------------------------------------------


class ServiceCreate(BaseModel):
    category_id: int
    name: Annotated[str, Field(min_length=2, max_length=120)]
    description: Annotated[str | None, Field(max_length=2000)] = None
    duration_min: DurationMin
    price: Money
    is_active: bool = True


class ServiceUpdate(BaseModel):
    category_id: int | None = None
    name: Annotated[str | None, Field(min_length=2, max_length=120)] = None
    description: Annotated[str | None, Field(max_length=2000)] = None
    duration_min: DurationMin | None = None
    price: Money | None = None
    is_active: bool | None = None


# --- мастера ---------------------------------------------------------------


class MasterCreate(BaseModel):
    """Создаёт сразу и пользователя с ролью master, и его профиль."""

    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=128)]
    full_name: FullName
    phone: Phone
    bio: Annotated[str | None, Field(max_length=2000)] = None
    photo_url: Annotated[str | None, Field(max_length=500)] = None


class MasterUpdate(BaseModel):
    full_name: FullName | None = None
    phone: Phone | None = None
    bio: Annotated[str | None, Field(max_length=2000)] = None
    photo_url: Annotated[str | None, Field(max_length=500)] = None
    is_active: bool | None = None


class MasterServiceLink(BaseModel):
    """Привязка услуги к мастеру. None в override означает «брать из услуги»."""

    service_id: int
    price_override: Money | None = None
    duration_min_override: DurationMin | None = None


# --- график и отпуска ------------------------------------------------------


class WorkingHoursCreate(BaseModel):
    weekday: Annotated[int, Field(ge=0, le=6, description="0 — понедельник")]
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("Конец интервала должен быть позже начала")
        return self


class TimeOffCreate(BaseModel):
    starts_at: datetime
    ends_at: datetime
    reason: Annotated[str | None, Field(max_length=200)] = None

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("Конец периода должен быть позже начала")
        return self


class TimeOffOut(BaseModel):
    id: int
    master_id: int
    starts_at: datetime
    ends_at: datetime
    reason: str | None


# --- записи ----------------------------------------------------------------


class NewClient(BaseModel):
    """Клиент, которого администратор заводит прямо при записи по телефону."""

    full_name: FullName
    phone: Phone
    email: EmailStr | None = Field(
        default=None,
        description="Если не указан, будет сгенерирован из телефона — "
        "клиент сможет завести пароль позже",
    )


class AdminAppointmentCreate(BaseModel):
    service_id: int
    master_id: int
    starts_at: datetime
    comment: Annotated[str | None, Field(max_length=500)] = None
    client_id: int | None = None
    client: NewClient | None = None

    @model_validator(mode="after")
    def _exactly_one_client(self) -> Self:
        if (self.client_id is None) == (self.client is None):
            raise ValueError("Укажите либо client_id существующего клиента, либо данные client")
        return self


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus


class UserOut(BaseModel):
    model_config = ORM

    id: int
    email: EmailStr
    full_name: str
    phone: str
    role: str
    created_at: datetime
