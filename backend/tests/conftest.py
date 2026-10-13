"""Общие помощники для всех тестов.

Здесь намеренно нет ничего, что ходит в базу. Фикстуры с PostgreSQL
лежат в tests/integration/conftest.py, поэтому `pytest tests/unit`
проходит на машине без поднятого Docker — а значит юнит-тесты
алгоритма слотов и конфигурации можно гонять где угодно.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from httpx import AsyncClient

from app.db.models import User

#: Пароль всех пользователей, создаваемых фабрикой make_user.
DEFAULT_PASSWORD = "testpass123"

#: Фабрика пользователей из tests/integration/conftest.py.
UserFactory = Callable[..., Coroutine[Any, Any, User]]


async def login(http_client: AsyncClient, email: str, password: str = DEFAULT_PASSWORD) -> str:
    """Логинится и возвращает access-токен. Cookie остаётся в клиенте."""
    response = await http_client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return token


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
