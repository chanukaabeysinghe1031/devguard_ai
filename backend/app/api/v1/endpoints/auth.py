"""Authentication API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session, get_settings_dep
from app.api.deps.auth import AuthenticatedUser, get_current_user
from app.application.services.auth_service import AuthService
from app.core.config import Settings
from app.core.security import validate_jwt_settings
from app.schemas.auth import (
    AccessTokenResponse,
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserPublicResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _auth_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> AuthService:
    validate_jwt_settings(settings)
    return AuthService(session=session, settings=settings)


@router.post(
    "/register",
    response_model=UserPublicResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    body: RegisterRequest,
    service: AuthService = Depends(_auth_service),
) -> UserPublicResponse:
    return await service.register(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
    )


@router.post("/login", response_model=TokenResponse, summary="Login")
async def login(
    body: LoginRequest,
    request: Request,
    service: AuthService = Depends(_auth_service),
) -> TokenResponse:
    user_agent = request.headers.get("user-agent")
    return await service.login(
        email=body.email,
        password=body.password,
        user_agent=user_agent,
    )


@router.post("/refresh", response_model=AccessTokenResponse, summary="Refresh access token")
async def refresh(
    body: RefreshRequest,
    service: AuthService = Depends(_auth_service),
) -> AccessTokenResponse:
    return await service.refresh(refresh_token=body.refresh_token)


@router.post("/logout", response_model=MessageResponse, summary="Logout / revoke refresh token")
async def logout(
    body: LogoutRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: AuthService = Depends(_auth_service),
) -> MessageResponse:
    return await service.logout(refresh_token=body.refresh_token, user_id=current_user.id)


@router.get("/me", response_model=UserPublicResponse, summary="Current authenticated user")
async def me(
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: AuthService = Depends(_auth_service),
) -> UserPublicResponse:
    return await service.me(user_id=current_user.id)


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password for the current user",
)
async def change_password(
    body: ChangePasswordRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: AuthService = Depends(_auth_service),
) -> MessageResponse:
    return await service.change_password(
        user_id=current_user.id,
        current_password=body.current_password,
        new_password=body.new_password,
    )
