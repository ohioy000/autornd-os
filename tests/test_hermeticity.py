"""The suite cannot reach the provider, and cannot read the operator's
configuration (ARCH-20261002-112's constraint, implemented under
ARCH-20261002-116, which found the command unexecuted on main).

Three properties, each proved by breaking the guard or the isolation
and quoting what gets through:

1. THE GUARD REFUSES. A non-loopback connect and a non-loopback name
   resolution are both refused at the socket primitives, and each
   attempt is recorded with the test that made it. Loopback is
   allowed, and a completed loopback connection is recorded as
   completed — attempted connections are reported separately from
   completed ones. These tests carry the `hermetic_probe` marker:
   they deliberately attempt what every other test may not, so the
   teardown check in conftest does not fail them for their own
   deliberate probes.

2. THE SUITE'S SETTINGS ARE ITS OWN. With sentinel values exported
   AND a .env holding sentinels in the working directory, the
   suite's settings equal its placeholders. The control run proves
   the mechanism: without the suite's isolation switch, the same
   .env reaches the settings — so the switch, not luck, is what
   isolates the suite.

3. THE DOUBLE IS PROVIDER-FREE. make_mock_client stubs every method
   that reaches the network, rerank included.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

import tests.hermetic_guard as guard

# A remote address that needs no resolution, so the probe measures
# the guard and nothing else.
REMOTE = "93.184.216.34"


@pytest.mark.hermetic_probe
class TestTheGuardRefuses:
    def test_a_nonloopback_connect_is_refused_and_recorded(self):
        before = len(guard.ATTEMPTS)
        with pytest.raises(guard.HermeticRefusal):
            socket.create_connection((REMOTE, 80), timeout=0.1)
        attempts = guard.ATTEMPTS[before:]
        assert attempts, "the attempt was not recorded: no evidence"
        assert attempts[-1]["target"].startswith(REMOTE)
        assert attempts[-1]["outcome"] == "refused-nonloopback"
        assert attempts[-1]["test"], "the record names no test"

    def test_a_nonloopback_name_is_never_resolved(self):
        before = len(guard.ATTEMPTS)
        with pytest.raises(guard.HermeticRefusal):
            socket.getaddrinfo("example.com", 443)
        attempts = guard.ATTEMPTS[before:]
        assert attempts, "the resolution attempt was not recorded"
        assert attempts[-1]["target"] == "example.com"
        assert attempts[-1]["outcome"] == "refused-nonloopback"

    async def test_a_loopback_connection_completes_and_is_recorded(self):
        """Loopback stays available, and a completed connection is
        reported as completed — not merely attempted."""
        async def _handler(reader, writer):
            # Close the server side too: since Python 3.12,
            # server.wait_closed() waits for every client handler
            # to finish, and a handler that leaves its writer open
            # keeps the connection tracked after the client's FIN
            # (which only half-closes the server side).
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(_handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        before = len(guard.ATTEMPTS)
        try:
            reader, writer = await asyncio.open_connection(
                "127.0.0.1", port)
            writer.close()
            await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()
        attempts = guard.ATTEMPTS[before:]
        assert attempts, "the loopback connection was not recorded"
        assert attempts[-1]["target"] == f"127.0.0.1:{port}"
        assert attempts[-1]["outcome"] == "loopback"

    def test_the_summary_separates_attempts_from_completions(self):
        counts = guard.summary()
        assert counts["attempts"] == (
            counts["refused_nonloopback"] + counts["loopback_completed"]
            + counts["loopback_failed"])
        assert counts["attempts"] >= 1, "no attempt has been recorded yet"


@pytest.mark.hermetic_probe
class TestTheSettingsAreTheSuitesOwn:
    """Sentinels cannot displace the suite's settings — not an
    export, not a .env in the working directory, not both."""

    # Everything the suite forces, with a sentinel value that could
    # only come from outside the suite.
    SENTINELS = {
        "MODEL_TRIAGE": "sentinel/triage-x",
        "MODEL_ENGINEERING": "sentinel/engineering-x",
        "MODEL_ARCHITECTURE": "sentinel/architecture-x",
        "MODEL_ESCALATION": "sentinel/escalation-x",
        "MODEL_RESEARCH": "sentinel/research-x",
        "MODEL_SEARCH": "sentinel/search-x",
        "MODEL_RANKER": "sentinel/ranker-x",
        "MODEL_PREMIUM": "sentinel/premium-x",
        "MODEL_JUDGE": "sentinel/judge-x",
        "OPENROUTER_API_KEY": "sentinel-owner-key",
        "OPENROUTER_PROVIDER_ORDER": "sentinel-provider",
        "OPENROUTER_PROVIDER_FALLBACKS": "true",
        "API_KEY": "sentinel-api-key",
        "JWT_SECRET": "sentinel-jwt-secret",
        "ALLOW_UNAUTHENTICATED_REMOTE": "true",
    }

    PLACEHOLDERS = {
        "model_triage": "test-provider/test-triage",
        "model_engineering": "test-provider/test-engineering",
        "model_architecture": "test-provider/test-architecture",
        "model_escalation": "test-provider/test-escalation",
        "model_research": "test-provider/test-research",
        "model_search": "test-provider/test-search",
        "model_ranker": "test-provider/test-ranker",
        "model_premium": "test-provider/test-premium",
        "model_judge": "test-provider/test-judge",
        "openrouter_api_key": "",
        "openrouter_provider_order": "",
        "openrouter_provider_fallbacks": "",
        "api_key": "",
        "jwt_secret": "",
        "allow_unauthenticated_remote": False,
    }

    @staticmethod
    def _run_subprocess(cwd: Path, env: dict,
                        startup: str = "") -> dict:
        """Import the suite's settings in a subprocess and dump them.

        `startup` is imported before the settings, so a subprocess can
        run the suite's own startup (tests.conftest, which forces the
        suite's settings and installs the guard) exactly as a test
        session does.
        """
        script = (
            "import json\n"
            + startup
            + "from autornd.config import settings\n"
            "names = " + json.dumps(list(
                TestTheSettingsAreTheSuitesOwn.PLACEHOLDERS)) + "\n"
            "print(json.dumps({n: getattr(settings, n) for n in names}))\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=cwd, env=env, capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    @staticmethod
    def _clean_env() -> dict:
        """The parent env with every setting the suite forces removed."""
        env = dict(os.environ)
        for name in list(env):
            if (name.startswith("MODEL_")
                    or name in TestTheSettingsAreTheSuitesOwn.SENTINELS):
                del env[name]
        env.pop("AUTORND_HERMETIC", None)
        return env

    def test_sentinels_exported_and_dotted_cannot_displace_the_suite(
            self, tmp_path):
        # The suite's own startup, run in a subprocess whose shell
        # exports sentinels and whose working directory holds a
        # sentinel .env — the two ways an operator's configuration
        # reaches a checkout. The startup forces the suite's settings
        # (an export cannot displace an assignment that comes after
        # it) and the suite's switch keeps the .env out of the
        # settings, so every value is the suite's own.
        env = self._clean_env()
        env.update(self.SENTINELS)
        env["AUTORND_HERMETIC"] = "1"
        # The subprocess imports tests.conftest, so the suite's root
        # must be importable from it.
        env["PYTHONPATH"] = str(
            Path(__file__).resolve().parent.parent)
        # Condition two: a .env holding sentinels sits in the
        # subprocess's working directory. Built under tmp_path,
        # never in the repo.
        (tmp_path / ".env").write_text(
            "\n".join(f"{k}={v}" for k, v in self.SENTINELS.items())
            + "\n")
        settings = self._run_subprocess(
            tmp_path, env, startup="import tests.conftest\n")
        for name, expected in self.PLACEHOLDERS.items():
            assert settings[name] == expected, (
                f"{name} read {settings[name]!r}, expected {expected!r}: "
                f"an export or a .env displaced the suite's setting")

    def test_the_control_proves_the_isolation_switch_is_what_isolates(
            self, tmp_path):
        """Without the suite's switch, the same .env reaches the
        settings — production behaviour, unchanged. This is the
        control that shows the switch, not chance, isolates the
        suite."""
        env = self._clean_env()
        assert "AUTORND_HERMETIC" not in env
        # The .env alone (no export) carries sentinels for every
        # required tier — the settings refuse to build with a tier
        # unset, so a partial .env would prove the exit, not the
        # read.
        (tmp_path / ".env").write_text(
            "\n".join(
                f"MODEL_{name.upper()}=sentinel/{name}-x"
                for name in ("triage", "engineering", "architecture",
                             "escalation", "research", "search"))
            + "\nOPENROUTER_API_KEY=sentinel-owner-key\n")
        settings = self._run_subprocess(tmp_path, env)
        assert settings["model_triage"] == "sentinel/triage-x"
        assert settings["openrouter_api_key"] == "sentinel-owner-key"


class TestTheDoubleIsProviderFree:
    async def test_the_double_stubs_rerank(self):
        from tests.conftest import make_mock_client

        client = make_mock_client({})
        with pytest.raises(RuntimeError, match="not part of the test double"):
            await client.rerank("test/reranker", "q", ["x"], top_n=3)
