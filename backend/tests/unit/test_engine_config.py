"""Настройка движка под транзакционный пул (PgBouncer у Neon и Supabase)."""

from __future__ import annotations

import pytest

from app.db.session import engine_options, is_transaction_pooler

POOLED = (
    "postgresql+asyncpg://u:p@ep-fancy-recipe-b19nw4c7-pooler.c-5.eu-central-1.aws.neon.tech/db"
)
DIRECT = "postgresql+asyncpg://u:p@ep-fancy-recipe-b19nw4c7.c-5.eu-central-1.aws.neon.tech/db"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (POOLED, True),
        (DIRECT, False),
        ("postgresql+asyncpg://u:p@db.pgbouncer.internal/db", True),
        ("postgresql+asyncpg://salon:salon@localhost:5433/salon", False),
    ],
)
def test_pooler_detection(url: str, expected: bool) -> None:
    assert is_transaction_pooler(url) is expected


def test_pooled_engine_disables_prepared_statement_cache() -> None:
    """За пулером соединение между запросами не закреплено.

    asyncpg по умолчанию кэширует подготовленные выражения, и следующий
    запрос может уйти в бэкенд, где их нет, — отсюда плавающие ошибки
    `prepared statement "__asyncpg_stmt_x__" does not exist`.
    """
    url, kwargs = engine_options(POOLED)

    assert url.endswith("?prepared_statement_cache_size=0")
    assert kwargs["connect_args"]["statement_cache_size"] == 0
    # Имена выражений должны быть уникальными, иначе столкнутся между соединениями.
    name_func = kwargs["connect_args"]["prepared_statement_name_func"]
    assert name_func() != name_func()


def test_direct_engine_keeps_defaults() -> None:
    """Прямое подключение ничего отключать не должно — кэш там выигрышен."""
    url, kwargs = engine_options(DIRECT)

    assert url == DIRECT
    assert "connect_args" not in kwargs


def test_existing_query_params_are_preserved() -> None:
    """Если в URL уже есть параметры, добавляем свой через &, а не через ?."""
    url, _ = engine_options(f"{POOLED}?application_name=salon")

    assert url == f"{POOLED}?application_name=salon&prepared_statement_cache_size=0"
