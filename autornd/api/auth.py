"""Authentication middleware — JWT tokens + API key fallback."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from autornd.config import settings

_PUBLIC_PATHS = {"/", "/api/health", "/api/auth/register", "/api/auth/login"}

_jwt_secret: str = ""


def _get_jwt_secret() -> str:
    global _jwt_secret
    if not _jwt_secret:
        _jwt_secret = settings.jwt_secret or secrets.token_hex(32)
    return _jwt_secret


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return salt.hex() + ":" + dk.hex()


def verify_password(password: str, hashed: str) -> bool:
    try:
        salt_hex, dk_hex = hashed.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
        return secrets.compare_digest(dk.hex(), dk_hex)
    except (ValueError, TypeError):
        return False


def create_token(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=72),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        data = jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
        data["sub"] = int(data["sub"])
        return data
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError, KeyError):
        return None


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _PUBLIC_PATHS or request.url.path.startswith("/static"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        token = auth_header[7:] if auth_header.startswith("Bearer ") else ""

        # Try JWT first
        if token:
            payload = decode_token(token)
            if payload:
                request.state.user_id = payload.get("sub")
                request.state.username = payload.get("username")
                return await call_next(request)

        # Fall back to API key
        if settings.api_key and token and secrets.compare_digest(token, settings.api_key):
            request.state.user_id = None
            request.state.username = None
            return await call_next(request)

        # No auth required if neither api_key nor jwt_secret is configured
        if not settings.api_key and not settings.jwt_secret:
            request.state.user_id = None
            request.state.username = None
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing credentials"},
        )
