"""Регистрация, вход, ротация сессии, выход."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.errors import UnauthorizedError
from app.core.security import create_access_token
from app.db.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.schemas.common import ErrorResponse, Message
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

#: Cookie отдаётся только на /api/auth/* — на остальные запросы её слать незачем.
REFRESH_COOKIE_PATH = "/api/auth"

RefreshCookie = Annotated[str | None, Cookie(alias=settings.refresh_cookie_name)]


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
        # httponly закрывает токен от JavaScript, то есть от XSS;
        # samesite и secure — от CSRF и от перехвата по http.
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=REFRESH_COOKIE_PATH,
        domain=settings.cookie_domain,
    )


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        expires_in=settings.access_token_ttl_min * 60,
        user=UserPublic.model_validate(user),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse, "description": "E-mail уже занят"}},
    summary="Регистрация клиента",
)
async def register(data: RegisterRequest, response: Response, session: SessionDep) -> TokenResponse:
    user = await auth_service.register_client(session, data)
    refresh = await auth_service.issue_refresh_token(session, user)
    await session.commit()
    _set_refresh_cookie(response, refresh)
    return _token_response(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse, "description": "Неверные учётные данные"}},
    summary="Вход",
)
async def login(data: LoginRequest, response: Response, session: SessionDep) -> TokenResponse:
    user = await auth_service.authenticate(session, str(data.email), data.password)
    refresh = await auth_service.issue_refresh_token(session, user)
    await session.commit()
    _set_refresh_cookie(response, refresh)
    return _token_response(user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse, "description": "Сессия недействительна"}},
    summary="Обновить access-токен",
)
async def refresh_tokens(
    response: Response, session: SessionDep, refresh_token: RefreshCookie = None
) -> TokenResponse:
    if not refresh_token:
        raise UnauthorizedError("Нет refresh-токена", code="no_refresh_cookie")
    user, new_refresh = await auth_service.rotate_refresh_token(session, refresh_token)
    await session.commit()
    _set_refresh_cookie(response, new_refresh)
    return _token_response(user)


@router.post("/logout", response_model=Message, summary="Выход")
async def logout(
    response: Response, session: SessionDep, refresh_token: RefreshCookie = None
) -> Message:
    if refresh_token:
        await auth_service.revoke_refresh_token(session, refresh_token)
        await session.commit()
    _clear_refresh_cookie(response)
    return Message(detail="Сессия завершена")


@router.get("/me", response_model=UserPublic, summary="Текущий пользователь")
async def me(user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(user)
