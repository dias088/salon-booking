"""Пароли и токены.

Схема аутентификации:
  * access  — JWT HS256 на 15 минут, уходит клиенту и живёт в памяти JS;
  * refresh — непрозрачная случайная строка в httpOnly cookie. В БД лежит
    только её SHA-256, поэтому утечка таблицы refresh_tokens не даёт сессий.

Refresh ротируется: каждый обмен отзывает старую строку и создаёт новую.
Повторное использование уже отозванного токена трактуется как кража сессии
(см. app/services/auth.py).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.errors import UnauthorizedError
from app.db.models.enums import UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TOKEN_TYPE_ACCESS = "access"


def hash_password(password: str) -> str:
    # passlib без аннотаций, поэтому .hash() для mypy возвращает Any.
    return str(pwd_context.hash(password))


def verify_password(password: str, password_hash: str) -> bool:
    return bool(pwd_context.verify(password, password_hash))


@dataclass(frozen=True)
class AccessTokenPayload:
    user_id: int
    role: UserRole
    expires_at: datetime


def create_access_token(user_id: int, role: UserRole) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_ttl_min)
    claims = {
        "sub": str(user_id),
        "role": role.value,
        "typ": TOKEN_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    # python-jose без аннотаций, поэтому для mypy encode возвращает Any.
    return str(jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm))


def decode_access_token(token: str) -> AccessTokenPayload:
    """Разбирает и проверяет access-токен. Любая проблема — это 401."""
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise UnauthorizedError("Токен недействителен или истёк") from exc

    if claims.get("typ") != TOKEN_TYPE_ACCESS:
        # Защита от подстановки refresh-токена вместо access.
        raise UnauthorizedError("Неверный тип токена")

    try:
        user_id = int(claims["sub"])
        role = UserRole(claims["role"])
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Токен повреждён") from exc

    return AccessTokenPayload(
        user_id=user_id,
        role=role,
        expires_at=datetime.fromtimestamp(claims["exp"], tz=UTC),
    )


def generate_refresh_token() -> str:
    """Непрозрачный токен. Не JWT: его всё равно проверять походом в БД."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """SHA-256, а не bcrypt: токен уже случайный на 384 бита, растягивать нечего,
    зато поиск по хэшу становится обычным индексным запросом."""
    return hashlib.sha256(token.encode()).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days)
