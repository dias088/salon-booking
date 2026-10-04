# Онлайн-запись в салон красоты

Fullstack-приложение для записи клиентов к мастерам салона.

Главное в проекте — **схема PostgreSQL и защита от двойной записи на уровне
базы данных**: два клиента физически не могут занять одно время у одного
мастера, даже если их запросы пришли в одну миллисекунду. Это обеспечивает
не код приложения, а ограничение `EXCLUDE USING gist` в самой БД.

> Проект в работе. Этап 1 из 8 — схема, миграции, демо-данные.
> Полный README (скриншоты, ER-диаграмма, описание API, деплой) — на этапе 8.

## Стек

| Слой | Технологии |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async) + asyncpg, Alembic, Pydantic v2, passlib[bcrypt], python-jose |
| Frontend | React 18 + TypeScript, Vite, React Router, TanStack Query, Tailwind CSS, react-hook-form + zod, date-fns, Recharts |
| БД | PostgreSQL 16 (`btree_gist`, `citext`, `tstzrange`) |
| Тесты | pytest + pytest-asyncio + httpx (отдельная тестовая БД), Vitest |
| Линтинг | ruff + mypy (strict), ESLint + Prettier |

## Запуск за 5 команд

```bash
cp .env.example .env     # 1. окружение (значения по умолчанию рабочие)
make up                  # 2. PostgreSQL 16 в Docker
make install             # 3. venv + зависимости backend
make migrate && make seed  # 4. схема и демо-данные
make dev                 # 5. API на http://localhost:8000/docs
```

<details>
<summary>Windows без <code>make</code></summary>

```powershell
Copy-Item .env.example .env
docker compose up -d --wait db
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\pip install -e "backend[dev]"
cd backend
..\backend\.venv\Scripts\python -m alembic upgrade head
..\backend\.venv\Scripts\python -m app.seed
..\backend\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```
</details>

## Демо-аккаунты

| Роль | E-mail | Пароль |
|---|---|---|
| Админ | `admin@salon.dev` | `admin1234` |
| Клиент | `client@salon.dev` | `client1234` |
| Мастер | `aigerim@salon.dev` | `master1234` |

## Как устроена защита от двойной записи

Полный разбор — на этапе 8. Суть в одном ограничении:

```sql
ALTER TABLE appointments
    ADD CONSTRAINT appointments_no_overlap
    EXCLUDE USING gist (master_id WITH =, period WITH &&)
    WHERE (status = 'booked');
```

* `master_id WITH =` — речь об одном и том же мастере;
* `period WITH &&` — интервалы времени пересекаются;
* `WHERE (status = 'booked')` — ограничение частичное: отменённая запись
  слот не держит, на её время можно записаться снова.

Проверка выполняется внутри GiST-индекса под блокировкой, поэтому две
параллельные транзакции не могут вставить пересекающиеся строки: одна
коммитится, вторая получает `SQLSTATE 23P01`. Приложение перехватывает его
и отвечает `409 { "error": { "code": "slot_taken", ... } }`.

## Структура

```
db/course/        исходные SQL из курса СУБД + разбор изменений
db/sql/           аналитические запросы (оконные функции) для статистики
backend/          FastAPI, модели, миграции, тесты
frontend/         React + TypeScript (этапы 6-7)
```

## Схема БД

Разбор «что изменено относительно курсовой схемы и зачем» —
в [`db/course/README.md`](db/course/README.md).
ER-диаграмма и описание представлений будут здесь на этапе 8.
