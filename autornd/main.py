"""FastAPI entry point for AutoRnD."""

import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from autornd.api.auth import APIKeyMiddleware
from autornd.api.dashboard import dashboard_router
from autornd.api.routes import router
from autornd.config import settings
from autornd.database import init_db
import autornd.knowledge.episodic  # noqa: F401 — register Episode model
import autornd.models.user  # noqa: F401 — register User model

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    from autornd.routing.openrouter import check_models
    logger = logging.getLogger("autornd")

    # Ruling D45 (1): an open server is logged at startup and reported by
    # /api/health, so it cannot be mistaken for a closed one.
    if settings.allow_unauthenticated_remote:
        logger.warning(
            "ALLOW_UNAUTHENTICATED_REMOTE=1: this server serves remote "
            "callers WITHOUT authentication — anyone who can reach this port "
            "can start runs and spend the owner's credits")
    elif not settings.api_key and not settings.jwt_secret:
        logger.info(
            "No API_KEY or JWT_SECRET configured: serving loopback callers "
            "only (Ruling D45). Set one in .env to serve remote callers.")

    try:
        status = await check_models()
        available = sum(1 for s in status.values() if s.get("available") is True)
        total = len(status)
        if available == total:
            logger.info("Model check: %d/%d models available", available, total)
        else:
            for fn, info in status.items():
                if info.get("available") is False:
                    logger.warning("Model unavailable — %s: %s", fn, info["model"])
            logger.warning("Model check: %d/%d models available — check config", available, total)
    except Exception:
        logger.warning("Model check skipped — could not reach OpenRouter")

    yield


app = FastAPI(
    title="AutoRnD",
    description="Engineering & R&D Agentic Team",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(APIKeyMiddleware)
app.include_router(router)
app.include_router(dashboard_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    logging.getLogger("autornd").error("Unhandled exception:\n%s", "".join(tb))
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": "".join(tb)},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "autornd.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
