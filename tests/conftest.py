"""Shared test fixtures — in-memory SQLite, mock OpenRouter client."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from autornd.database import Base, get_session
from autornd.main import app
from autornd.routing.openrouter import ModelResponse, OpenRouterClient
import autornd.knowledge.episodic  # noqa: F401 — register Episode model

test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_factory() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def api_client(db_session):
    async def _override_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


def make_mock_response(content: dict[str, Any], model: str = "test-model") -> ModelResponse:
    return ModelResponse(
        content=json.dumps(content),
        model=model,
        prompt_tokens=100,
        completion_tokens=50,
        cost=0.001,
    )


def make_mock_client(responses: dict[str, dict[str, Any]]) -> OpenRouterClient:
    """Create a mock OpenRouter client that returns preset responses per function."""
    client = OpenRouterClient(api_key="test-key")

    async def _mock_chat_json(
        function: str,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> tuple[dict[str, Any], ModelResponse]:
        data = responses.get(function, responses.get("default", {}))
        return data, make_mock_response(data, f"mock-{function}")

    client.chat_json = AsyncMock(side_effect=_mock_chat_json)
    client.close = AsyncMock()
    return client
