"""Публичный каталог: услуги, категории, мастера."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Master, MasterService, Service

pytestmark = pytest.mark.integration


async def test_catalog_is_public(client: AsyncClient, master: Master) -> None:
    """Каталог открыт без авторизации — это витрина салона."""
    response = await client.get("/api/services/categories")

    assert response.status_code == 200
    categories = response.json()
    assert [c["name"] for c in categories] == ["Стрижки"]
    assert categories[0]["services"][0]["name"] == "Женская стрижка"


async def test_inactive_service_is_hidden(
    client: AsyncClient, session: AsyncSession, master: Master
) -> None:
    service = await session.get(Service, 1)
    assert service is not None
    service.is_active = False
    await session.commit()

    catalog = (await client.get("/api/services/categories")).json()
    listing = (await client.get("/api/services")).json()

    assert catalog == [], "категория без активных услуг не показывается"
    assert listing["total"] == 0


async def test_services_pagination_and_search(
    client: AsyncClient, session: AsyncSession, master: Master
) -> None:
    category_id = (await client.get("/api/services")).json()["items"][0]["category_id"]
    session.add_all(
        [
            Service(
                category_id=category_id,
                name=f"Услуга {index}",
                duration_min=30,
                price=Decimal("1000.00"),
            )
            for index in range(5)
        ]
    )
    await session.commit()

    page = (await client.get("/api/services", params={"page": 1, "size": 2})).json()
    assert page["total"] == 6
    assert len(page["items"]) == 2

    found = (await client.get("/api/services", params={"q": "женск"})).json()
    assert [item["name"] for item in found["items"]] == ["Женская стрижка"]


async def test_master_list_shows_effective_price(
    client: AsyncClient, session: AsyncSession, master: Master
) -> None:
    """Своя цена мастера перебивает общую — COALESCE считает представление."""
    link = await session.get(MasterService, (master.id, 1))
    assert link is not None
    link.price_override = Decimal("12500.00")
    link.duration_min_override = 45
    await session.commit()

    body = (await client.get("/api/masters")).json()

    offer = body["items"][0]["services"][0]
    assert offer["price"] == "12500.00"
    assert offer["duration_min"] == 45
    assert offer["has_custom_price"] is True
    assert offer["has_custom_duration"] is True


async def test_masters_can_be_filtered_by_service(
    client: AsyncClient, session: AsyncSession, master: Master
) -> None:
    assert (await client.get("/api/masters", params={"service_id": 1})).json()["total"] == 1
    assert (await client.get("/api/masters", params={"service_id": 999})).json()["total"] == 0


async def test_master_detail_includes_working_hours(client: AsyncClient, master: Master) -> None:
    body = (await client.get(f"/api/masters/{master.id}")).json()

    assert body["full_name"] == "Тестовый Пользователь"
    assert body["bio"] == "Тестовый мастер"
    assert len(body["working_hours"]) == 5
    assert body["working_hours"][0]["weekday"] == 0
    assert body["working_hours"][0]["start_time"] == "10:00:00"


async def test_missing_master_returns_404_in_common_format(client: AsyncClient) -> None:
    response = await client.get("/api/masters/999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
