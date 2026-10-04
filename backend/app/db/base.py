"""Декларативная база SQLAlchemy 2.0.

Единое соглашение об именах ограничений нужно, чтобы Alembic умел их
находить и переименовывать, а в логах PostgreSQL было понятно, что упало.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Приближено к тому, как PostgreSQL называет ограничения сам,
# поэтому схема читается одинаково и из кода, и из \d в psql.
NAMING_CONVENTION = {
    "ix": "%(table_name)s_%(column_0_N_name)s_idx",
    "uq": "%(table_name)s_%(column_0_N_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
