"""Конфигурация приложения.

Всё читается из переменных окружения (или из .env в корне репозитория).
Единственная точка, где живут секреты и бизнес-константы, — здесь.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> <корень>
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # .env ищем и в корне репозитория, и в backend/ — удобно и локально, и в Docker
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Salon Booking API"
    environment: Literal["dev", "test", "prod"] = "dev"
    debug: bool = False

    # --- база ---
    database_url: str
    test_database_url: str | None = None

    # --- auth ---
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = Field(default=15, gt=0)
    refresh_token_ttl_days: int = Field(default=30, gt=0)

    # --- салон ---
    salon_tz: str = "Asia/Almaty"
    slot_step_min: int = Field(default=15, gt=0)
    min_lead_time_min: int = Field(default=60, ge=0)
    cancel_deadline_min: int = Field(default=120, ge=0)

    # --- web ---
    cors_origins: str = "http://localhost:5173"
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "none", "strict"] = "lax"
    cookie_domain: str | None = None
    refresh_cookie_name: str = "salon_refresh"

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _require_asyncpg_driver(cls, value: str | None) -> str | None:
        if value and not value.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "URL базы должен начинаться с postgresql+asyncpg:// "
                f"(получено: {value.split('://', 1)[0]}://...)"
            )
        return value

    @property
    def salon_timezone(self) -> ZoneInfo:
        return ZoneInfo(self.salon_tz)

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS_ORIGINS задаётся строкой через запятую — так удобнее в Render/Vercel."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Кэшируется, чтобы .env читался один раз за процесс.

    database_url и jwt_secret без значений по умолчанию — их обязательно
    задаёт окружение, иначе приложение честно падает на старте.
    """
    return Settings()


settings = get_settings()
