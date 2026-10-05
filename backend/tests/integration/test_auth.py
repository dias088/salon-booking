"""Регистрация, вход, ротация refresh-токена, выход."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import RefreshToken, User, UserRole
from tests.conftest import DEFAULT_PASSWORD, UserFactory, auth_header, login

pytestmark = pytest.mark.integration

REGISTRATION = {
    "email": "newbie@test.dev",
    "password": "secret12345",
    "full_name": "Новый  Клиент",
    "phone": "+7 707 111 22 33",
}


async def test_register_creates_client_and_sets_cookie(
    client: AsyncClient, session: AsyncSession
) -> None:
    response = await client.post("/api/auth/register", json=REGISTRATION)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["role"] == "client"
    # Лишние пробелы в имени схлопываются валидатором.
    assert body["user"]["full_name"] == "Новый Клиент"
    assert body["access_token"]
    assert body["expires_in"] == settings.access_token_ttl_min * 60
    # Refresh не должен попадать в тело ответа — только в cookie.
    assert "refresh" not in response.text.lower()

    cookie = response.cookies.get(settings.refresh_cookie_name)
    assert cookie, "refresh-токен не установлен в cookie"

    stored = await session.scalar(select(RefreshToken))
    assert stored is not None
    # В БД лежит хэш, а не сам токен.
    assert stored.token_hash != cookie
    assert len(stored.token_hash) == 64


async def test_register_rejects_duplicate_email_case_insensitively(
    client: AsyncClient, make_user: UserFactory
) -> None:
    await make_user(email="taken@test.dev")

    response = await client.post(
        "/api/auth/register", json={**REGISTRATION, "email": "TAKEN@test.dev"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("password", "short"),
        ("email", "not-an-email"),
        ("phone", "12345"),
        ("full_name", "х"),
    ],
)
async def test_register_validates_input(client: AsyncClient, field: str, value: str) -> None:
    response = await client.post("/api/auth/register", json={**REGISTRATION, field: value})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert any(detail["field"] == field for detail in error["details"])


async def test_register_cannot_choose_role(client: AsyncClient, session: AsyncSession) -> None:
    """Роль не берётся из запроса, иначе это дыра на повышение привилегий."""
    response = await client.post("/api/auth/register", json={**REGISTRATION, "role": "admin"})

    assert response.status_code == 201
    user = await session.scalar(select(User).where(User.email == REGISTRATION["email"]))
    assert user is not None
    assert user.role is UserRole.client


async def test_login_returns_token(client: AsyncClient, client_user: User) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": client_user.email, "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == client_user.email


@pytest.mark.parametrize(
    ("email", "password"),
    [("client@test.dev", "wrong-password"), ("ghost@test.dev", DEFAULT_PASSWORD)],
)
async def test_login_rejects_bad_credentials(
    client: AsyncClient, client_user: User, email: str, password: str
) -> None:
    """Несуществующий e-mail и неверный пароль дают одинаковый ответ."""
    response = await client.post("/api/auth/login", json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_me_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_me_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me", headers=auth_header("not.a.jwt"))

    assert response.status_code == 401


async def test_me_returns_profile_without_password_hash(
    client: AsyncClient, client_user: User
) -> None:
    token = await login(client, client_user.email)

    response = await client.get("/api/auth/me", headers=auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == client_user.email
    assert "password_hash" not in body


async def test_refresh_rotates_token(
    client: AsyncClient, client_user: User, session: AsyncSession
) -> None:
    await login(client, client_user.email)
    first_cookie = client.cookies[settings.refresh_cookie_name]

    response = await client.post("/api/auth/refresh")

    assert response.status_code == 200
    second_cookie = client.cookies[settings.refresh_cookie_name]
    assert second_cookie != first_cookie, "refresh-токен обязан меняться при каждом обмене"

    total = await session.scalar(select(func.count()).select_from(RefreshToken))
    revoked = await session.scalar(
        select(func.count()).select_from(RefreshToken).where(RefreshToken.revoked_at.is_not(None))
    )
    assert (total, revoked) == (2, 1)


async def test_refresh_without_cookie_is_401(client: AsyncClient) -> None:
    response = await client.post("/api/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "no_refresh_cookie"


async def test_reusing_old_refresh_token_kills_all_sessions(
    client: AsyncClient, client_user: User, session: AsyncSession
) -> None:
    """Повторное использование отозванного токена — признак кражи сессии."""
    await login(client, client_user.email)
    stolen = client.cookies[settings.refresh_cookie_name]

    await client.post("/api/auth/refresh")  # токен stolen отозван и заменён

    client.cookies.set(settings.refresh_cookie_name, stolen)
    replay = await client.post("/api/auth/refresh")

    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "refresh_reused"

    active = await session.scalar(
        select(func.count()).select_from(RefreshToken).where(RefreshToken.revoked_at.is_(None))
    )
    assert active == 0, "все сессии пользователя должны быть завершены"


async def test_logout_revokes_token(
    client: AsyncClient, client_user: User, session: AsyncSession
) -> None:
    await login(client, client_user.email)

    response = await client.post("/api/auth/logout")

    assert response.status_code == 200
    active = await session.scalar(
        select(func.count()).select_from(RefreshToken).where(RefreshToken.revoked_at.is_(None))
    )
    assert active == 0

    # После выхода обменять токен уже нельзя.
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_logout_without_cookie_is_ok(client: AsyncClient) -> None:
    """Выход идемпотентен: повторный logout не должен падать."""
    assert (await client.post("/api/auth/logout")).status_code == 200
