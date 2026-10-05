"""Общие фикстуры.

Тесты идут на отдельной БД (TEST_DATABASE_URL), схема накатывается теми же
миграциями, что и в проде — иначе EXCLUDE-ограничений в тестовой базе просто
не было бы, а они здесь самое важное.

Между тестами таблицы очищаются TRUNCATE, а не откатом транзакции: тест на
параллельную запись должен открывать настоящие конкурирующие транзакции,
а в общей внешней транзакции это невозможно.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable, Coroutine
from datetime import time
from decimal import Decimal
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import PROJECT_ROOT, settings
from app.core.security import hash_password
from app.db.models import (
    Master,
    MasterService,
    Service,
    ServiceCategory,
    User,
    UserRole,
    WorkingHours,
)
from app.db.session import create_engine, get_session
from app.main import app

TABLES_TO_WIPE = (
    "appointments",
    "master_services",
    "working_hours",
    "time_off",
    "masters",
    "services",
    "service_categories",
    "refresh_tokens",
    "users",
)

DEFAULT_PASSWORD = "testpass123"


def _test_database_url() -> str:
    url = settings.test_database_url
    if not url:
        pytest.exit(
            "TEST_DATABASE_URL не задан. Скопируй .env.example в .env "
            "и подними базу: docker compose up -d --wait db",
            returncode=1,
        )
    if url == settings.database_url:
        pytest.exit("TEST_DATABASE_URL совпадает с DATABASE_URL — тесты затрут dev-данные", 1)
    return url


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return _test_database_url()


@pytest.fixture(scope="session", autouse=True)
def migrate_test_database(test_database_url: str) -> None:
    """Накатывает миграции на тестовую БД один раз за прогон."""
    config = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "alembic"))
    # env.py читает ALEMBIC_DATABASE_URL раньше, чем settings.database_url.
    os.environ["ALEMBIC_DATABASE_URL"] = test_database_url
    try:
        command.upgrade(config, "head")
    finally:
        os.environ.pop("ALEMBIC_DATABASE_URL", None)


@pytest.fixture
async def engine(test_database_url: str) -> AsyncIterator[AsyncEngine]:
    """Движок на каждый тест.

    Не session-scope: у каждого теста свой event loop, а соединения asyncpg
    привязаны к тому loop, в котором созданы. Общий движок падал бы с
    "attached to a different loop". Накладные расходы — одно соединение.
    """
    test_engine = create_engine(test_database_url)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@pytest.fixture(autouse=True)
async def clean_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.execute(
            text(f"TRUNCATE {', '.join(TABLES_TO_WIPE)} RESTART IDENTITY CASCADE")
        )
    yield


@pytest.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as db_session:
        yield db_session


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """HTTP-клиент поверх ASGI, с сессиями на тестовой БД."""

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as db_session:
            yield db_session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Фабрики данных
# ---------------------------------------------------------------------------

UserFactory = Callable[..., Coroutine[Any, Any, User]]


@pytest.fixture
def make_user(session: AsyncSession) -> UserFactory:
    async def factory(
        email: str = "user@test.dev",
        role: UserRole = UserRole.client,
        password: str = DEFAULT_PASSWORD,
        full_name: str = "Тестовый Пользователь",
        phone: str = "+7 700 000 00 00",
    ) -> User:
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            phone=phone,
            role=role,
        )
        session.add(user)
        await session.commit()
        return user

    return factory


@pytest.fixture
async def client_user(make_user: UserFactory) -> User:
    return await make_user(email="client@test.dev", role=UserRole.client)


@pytest.fixture
async def admin_user(make_user: UserFactory) -> User:
    return await make_user(email="admin@test.dev", role=UserRole.admin)


@pytest.fixture
async def master_user(make_user: UserFactory) -> User:
    return await make_user(email="master@test.dev", role=UserRole.master)


@pytest.fixture
async def master(session: AsyncSession, master_user: User) -> Master:
    """Мастер с одной услугой и графиком пн-пт 10:00-18:00."""
    category = ServiceCategory(name="Стрижки", sort_order=10)
    service = Service(
        category=category,
        name="Женская стрижка",
        duration_min=60,
        price=Decimal("9000.00"),
    )
    master_profile = Master(user_id=master_user.id, bio="Тестовый мастер", is_active=True)
    master_profile.services.append(MasterService(service=service))
    for weekday in range(5):
        master_profile.working_hours.append(
            WorkingHours(weekday=weekday, start_time=time(10, 0), end_time=time(18, 0))
        )
    session.add_all([category, service, master_profile])
    await session.commit()
    return master_profile


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
