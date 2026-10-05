"""Публичный список мастеров."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.schemas.catalog import MasterDetailOut, MasterOut
from app.schemas.common import ErrorResponse, Page
from app.services import catalog

router = APIRouter(prefix="/masters", tags=["catalog"])


@router.get("", response_model=Page[MasterOut], summary="Список мастеров")
async def list_masters(
    session: SessionDep,
    service_id: Annotated[int | None, Query(description="Только те, кто делает эту услугу")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[MasterOut]:
    items, total = await catalog.list_masters(session, service_id=service_id, page=page, size=size)
    return Page(items=items, total=total, page=page, size=size)


@router.get(
    "/{master_id}",
    response_model=MasterDetailOut,
    responses={404: {"model": ErrorResponse}},
    summary="Мастер: услуги и график",
)
async def get_master(master_id: int, session: SessionDep) -> MasterDetailOut:
    return await catalog.get_master(session, master_id)
