# syntax=docker/dockerfile:1
#
# Контекст сборки — КОРЕНЬ репозитория, а не backend/:
#   docker build -f backend/Dockerfile -t salon-api .
# Так в образ попадает ещё и db/sql: статистика читает запросы оттуда
# во время работы, а не хранит их копию в питоне.

# ---------------------------------------------------------------------------
# Зависимости отдельным слоем: пока pyproject.toml не менялся, пересборка
# при каждой правке кода не переустанавливает пакеты.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./
# Заглушка пакета: setuptools требует, чтобы исходники существовали на
# момент установки, но копировать их сюда — значит терять кэш слоя.
RUN mkdir -p app && touch app/__init__.py \
    && python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install .

# ---------------------------------------------------------------------------
# Рантайм
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PATH="/opt/venv/bin:$PATH"

# Не от root: контейнеру незачем право записи в систему.
RUN useradd --create-home --uid 1000 app

COPY --from=builder /opt/venv /opt/venv

# Раскладка повторяет репозиторий, потому что app/core/config.py вычисляет
# корень проекта как три уровня вверх от себя и ищет там db/sql.
WORKDIR /srv/backend
COPY --chown=app:app backend/alembic.ini ./
COPY --chown=app:app backend/alembic ./alembic
COPY --chown=app:app backend/app ./app
COPY --chown=app:app db/sql /srv/db/sql

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# Миграции накатываются на старте: на Render это единственный момент,
# когда уже есть доступ к БД, но ещё не принят трафик.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
