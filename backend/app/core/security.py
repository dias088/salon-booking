"""Хэширование паролей.

Выдача и проверка JWT добавляются на этапе авторизации; здесь пока только
то, что нужно и сиду, и регистрации.
"""

from __future__ import annotations

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return bool(pwd_context.verify(password, password_hash))
