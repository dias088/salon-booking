"""Зависимости FastAPI: текущий пользователь и проверка ролей."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.models import Master, User, UserRole
from app.db.session import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# auto_error=False, чтобы отсутствие заголовка тоже прошло через наш
# обработчик и вернулось в едином формате {error:{code,message}}.
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Access-токен из /api/auth/login. Refresh живёт в httpOnly cookie.",
)

BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


async def get_current_user(credentials: BearerDep, session: SessionDep) -> User:
    if credentials is None:
        raise UnauthorizedError("Нужен заголовок Authorization: Bearer <token>")
    payload = decode_access_token(credentials.credentials)
    user = await session.get(User, payload.user_id)
    if user is None:
        # Токен подписан нами, но пользователя уже нет.
        raise UnauthorizedError("Пользователь не найден")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    """Фабрика зависимостей «только для этих ролей»."""
    allowed = frozenset(roles)

    async def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise ForbiddenError(
                "Доступно только для ролей: " + ", ".join(sorted(r.value for r in allowed))
            )
        return user

    return dependency


AdminUser = Annotated[User, Depends(require_roles(UserRole.admin))]
MasterUser = Annotated[User, Depends(require_roles(UserRole.master))]
ClientUser = Annotated[User, Depends(require_roles(UserRole.client))]
StaffUser = Annotated[User, Depends(require_roles(UserRole.master, UserRole.admin))]


async def get_current_master(user: MasterUser, session: SessionDep) -> Master:
    """Профиль мастера для текущего пользователя с ролью master."""
    master = await session.scalar(
        select(Master).where(Master.user_id == user.id).options(selectinload(Master.user))
    )
    if master is None:
        raise NotFoundError("У пользователя нет профиля мастера")
    return master


CurrentMaster = Annotated[Master, Depends(get_current_master)]
