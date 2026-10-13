"""Проверки конфигурации, которые должны срабатывать на старте приложения."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings

DB_URL = "postgresql+asyncpg://u:p@localhost/db"
SECRET = "x" * 32


def test_unknown_timezone_is_rejected() -> None:
    """Asia/Astana — популярная опечатка: такой зоны в tzdata нет.

    Раньше она проходила молча: приложение поднималось, health отвечал
    «ok», а 500 прилетал на первом же запросе слотов — уже на проде.
    """
    with pytest.raises(ValidationError) as caught:
        Settings(database_url=DB_URL, jwt_secret=SECRET, salon_tz="Asia/Astana")

    message = str(caught.value)
    assert "Asia/Astana" in message
    assert "Asia/Almaty" in message, "ошибка должна подсказывать правильную зону"


def test_known_timezone_passes() -> None:
    settings = Settings(database_url=DB_URL, jwt_secret=SECRET, salon_tz="Asia/Almaty")

    assert settings.salon_timezone.key == "Asia/Almaty"


@pytest.mark.parametrize("url", ["postgresql://u:p@h/db", "postgres://u:p@h/db"])
def test_non_asyncpg_url_is_rejected(url: str) -> None:
    """Neon отдаёт строку с postgresql:// — её надо заметить сразу."""
    with pytest.raises(ValidationError, match="asyncpg"):
        Settings(database_url=url, jwt_secret=SECRET)


def test_cors_origins_split_by_comma() -> None:
    settings = Settings(
        database_url=DB_URL,
        jwt_secret=SECRET,
        cors_origins="https://a.vercel.app, https://b.vercel.app ,",
    )

    assert settings.cors_origin_list == ["https://a.vercel.app", "https://b.vercel.app"]
