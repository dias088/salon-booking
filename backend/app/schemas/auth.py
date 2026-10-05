"""Схемы регистрации, входа и профиля."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.db.models.enums import UserRole

#: Телефон в свободной форме, но с проверкой: плюс не обязателен,
#: 10-15 цифр, разделители любые.
_PHONE_DIGITS = re.compile(r"\d")

Password = Annotated[str, Field(min_length=8, max_length=128)]
FullName = Annotated[str, Field(min_length=2, max_length=120)]
Phone = Annotated[str, Field(min_length=10, max_length=32)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Password
    full_name: FullName
    phone: Phone

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        digits = _PHONE_DIGITS.findall(value)
        if not 10 <= len(digits) <= 15:
            raise ValueError("Телефон должен содержать от 10 до 15 цифр")
        return value.strip()

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return " ".join(value.split())


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    """Профиль текущего пользователя. password_hash сюда не попадает никогда."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    phone: str
    role: UserRole
    created_at: datetime


class TokenResponse(BaseModel):
    """Refresh-токена здесь нет намеренно: он уходит только в httpOnly cookie,
    чтобы его нельзя было прочитать из JavaScript."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Срок жизни access-токена в секундах")
    user: UserPublic
