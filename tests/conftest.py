"""Shared test fixtures — in-memory SQLite, mock OpenRouter client.

The suite's configuration belongs to the suite, wherever the suite
runs (ARCH-20261002-112's constraint, implemented under
ARCH-20261002-116, which found the command unexecuted on main):
every model tier the settings read — required and optional — the
provider key, provider order, provider fallbacks and every
credential setting are FORCED to a placeholder or an empty value
before any autornd import. `setdefault` is deliberately not used:
an exported value (the executor's shell exports the owner's pins)
or a .env in the working directory (the checkout holds the
owner's) must not displace the suite's own settings. A test that
needs a different value sets it itself, via monkeypatch.

The suite also cannot reach the provider: the hermetic guard
(tests/hermetic_guard.py) is installed before any test module is
imported and refuses every non-loopback name resolution and
connection, recording each attempt and failing the test that made
it. Suite runs are therefore independent of the shell and the
checkout they run from — and they cannot spend anyone's credits.
"""

from __future__ import annotations

import os

# The suite's own settings. Forced (not setdefault): see the
# module docstring. AUTORND_HERMETIC also keeps the settings
# from reading a .env in the working directory
# (autornd/config.py).
os.environ["AUTORND_HERMETIC"] = "1"

_TIERS = {
    "MODEL_TRIAGE": "test-provider/test-triage",
    "MODEL_ENGINEERING": "test-provider/test-engineering",
    "MODEL_ARCHITECTURE": "test-provider/test-architecture",
    "MODEL_ESCALATION": "test-provider/test-escalation",
    "MODEL_RESEARCH": "test-provider/test-research",
    "MODEL_SEARCH": "test-provider/test-search",
    "MODEL_RANKER": "test-provider/test-ranker",
    "MODEL_PREMIUM": "test-provider/test-premium",
    "MODEL_JUDGE": "test-provider/test-judge",
}
for _name, _value in _TIERS.items():
    os.environ[_name] = _value

# Every credential and provider-routing setting the settings read.
# Empty is the suite's baseline: no key, no pin, no fallback, no
# remote serving, no profile. Tests that exercise one of these set
# it themselves.
_CREDENTIALS = {
    "OPENROUTER_API_KEY": "",
    "OPENROUTER_PROVIDER_ORDER": "",
    "OPENROUTER_PROVIDER_FALLBACKS": "",
    "API_KEY": "",
    "JWT_SECRET": "",
    "ALLOW_UNAUTHENTICATED_REMOTE": "false",
    "REGISTRATION_ENABLED": "true",
    "AUTORND_PROFILE": "",
    "AUTORND_WORKFLOW": "",
}
for _name, _value in _CREDENTIALS.items():
    os.environ[_name] = _value

from tests.hermetic_guard import install as _install_guard

_install_guard()

import asyncio
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
import autornd.models.user  # noqa: F401 — register User model
import tests.hermetic_guard as hermetic_guard

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


@pytest.fixture(autouse=True)
def _hermetic_guard(request):
    """Fail the test that reached for the network, by name.

    The guard refuses a non-loopback connection at the socket, but
    code under test may catch the refusal and carry on (the
    catalogue fetch does exactly that). The record is therefore
    checked at teardown: a refused attempt attributed to this test
    fails it here, whatever the code under test did with the error.

    `hermetic_probe` marks a test that deliberately attempts a
    non-loopback connection to prove the guard refuses it — the
    attempt is the test's subject, not a violation by it.
    """
    hermetic_guard.CURRENT["nodeid"] = request.node.nodeid
    yield
    hermetic_guard.CURRENT["nodeid"] = None
    if request.node.get_closest_marker("hermetic_probe"):
        return
    refused = hermetic_guard.refused_for(request.node.nodeid)
    if refused:
        shown = "; ".join(
            f"{a['target']} ({a['outcome']})" for a in refused[:5])
        pytest.fail(
            f"hermetic violation: this test attempted {len(refused)} "
            f"non-loopback connection(s) the guard refused: {shown}")


def pytest_runtest_makereport(item, call):
    """Keep the guard's record tied to the test that made it."""
    if call.when == "setup":
        hermetic_guard.CURRENT["nodeid"] = item.nodeid


def pytest_sessionfinish(session, exitstatus):
    """The session's network-attempt evidence, counted and written.

    Attempted connections are reported separately from completed
    ones: the summary and the log (AUTORND_HERMETIC_LOG, a JSONL
    file of one record per attempt) say how many were refused
    non-loopback, how many loopback connections completed, and how
    many loopback connections failed.
    """
    counts = hermetic_guard.summary()
    log_path = os.environ.get("AUTORND_HERMETIC_LOG")
    if log_path:
        hermetic_guard.write_log(log_path)
    hermetic_guard.CURRENT["nodeid"] = None


def make_mock_response(content: dict[str, Any], model: str = "test-model") -> ModelResponse:
    return ModelResponse(
        content=json.dumps(content),
        model=model,
        prompt_tokens=100,
        completion_tokens=50,
        cost=0.001,
    )


def make_mock_client(responses: dict[str, dict[str, Any]],
                     delays: dict[str, float] | None = None) -> OpenRouterClient:
    """A client that returns preset responses per function, and bills for them.

    The double accounts exactly as the real client does. Spend and call counts
    live on the client precisely so no call path can avoid them, and a test
    double that answered for free would hide the bug this guards against —
    including from the tests that assert one workflow is cheaper than another.

    `delays` makes a function's calls take that long, in seconds ("default"
    applies to any function not named). The sleep comes before the bill, as a
    real call's cost arrives with its response, so a call cancelled mid-sleep
    bills nothing. Ruling D38's watchdog tests need calls with a duration.

    Every method that reaches the network is stubbed: chat and chat_json
    answer from `responses`, and rerank raises rather than posting — a run
    ingests what it looks up, so a later retrieval would otherwise probe the
    provider's rerank API from inside a test (ARCH-20261002-112's audit
    measured exactly that: a real rerank on the owner's ranker pin).
    """
    client = OpenRouterClient(api_key="test-key")
    delays = delays or {}

    async def _wait(function: str) -> None:
        seconds = delays.get(function, delays.get("default", 0.0))
        if seconds:
            await asyncio.sleep(seconds)

    async def _mock_chat_json(
        function: str,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], ModelResponse]:
        await _wait(function)
        data = responses.get(function, responses.get("default", {}))
        response = make_mock_response(data, f"mock-{function}")
        client._account(function, response.cost)
        return data, response

    async def _mock_chat(
        function: str, system_prompt: str, user_message: str, **kwargs: Any,
    ) -> ModelResponse:
        await _wait(function)
        data = responses.get(function, responses.get("default", {}))
        response = make_mock_response(data, f"mock-{function}")
        client._account(function, response.cost)
        return response

    async def _mock_rerank(
        model: str, query: str, documents: list[str], top_n: int,
        **kwargs: Any,
    ) -> list[tuple[int, float]]:
        # The double must bill what it would have spent, and must
        # not post: a provider-free run makes no provider call,
        # billed or not. Rerank has no per-call rate in the
        # catalogue, so the honest double is one that refuses the
        # call the way an unsupported endpoint does.
        raise RuntimeError(
            "rerank is not part of the test double "
            "(hermetic suite, ARCH-20261002-112/116)")

    client.chat_json = AsyncMock(side_effect=_mock_chat_json)
    client.chat = AsyncMock(side_effect=_mock_chat)
    client.rerank = AsyncMock(side_effect=_mock_rerank)
    client.close = AsyncMock()
    return client
