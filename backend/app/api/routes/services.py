"""Публичный каталог услуг."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.schemas.catalog import CategoryWithServices, ServiceOut
from app.schemas.common import ErrorResponse, Page
from app.services import catalog

router = APIRouter(prefix="/services", tags=["catalog"])


@router.get(
    "/categories",
    response_model=list[CategoryWithServices],
    summary="Каталог: категории вместе с услугами",
)
async def list_categories(session: SessionDep) -> list[CategoryWithServices]:
    return await catalog.list_catalog(session)


@router.get("", response_model=Page[ServiceOut], summary="Список услуг")
async def list_services(
    session: SessionDep,
    category_id: Annotated[int | None, Query(description="Фильтр по категории")] = None,
    q: Annotated[str | None, Query(description="Поиск по названию")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[ServiceOut]:
    query = catalog.services_query(category_id=category_id, search=q)
    items, total = await catalog.paginate_services(session, query, page=page, size=size)
    return Page(items=items, total=total, page=page, size=size)


@router.get(
    "/{service_id}",
    response_model=ServiceOut,
    responses={404: {"model": ErrorResponse}},
    summary="Одна услуга",
)
async def get_service(service_id: int, session: SessionDep) -> ServiceOut:
    return await catalog.get_service(session, service_id)
