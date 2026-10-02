"""Shared test fixtures — in-memory SQLite, mock OpenRouter client.

The suite is hermetic by construction (ARCH-20261002-112): its configuration
is the suite's, and nothing it runs reaches the network. Both are enforced
rather than assumed — the placeholders below are forced, the guard further
down refuses every non-loopback socket, and tests/test_hermetic_suite.py
proves both end to end.
"""

from __future__ import annotations

import os

# ── 1. The suite's configuration belongs to the suite ───────────────────────
# Both halves, because each covers the other's hole. AUTORND_TESTING keeps
# Settings from reading any dotenv file at all (a checkout holding the owner's
# .env is then the same configuration as one that does not), and the fields
# below are FORCED — not setdefault — so nothing exported in the shell can
# displace them either. The owner's exported pins used to beat the old
# placeholders silently, and two tests judged the owner's models instead of
# the suite's. Required tiers carry named placeholders; optional tiers, the
# credentials and the provider order are empty, which is the suite's
# configuration (an empty ranker never reranks, an empty premium never runs an
# independent pass); everything else takes its declared default.
# tests/test_hermetic_suite.py guards both lists against drift.
os.environ["AUTORND_TESTING"] = "1"

PLACEHOLDERS: dict[str, str] = {
    # credentials and transport — empty, and nothing can fill them here
    "OPENROUTER_API_KEY": "",
    "API_KEY": "",
    "JWT_SECRET": "",
    "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
    "OPENROUTER_PROVIDER_ORDER": "",
    "OPENROUTER_PROVIDER_FALLBACKS": "",
    # required tiers — named placeholders
    "MODEL_TRIAGE": "test-provider/test-triage",
    "MODEL_ENGINEERING": "test-provider/test-engineering",
    "MODEL_ARCHITECTURE": "test-provider/test-architecture",
    "MODEL_ESCALATION": "test-provider/test-escalation",
    "MODEL_RESEARCH": "test-provider/test-research",
    "MODEL_SEARCH": "test-provider/test-search",
    # optional tiers — empty: the features are off, exactly as on a machine
    # that never configured them
    "MODEL_RANKER": "",
    "MODEL_PREMIUM": "",
    "MODEL_JUDGE": "",
    # everything else — the declared defaults
    "DATABASE_URL": "sqlite+aiosqlite:///./autornd.db",
    "API_HOST": "127.0.0.1",
    "API_PORT": "8100",
    "LOG_LEVEL": "INFO",
    "MAX_ITERATIONS": "5",
    "REVIEW_REWORK_ATTEMPTS": "2",
    "PLAN_MAX_TOKENS": "32768",
    "ESCALATION_MAX_TOKENS": "16384",
    "VALIDATE_MAX_TOKENS": "8000",
    "JUDGE_MAX_TOKENS": "8000",
    "SEARCH_MAX_TOKENS": "1500",
    "SEARCH_MAX_TOKENS_CONSEQUENTIAL": "4000",
    "ESCALATION_RECOVERY_ATTEMPTS": "3",
    "RUN_TIME_BUDGET_SECONDS": "1800",
    "RUN_SPEND_CEILING_USD": "0.50",
    "MAX_CONCURRENT_RUNS": "2",
    "ALLOW_UNAUTHENTICATED_REMOTE": "false",
    "CHROMADB_PATH": "./chromadb_data",
    "REGISTRATION_ENABLED": "true",
    "AUTORND_PROFILE": "",
    "AUTORND_WORKFLOW": "engineering-rnd",
}
for _name, _value in PLACEHOLDERS.items():
    os.environ[_name] = _value

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

# ── 2. Nothing the suite runs reaches the network ───────────────────────────
# One guard for the whole session: name resolution and connect to any
# non-loopback address are refused and recorded. A test that trips it fails
# BY NAME in teardown even when the code under test caught the error and the
# test itself passed — which is exactly how the five leaks this command
# repaired survived. Loopback is allowed (ASGI and the API's own binds),
# and httpx.MockTransport / ASGITransport never touch a socket.
# tests/test_hermetic_suite.py proves the guard end to end and breaks it.
import ipaddress
import socket


class _NetworkGuard:
    def __init__(self) -> None:
        self.attempts: list[str] = []

    @staticmethod
    def _is_loopback(host: Any) -> bool:
        if host is None:
            return True          # passive bind / wildcard resolution
        if isinstance(host, (bytes, bytearray)):
            host = host.decode("ascii", "replace")
        if not isinstance(host, str):
            return False
        text = host.strip("[]")
        if text == "localhost":
            return True
        try:
            return ipaddress.ip_address(text).is_loopback
        except ValueError:
            return False         # a hostname: not loopback until proven

    def refuse(self, kind: str, target: str) -> None:
        self.attempts.append(f"{kind} {target}")
        raise OSError(
            f"the suite may not reach {target!r} — no network "
            f"(ARCH-20261002-112)")


_network_guard = _NetworkGuard()

_real_getaddrinfo = socket.getaddrinfo
_real_gethostbyname = socket.gethostbyname
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


def _guarded_getaddrinfo(host, *args, **kwargs):
    if not _NetworkGuard._is_loopback(host):
        _network_guard.refuse("resolve", str(host))
    return _real_getaddrinfo(host, *args, **kwargs)


def _guarded_gethostbyname(host):
    if not _NetworkGuard._is_loopback(host):
        _network_guard.refuse("resolve", str(host))
    return _real_gethostbyname(host)


def _guarded_connect(sock, address):
    target = address[0] if isinstance(address, tuple) and address else address
    if not _NetworkGuard._is_loopback(target):
        _network_guard.refuse("connect", repr(address))
    return _real_connect(sock, address)


def _guarded_connect_ex(sock, address):
    target = address[0] if isinstance(address, tuple) and address else address
    if not _NetworkGuard._is_loopback(target):
        _network_guard.refuse("connect", repr(address))
    return _real_connect_ex(sock, address)


socket.getaddrinfo = _guarded_getaddrinfo
socket.gethostbyname = _guarded_gethostbyname
socket.socket.connect = _guarded_connect
socket.socket.connect_ex = _guarded_connect_ex

# Chroma's default embedding function downloads a ~80 MB ONNX model from S3
# the first time it embeds. Locally the cache hides that; in CI every
# store-touching test fetched it — a sixth network surface the audit's five
# did not count, caught here by the guard (ARCH-20261002-112). A deterministic
# local embedder keeps the retrieval tests testing retrieval and the suite
# offline: same shape every input, different across inputs.
import hashlib

import chromadb.utils.embedding_functions as _chroma_ef


class _LocalEmbeddings:
    @staticmethod
    def name() -> str:
        return "local-deterministic-tests"

    def __call__(self, texts):
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vectors.append([b / 255.0 for b in digest[:16]])
        return vectors


_chroma_ef.ONNXMiniLM_L6_V2 = _LocalEmbeddings


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    # What the guard measured, on the record (convention 26).
    terminalreporter.write_line(
        f"network guard: {len(_network_guard.attempts)} non-loopback "
        f"attempt(s) recorded"
        + (f" — {_network_guard.attempts}" if _network_guard.attempts else ""))


@pytest.fixture(autouse=True)
def _no_network_attempts(request):
    before = len(_network_guard.attempts)
    yield
    fresh = _network_guard.attempts[before:]
    if fresh:
        pytest.fail(
            f"{request.node.nodeid} attempted network access: {fresh}",
            pytrace=False)


# ── 3. The test database: one in-memory engine shared per test ──────────────

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


def seal_double(client: OpenRouterClient) -> OpenRouterClient:
    """Complete a hand-built double: stub every network method it leaves live.

    ARCH-20261002-112: a double that patches `chat_json` but leaves `chat` or
    `rerank` real can reach the provider — the context builder's research
    lookup uses `chat`, and rerank's native path uses `rerank`. A transport
    double (`client._client` replaced by a local fake) is already provider-free
    and needs nothing; this is for the half-patched kind. Methods already
    stubbed are left alone, so it is safe to call on any double.
    """
    for name in ("chat", "chat_json", "rerank"):
        method = getattr(client, name)
        if isinstance(method, AsyncMock):
            continue
        setattr(client, name, AsyncMock(
            side_effect=RuntimeError(
                f"{name} is not part of this test double "
                f"(ARCH-20261002-112)")))
    return client


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

    client.chat_json = AsyncMock(side_effect=_mock_chat_json)
    client.chat = AsyncMock(side_effect=_mock_chat)
    # The double is provider-free (ARCH-20261002-112): rerank was the one
    # method left real, and a run that ingests its findings later probes the
    # provider's rerank API from inside a test. Raising is the honest stub —
    # the double does not serve rerank, and rerank_chunks falls back to
    # retrieval order exactly as it does when the provider refuses.
    client.rerank = AsyncMock(
        side_effect=RuntimeError("rerank is not part of the test double"))
    client.close = AsyncMock()
    return client

