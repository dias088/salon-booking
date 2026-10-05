"""Бизнес-логика аутентификации: регистрация, вход, ротация refresh-токена."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import EmailTakenError, UnauthorizedError
from app.core.security import (
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.db.models import RefreshToken, User, UserRole
from app.schemas.auth import RegisterRequest


async def register_client(session: AsyncSession, data: RegisterRequest) -> User:
    """Самостоятельная регистрация — всегда роль client.

    Мастера и админы создаются только администратором: иначе роль была бы
    параметром запроса, то есть дырой на повышение привилегий.
    """
    existing = await session.scalar(select(User.id).where(User.email == data.email))
    if existing is not None:
        raise EmailTakenError()

    user = User(
        email=str(data.email),
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
        role=UserRole.client,
    )
    session.add(user)
    await session.flush()
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    # Проверяем пароль даже когда пользователя нет — иначе по времени ответа
    # можно было бы перебирать существующие e-mail.
    password_hash = user.password_hash if user else _DUMMY_HASH
    password_ok = verify_password(password, password_hash)
    if user is None or not password_ok:
        raise UnauthorizedError("Неверный e-mail или пароль", code="invalid_credentials")
    return user


async def issue_refresh_token(session: AsyncSession, user: User) -> str:
    """Создаёт новый refresh и возвращает его открытое значение.

    В БД уходит только хэш — открытое значение существует ровно один раз,
    по дороге в cookie.
    """
    token = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(token),
            expires_at=refresh_token_expiry(),
        )
    )
    await session.flush()
    return token


async def rotate_refresh_token(session: AsyncSession, token: str) -> tuple[User, str]:
    """Обменивает refresh на новую пару. Старый токен отзывается.

    Если пришёл уже отозванный токен — значит его кто-то использовал повторно.
    Либо это гонка, либо у токена два владельца; безопаснее считать вторым и
    отозвать вообще все сессии пользователя.
    """
    stored = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if stored is None:
        raise UnauthorizedError("Сессия не найдена, войдите заново", code="invalid_refresh")

    now = datetime.now(UTC)
    if stored.revoked_at is not None:
        await revoke_all_user_tokens(session, stored.user_id)
        # Коммит прямо здесь — единственное место в сервисах, где это делается.
        # Дальше бросается исключение, и зависимость get_session откатила бы
        # транзакцию: отзыв сессий не сохранился бы, то есть защита от кражи
        # токена не сработала бы вовсе.
        await session.commit()
        raise UnauthorizedError(
            "Токен уже использован, все сессии завершены", code="refresh_reused"
        )
    if stored.expires_at <= now:
        raise UnauthorizedError("Сессия истекла, войдите заново", code="refresh_expired")

    stored.revoked_at = now
    user = await session.get(User, stored.user_id)
    if user is None:
        raise UnauthorizedError("Пользователь удалён", code="invalid_refresh")

    new_token = await issue_refresh_token(session, user)
    return user, new_token


async def revoke_refresh_token(session: AsyncSession, token: str) -> None:
    """Выход. Несуществующий токен не ошибка: logout должен быть идемпотентным."""
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_refresh_token(token),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )


async def revoke_all_user_tokens(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


#: Валидный bcrypt-хэш от случайной строки. Нужен, чтобы ветка «пользователя
#: нет» занимала столько же времени, сколько ветка «неверный пароль».
_DUMMY_HASH = hash_password("dummy-password-for-constant-time-compare")
