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

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
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
