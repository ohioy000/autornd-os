"""API key authentication middleware."""

from __future__ import annotations

import secrets

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from autornd.config import settings

_PUBLIC_PATHS = {"/", "/api/health"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.api_key:
            return await call_next(request)

        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        if request.url.path.startswith("/static"):
            return await call_next(request)

        token = request.headers.get("Authorization", "")
        if token.startswith("Bearer "):
            token = token[7:]

        if not token or not secrets.compare_digest(token, settings.api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
