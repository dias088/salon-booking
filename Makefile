.DEFAULT_GOAL := help
SHELL := /bin/sh

PY  := backend/.venv/bin/python
PIP := backend/.venv/bin/pip
# На Windows venv складывает бинарники в Scripts/, а не bin/
ifeq ($(OS),Windows_NT)
	PY  := backend/.venv/Scripts/python.exe
	PIP := backend/.venv/Scripts/pip.exe
endif

.PHONY: help up down logs install migrate revision seed dev test lint fmt \
        web-install web-dev web-test web-lint reset

help: ## Показать список команд
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN{FS=":.*?## "};{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

# --- инфраструктура ---------------------------------------------------------

up: ## Поднять PostgreSQL 16 и дождаться готовности
	docker compose up -d --wait db

down: ## Остановить контейнеры (данные сохраняются)
	docker compose down

reset: ## Снести БД вместе с данными и поднять заново
	docker compose down -v
	docker compose up -d --wait db

logs: ## Логи БД
	docker compose logs -f db

# --- backend ----------------------------------------------------------------

install: ## Создать venv и установить backend-зависимости
	python -m venv backend/.venv
	$(PIP) install --upgrade pip
	$(PIP) install -e "backend[dev]"

migrate: ## Применить миграции к основной БД
	cd backend && ../$(PY) -m alembic upgrade head

revision: ## Новая миграция: make revision m="описание"
	cd backend && ../$(PY) -m alembic revision --autogenerate -m "$(m)"

seed: ## Залить демо-данные (пересоздаёт их заново)
	cd backend && ../$(PY) -m app.seed

dev: ## Запустить API на http://localhost:8000 (/docs — Swagger)
	cd backend && ../$(PY) -m uvicorn app.main:app --reload --port 8000

test: ## pytest на отдельной тестовой БД
	cd backend && ../$(PY) -m pytest

lint: ## ruff + mypy
	cd backend && ../$(PY) -m ruff check . && ../$(PY) -m ruff format --check . && ../$(PY) -m mypy .

fmt: ## Автоформат и автофиксы backend
	cd backend && ../$(PY) -m ruff check --fix . && ../$(PY) -m ruff format .

# --- frontend ---------------------------------------------------------------

web-install: ## npm install
	cd frontend && npm install

web-dev: ## Vite dev-сервер на http://localhost:5173
	cd frontend && npm run dev

web-test: ## Vitest
	cd frontend && npm run test

web-lint: ## ESLint + Prettier + tsc
	cd frontend && npm run lint && npm run typecheck
