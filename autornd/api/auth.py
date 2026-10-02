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

# Ruling D45 (1): unauthenticated serving is loopback-only. These are the
# addresses of callers physically on this machine — the loopback interface.
# The host comes from the socket peer, not from anything a request can carry,
# so it cannot be spoofed remotely. Starlette's in-process test client reports
# 'testclient' as its host; it is deliberately NOT accepted here: a test that
# wants remote-caller behaviour passes a client host, and the rule is never
# widened to make a test pass.
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _is_loopback(request: Request) -> bool:
    host = (request.client.host if request.client else "") or ""
    return host in _LOOPBACK_HOSTS or host.startswith("127.")


_UNAUTHENTICATED_REMOTE_FIX = (
    "This server has no authentication configured and serves loopback callers "
    "only. Set API_KEY or JWT_SECRET in .env to serve remote callers, or set "
    "ALLOW_UNAUTHENTICATED_REMOTE=1 to serve everyone without authentication "
    "(anyone who can reach this port can then spend the owner's credits)."
)

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
        # Ruling D45 (1): /api/health stays open to everyone — CI's docker
        # job reads it from outside the container and must stay green.
        if request.url.path == "/api/health":
            return await call_next(request)

        # No authentication configured: loopback only, unless the operator
        # deliberately opened it (logged at startup, reported by /api/health).
        if (not settings.api_key and not settings.jwt_secret
                and not settings.allow_unauthenticated_remote
                and not _is_loopback(request)):
            return JSONResponse(status_code=403,
                                content={"detail": _UNAUTHENTICATED_REMOTE_FIX})

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
