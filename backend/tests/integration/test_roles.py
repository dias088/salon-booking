"""Разграничение доступа по ролям.

Защищённых ручек на этом этапе ещё нет, поэтому роли проверяются на
временных эндпоинтах, собранных из тех же зависимостей, что пойдут в
боевые роутеры. Так проверяется именно механизм, а не конкретный маршрут.
"""

from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import AdminUser, CurrentUser, MasterUser, StaffUser
from app.core.errors import register_exception_handlers
from app.db.models import User
from app.db.session import get_session
from tests.conftest import auth_header, login

pytestmark = pytest.mark.integration

probe_router = APIRouter(prefix="/probe")


@probe_router.get("/any")
async def any_user(user: CurrentUser) -> dict[str, str]:
    return {"role": user.role.value}


@probe_router.get("/admin")
async def admin_only(user: AdminUser) -> dict[str, str]:
    return {"role": user.role.value}


@probe_router.get("/master")
async def master_only(user: MasterUser) -> dict[str, str]:
    return {"role": user.role.value}


@probe_router.get("/staff")
async def staff_only(user: StaffUser) -> dict[str, str]:
    return {"role": user.role.value}


@pytest.fixture
async def probe_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncClient:
    probe_app = FastAPI()
    register_exception_handlers(probe_app)
    probe_app.include_router(probe_router)
    # Логин нужен настоящий, поэтому подключаем и боевой роутер авторизации.
    from app.api.routes import auth as auth_routes

    probe_app.include_router(auth_routes.router, prefix="/api")

    async def override_get_session():  # type: ignore[no-untyped-def]
        async with session_factory() as db_session:
            yield db_session

    probe_app.dependency_overrides[get_session] = override_get_session
    return AsyncClient(transport=ASGITransport(app=probe_app), base_url="http://test")


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("/probe/any", {"client", "master", "admin"}),
        ("/probe/admin", {"admin"}),
        ("/probe/master", {"master"}),
        ("/probe/staff", {"master", "admin"}),
    ],
)
async def test_role_matrix(
    probe_client: AsyncClient,
    client_user: User,
    master_user: User,
    admin_user: User,
    path: str,
    allowed: set[str],
) -> None:
    for user in (client_user, master_user, admin_user):
        token = await login(probe_client, user.email)

        response = await probe_client.get(path, headers=auth_header(token))

        expected = 200 if user.role.value in allowed else 403
        assert response.status_code == expected, (
            f"{user.role.value} -> {path}: ждали {expected}, получили {response.status_code}"
        )
        if expected == 403:
            assert response.json()["error"]["code"] == "forbidden"


async def test_protected_route_without_token_is_401(probe_client: AsyncClient) -> None:
    response = await probe_client.get("/probe/admin")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
