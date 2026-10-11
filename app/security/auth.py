from __future__ import annotations

import hmac
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pwdlib import PasswordHash
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Settings, get_settings

_PASSWORD_HASHER = PasswordHash.recommended()


class LoginRateLimiter:
    """Small in-process limiter for the MVP login endpoint.

    Production deployments should also rate-limit at the reverse proxy or platform
    edge. This limiter prevents trivial repeated login attempts inside one process.
    """

    def __init__(self, attempts: int, window_seconds: int) -> None:
        self.attempts = attempts
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= self.attempts:
                return False
            events.append(now)
            return True


_rate_limiter: LoginRateLimiter | None = None


def password_hash(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def validate_auth_configuration(settings: Settings) -> None:
    if not settings.auth_enabled:
        return
    missing = []
    if not settings.auth_username:
        missing.append("AUTH_USERNAME")
    if not settings.auth_password_hash:
        missing.append("AUTH_PASSWORD_HASH")
    if not settings.auth_jwt_secret or len(settings.auth_jwt_secret) < 32:
        missing.append("AUTH_JWT_SECRET (at least 32 characters)")
    if missing:
        raise RuntimeError(
            "Authentication is enabled but required settings are missing: "
            + ", ".join(missing)
        )


def verify_login(username: str, password: str, settings: Settings) -> bool:
    if not settings.auth_username or not settings.auth_password_hash:
        return False
    username_ok = hmac.compare_digest(username, settings.auth_username)
    try:
        password_ok = _PASSWORD_HASHER.verify(password, settings.auth_password_hash)
    except Exception:
        password_ok = False
    return username_ok and password_ok


def create_access_token(username: str, settings: Settings) -> tuple[str, int]:
    if not settings.auth_jwt_secret:
        raise RuntimeError("AUTH_JWT_SECRET is not configured.")
    now = datetime.now(timezone.utc)
    ttl = timedelta(minutes=settings.auth_token_ttl_minutes)
    expires = now + ttl
    payload: dict[str, Any] = {
        "sub": username,
        "role": "admin",
        "iss": "pipi-datacatalog",
        "iat": now,
        "exp": expires,
        "jti": str(uuid4()),
    }
    token = jwt.encode(payload, settings.auth_jwt_secret, algorithm="HS256")
    return token, int(ttl.total_seconds())


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    if not settings.auth_jwt_secret:
        raise jwt.InvalidTokenError("JWT secret is not configured")
    return jwt.decode(
        token,
        settings.auth_jwt_secret,
        algorithms=["HS256"],
        issuer="pipi-datacatalog",
        options={"require": ["exp", "iat", "iss", "sub"]},
    )


def check_login_rate_limit(request: Request, settings: Settings) -> None:
    global _rate_limiter
    if _rate_limiter is None or (
        _rate_limiter.attempts != settings.auth_rate_limit_attempts
        or _rate_limiter.window_seconds != settings.auth_rate_limit_window_seconds
    ):
        _rate_limiter = LoginRateLimiter(
            settings.auth_rate_limit_attempts,
            settings.auth_rate_limit_window_seconds,
        )
    client = request.client.host if request.client else "unknown"
    if not _rate_limiter.allow(client):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Protect API and UI paths with short-lived bearer tokens when enabled."""

    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next):
        if not self.settings.auth_enabled:
            return await call_next(request)

        path = request.url.path
        protected = path.startswith("/api/v1") or path.startswith("/ui")
        exempt = path.startswith("/api/v1/auth/")
        if not protected or exempt:
            return await call_next(request)

        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            claims = decode_access_token(token, self.settings)
        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication token expired."},
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid authentication token."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        request.state.user = claims
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "media-src 'self' https:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        if self.settings.security_hsts_enabled:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response
