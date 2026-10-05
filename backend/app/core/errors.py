"""Единый формат ошибок API.

Любой ответ со статусом >= 400 выглядит так::

    { "error": { "code": "slot_taken", "message": "Это время уже занято" } }

Поэтому фронтенду достаточно одного разбора: `code` — для логики,
`message` — для показа человеку.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

#: SQLSTATE нарушения ограничения EXCLUDE.
#: Именно его поднимает appointments_no_overlap при попытке
#: записаться на уже занятое время.
SQLSTATE_EXCLUSION_VIOLATION = "23P01"
SQLSTATE_UNIQUE_VIOLATION = "23505"
SQLSTATE_CHECK_VIOLATION = "23514"
SQLSTATE_NOT_NULL_VIOLATION = "23502"
SQLSTATE_FOREIGN_KEY_VIOLATION = "23503"

#: Starlette переименовала HTTP_422_UNPROCESSABLE_ENTITY в ..._CONTENT и
#: ругается депрекейшеном на старое имя. Числовой литерал не зависит от версии.
HTTP_422 = 422


class AppError(Exception):
    """База для всех ожидаемых ошибок приложения."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    message: str = "Некорректный запрос"

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        super().__init__(self.message)


class BadRequestError(AppError):
    pass


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    message = "Нужна авторизация"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "Недостаточно прав"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Не найдено"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "Конфликт состояния"


class SlotTakenError(ConflictError):
    """409 на занятый слот. Фронтенд по этому коду перезапрашивает слоты."""

    code = "slot_taken"
    message = "Это время уже занято. Пожалуйста, выберите другой слот"


class TimeOffOverlapError(ConflictError):
    code = "time_off_overlap"
    message = "У мастера уже есть период отсутствия, пересекающийся с этим"


class WorkingHoursOverlapError(ConflictError):
    code = "working_hours_overlap"
    message = "Рабочие интервалы в этот день недели пересекаются"


class EmailTakenError(ConflictError):
    code = "email_taken"
    message = "Пользователь с таким e-mail уже зарегистрирован"


class UnprocessableError(AppError):
    status_code = HTTP_422
    code = "validation_error"
    message = "Данные не прошли проверку"


def error_body(code: str, message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    payload.update(extra)
    return {"error": payload}


#: Имя ограничения из текста ошибки — фолбэк, если атрибут недоступен.
_CONSTRAINT_IN_MESSAGE = re.compile(r'constraint "([^"]+)"')

#: Глубина обхода цепочки причин. Реально нужно 3 звена, берём с запасом.
_MAX_CAUSE_DEPTH = 5


def _error_chain(exc: BaseException) -> Iterator[BaseException]:
    """Разворачивает sqlalchemy.exc.IntegrityError до настоящей ошибки asyncpg.

    Цепочка такая:
        sqlalchemy.exc.IntegrityError
          .orig     -> AsyncAdapt_asyncpg_dbapi.IntegrityError (обёртка DBAPI)
          .__cause__-> asyncpg.exceptions.ExclusionViolationError  <- вот тут
                       и лежат sqlstate с constraint_name
    Обёртка DBAPI их не проксирует, поэтому одного exc.orig недостаточно.
    """
    current: BaseException | None = exc
    for _ in range(_MAX_CAUSE_DEPTH):
        if current is None:
            return
        yield current
        following = getattr(current, "orig", None)
        if following is None or following is current:
            following = current.__cause__
        current = following


def sqlstate_of(exc: BaseException) -> str | None:
    for error in _error_chain(exc):
        code = getattr(error, "sqlstate", None) or getattr(error, "pgcode", None)
        if code:
            return str(code)
    return None


def constraint_name_of(exc: BaseException) -> str | None:
    for error in _error_chain(exc):
        name = getattr(error, "constraint_name", None)
        if name:
            return str(name)
    match = _CONSTRAINT_IN_MESSAGE.search(str(exc))
    return match.group(1) if match else None


#: Какое ограничение БД превращается в какую ошибку API.
_CONSTRAINT_ERRORS: dict[str, type[AppError]] = {
    "appointments_no_overlap": SlotTakenError,
    "time_off_no_overlap": TimeOffOverlapError,
    "working_hours_no_overlap": WorkingHoursOverlapError,
    "users_email_key": EmailTakenError,
}


def translate_integrity_error(exc: IntegrityError) -> AppError:
    """IntegrityError из БД -> осмысленная ошибка API.

    Главный случай: 23P01 от appointments_no_overlap означает, что пока
    клиент выбирал слот, его занял кто-то другой (или это вторая из двух
    одновременных попыток). Для пользователя это 409, а не 500.

    Внимание: IntegrityError прилетает не только от UNIQUE и EXCLUDE, но и от
    CHECK, NOT NULL и FOREIGN KEY. Это ошибки ввода, им место в 4xx, поэтому
    они разобраны здесь, а не падают в общий 409.
    """
    constraint = constraint_name_of(exc)
    if constraint and constraint in _CONSTRAINT_ERRORS:
        return _CONSTRAINT_ERRORS[constraint]()

    sqlstate = sqlstate_of(exc)
    if sqlstate == SQLSTATE_EXCLUSION_VIOLATION:
        # Имя ограничения не доехало, но пересечение периодов — всё равно 409.
        return SlotTakenError()
    if sqlstate == SQLSTATE_UNIQUE_VIOLATION:
        return ConflictError("Такая запись уже существует", code="already_exists")
    if sqlstate == SQLSTATE_CHECK_VIOLATION:
        return UnprocessableError(
            f"Данные нарушают ограничение базы: {constraint or 'check'}",
            code="constraint_violated",
        )
    if sqlstate == SQLSTATE_NOT_NULL_VIOLATION:
        return UnprocessableError("Обязательное поле не заполнено", code="field_required")
    if sqlstate == SQLSTATE_FOREIGN_KEY_VIOLATION:
        return UnprocessableError("Ссылка на несуществующую запись", code="related_object_missing")
    return ConflictError()


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message),
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        app_error = translate_integrity_error(exc)
        return JSONResponse(
            status_code=app_error.status_code,
            content=error_body(app_error.code, app_error.message),
        )

    # Отдельный обработчик DBAPIError не нужен: все нарушения ограничений
    # (UNIQUE, EXCLUDE, CHECK, NOT NULL, FK) SQLAlchemy заворачивает именно
    # в IntegrityError. Прочие ошибки драйвера — это настоящие 500,
    # и пусть они всплывают как есть.

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Приводим штатные 404/405 Starlette к общему формату.
        code = {
            status.HTTP_401_UNAUTHORIZED: "unauthorized",
            status.HTTP_403_FORBIDDEN: "forbidden",
            status.HTTP_404_NOT_FOUND: "not_found",
            status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
        }.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in err["loc"][1:]) or str(err["loc"][0]),
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=HTTP_422,
            content=error_body(
                "validation_error",
                "Данные не прошли проверку",
                details=details,
            ),
        )
