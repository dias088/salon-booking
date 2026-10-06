"""Загрузка именованных запросов из .sql-файлов.

Аналитика написана обычным SQL и лежит в db/sql/reports.sql — её можно
открыть в psql, прогнать и посмотреть план. Чтобы тот же текст не
дублировался в питоне, файл разбирается по маркерам::

    -- name: monthly_revenue
    SELECT ...;

Файл читается один раз при импорте, дальше запросы берутся из кэша.
"""

from __future__ import annotations

import re
from functools import cache

from sqlalchemy import TextClause, text

from app.core.config import PROJECT_ROOT

SQL_DIR = PROJECT_ROOT / "db" / "sql"

#: Разделитель блоков. Имя — идентификатор в snake_case.
_NAME_MARKER = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.MULTILINE)


def parse_blocks(content: str) -> dict[str, str]:
    """Режет содержимое файла на именованные запросы."""
    markers = list(_NAME_MARKER.finditer(content))
    blocks: dict[str, str] = {}
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(content)
        # Точка с запятой нужна для psql, но мешает, когда запрос
        # оборачивают в подзапрос для подсчёта total.
        blocks[marker.group(1)] = content[marker.end() : end].strip().rstrip(";")
    return blocks


@cache
def load_file(filename: str) -> dict[str, str]:
    path = SQL_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Нет файла с запросами: {path}")
    return parse_blocks(path.read_text(encoding="utf-8"))


def query(filename: str, name: str) -> TextClause:
    blocks = load_file(filename)
    if name not in blocks:
        raise KeyError(f"В {filename} нет запроса '{name}'. Есть: {sorted(blocks)}")
    return text(blocks[name])
