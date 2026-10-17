from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request, status

from app.config import get_settings
from app.security.auth import (
    check_login_rate_limit,
    create_access_token,
    verify_login,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=500)


@router.get("/status")
async def auth_status() -> dict[str, object]:
    settings = get_settings()
    return {
        "enabled": settings.auth_enabled,
        "method": "bearer-jwt" if settings.auth_enabled else "disabled",
        "token_ttl_minutes": settings.auth_token_ttl_minutes,
    }


@router.post("/login")
async def login(payload: LoginRequest, request: Request) -> dict[str, object]:
    settings = get_settings()
    if not settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Authentication is disabled for this deployment.",
        )

    check_login_rate_limit(request, settings)
    if not verify_login(payload.username, payload.password, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    token, expires_in = create_access_token(payload.username, settings)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": {"username": payload.username, "role": "admin"},
    }
