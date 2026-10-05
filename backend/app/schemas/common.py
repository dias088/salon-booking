"""Схемы, общие для всего API."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

#: Параметры пагинации списков.
PageNumber = Annotated[int, Field(ge=1, description="Номер страницы, с единицы")]
PageSize = Annotated[int, Field(ge=1, le=100, description="Элементов на странице")]


class Page[T](BaseModel):
    """Единый конверт для всех списков."""

    items: list[T]
    total: int = Field(description="Всего элементов с учётом фильтров")
    page: int
    size: int

    @property
    def pages(self) -> int:
        return (self.total + self.size - 1) // self.size if self.size else 0


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    """Форма ответа при любом статусе >= 400.

    Объявлена явно, чтобы Swagger показывал реальную структуру ошибки,
    а не пустое тело.
    """

    error: ErrorDetail


class Message(BaseModel):
    detail: str
