"""Запросы каталога: категории, услуги, мастера."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError
from app.db.models import Master, Service, ServiceCategory, User
from app.db.views import master_service_offer
from app.schemas.catalog import (
    CategoryWithServices,
    MasterDetailOut,
    MasterOut,
    MasterServiceOut,
    ServiceOut,
    WorkingHoursOut,
)


def _service_out(service: Service) -> ServiceOut:
    return ServiceOut(
        id=service.id,
        name=service.name,
        description=service.description,
        duration_min=service.duration_min,
        price=service.price,
        is_active=service.is_active,
        category_id=service.category_id,
        category_name=service.category.name,
    )


async def list_catalog(
    session: AsyncSession, *, only_active: bool = True
) -> list[CategoryWithServices]:
    """Категории вместе с услугами — одним запросом под страницу каталога."""
    query = (
        select(ServiceCategory)
        .options(selectinload(ServiceCategory.services).selectinload(Service.category))
        .order_by(ServiceCategory.sort_order, ServiceCategory.name)
    )
    categories = (await session.scalars(query)).unique().all()

    result = []
    for category in categories:
        services = [s for s in category.services if s.is_active or not only_active]
        if not services and only_active:
            continue
        result.append(
            CategoryWithServices(
                id=category.id,
                name=category.name,
                sort_order=category.sort_order,
                services=[_service_out(s) for s in services],
            )
        )
    return result


def services_query(
    *, category_id: int | None = None, search: str | None = None, only_active: bool = True
) -> Select[tuple[Service]]:
    query = select(Service).join(Service.category)
    if only_active:
        query = query.where(Service.is_active.is_(True))
    if category_id is not None:
        query = query.where(Service.category_id == category_id)
    if search:
        query = query.where(Service.name.ilike(f"%{search}%"))
    return query


async def paginate_services(
    session: AsyncSession, query: Select[tuple[Service]], *, page: int, size: int
) -> tuple[list[ServiceOut], int]:
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        await session.scalars(
            query.options(selectinload(Service.category))
            .order_by(Service.name)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()
    return [_service_out(service) for service in rows], total


async def get_service(session: AsyncSession, service_id: int) -> ServiceOut:
    service = await session.scalar(
        select(Service).where(Service.id == service_id).options(selectinload(Service.category))
    )
    if service is None:
        raise NotFoundError("Услуга не найдена")
    return _service_out(service)


async def _offers_by_master(
    session: AsyncSession, master_ids: list[int]
) -> dict[int, list[MasterServiceOut]]:
    """Услуги мастеров берём из представления: там уже посчитаны COALESCE-цены."""
    if not master_ids:
        return {}

    rows = (
        await session.execute(
            select(master_service_offer)
            .where(
                master_service_offer.c.master_id.in_(master_ids),
                master_service_offer.c.service_is_active.is_(True),
            )
            .order_by(
                master_service_offer.c.category_sort_order,
                master_service_offer.c.service_name,
            )
        )
    ).mappings()

    grouped: dict[int, list[MasterServiceOut]] = {master_id: [] for master_id in master_ids}
    for row in rows:
        grouped[row["master_id"]].append(
            MasterServiceOut(
                service_id=row["service_id"],
                service_name=row["service_name"],
                category_id=row["category_id"],
                category_name=row["category_name"],
                price=row["price"],
                duration_min=row["duration_min"],
                has_custom_price=row["has_custom_price"],
                has_custom_duration=row["has_custom_duration"],
            )
        )
    return grouped


async def list_masters(
    session: AsyncSession,
    *,
    service_id: int | None = None,
    only_active: bool = True,
    page: int = 1,
    size: int = 20,
) -> tuple[list[MasterOut], int]:
    query = select(Master).join(Master.user)
    if only_active:
        query = query.where(Master.is_active.is_(True))
    if service_id is not None:
        query = query.where(
            Master.id.in_(
                select(master_service_offer.c.master_id).where(
                    master_service_offer.c.service_id == service_id,
                    master_service_offer.c.service_is_active.is_(True),
                )
            )
        )

    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    masters = (
        await session.scalars(
            query.options(selectinload(Master.user))
            .order_by(User.full_name)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()

    offers = await _offers_by_master(session, [master.id for master in masters])
    items = [
        MasterOut(
            id=master.id,
            full_name=master.user.full_name,
            bio=master.bio,
            photo_url=master.photo_url,
            is_active=master.is_active,
            services=offers.get(master.id, []),
        )
        for master in masters
    ]
    return items, total


async def get_master(session: AsyncSession, master_id: int) -> MasterDetailOut:
    master = await session.scalar(
        select(Master)
        .where(Master.id == master_id)
        .options(selectinload(Master.user), selectinload(Master.working_hours))
    )
    if master is None:
        raise NotFoundError("Мастер не найден")

    offers = await _offers_by_master(session, [master.id])
    return MasterDetailOut(
        id=master.id,
        full_name=master.user.full_name,
        bio=master.bio,
        photo_url=master.photo_url,
        is_active=master.is_active,
        services=offers.get(master.id, []),
        working_hours=[
            WorkingHoursOut.model_validate(hours)
            for hours in sorted(master.working_hours, key=lambda h: (h.weekday, h.start_time))
        ],
    )
