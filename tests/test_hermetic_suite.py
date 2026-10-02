"""The suite is hermetic: its configuration is its own, and it makes no
network call (ARCH-20261002-112).

The advisor's audit of 2026-10-02 found the suite reading the owner's .env
and reaching the provider five times in one run — each carrying the owner's
key. The suite's answer is two enforced halves: the placeholders in
tests/conftest.py are forced before the first autornd import (nothing in the
shell and nothing in a .env can displace them), and a session guard refuses
every non-loopback socket, recording the attempt and failing the test that
made it by name even when the code under test swallowed the error.

These tests prove both mechanisms end to end, including the guard itself —
which runs in a child pytest so this suite's own record stays empty.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from autornd.config import Settings, settings

# The tiers whose placeholders are suite-chosen rather than declared defaults,
# plus the store path: a fresh directory per run, so a leftover collection
# from an earlier run cannot break the store tests on a dimension mismatch.
SUITE_CHOSEN = {
    "model_triage", "model_engineering", "model_architecture",
    "model_escalation", "model_research", "model_search",
    "chromadb_path",
}

# Not a setting: the class-annotated set of runtime-mutable names, which
# pydantic nonetheless reports as a field.
NOT_SETTINGS = {"RUNTIME_MUTABLE"}

_PROBE = (
    "import json; "
    "import tests.conftest as c; "
    "from autornd.config import settings; "
    # RUNTIME_MUTABLE's stringified set is unordered, and chromadb_path is a
    # fresh temp directory per process — both differ run to run by design.
    "print(json.dumps({k: v for k, v in settings.model_dump().items() "
    "if k not in ('RUNTIME_MUTABLE', 'chromadb_path')}, default=str))"
)


def _minimal_env() -> dict:
    return {"PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "LANG": os.environ.get("LANG", "C"),
            # so a probe run from tmp_path still finds the suite
            "PYTHONPATH": os.getcwd()}


def _run_probe(env: dict, cwd) -> dict:
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE],
        env=env, cwd=cwd, capture_output=True, text=True,
        timeout=120)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


class TestThePlaceholdersWin:
    """(a) The suite's settings equal its placeholders in both conditions the
    command names: sentinels exported in the shell, and a sentinel .env in
    the working directory. Neither can displace them."""

    def test_every_setting_is_forced(self):
        """Nothing can slip past the map: a new field must be classified."""
        from tests.conftest import PLACEHOLDERS

        assert set(PLACEHOLDERS) == {
            name.upper() for name in Settings.model_fields} - NOT_SETTINGS

    def test_non_security_fields_take_their_declared_defaults(self):
        """The map may not drift from the defaults it is meant to pin."""
        from tests.conftest import PLACEHOLDERS

        for name, field in Settings.model_fields.items():
            if name in SUITE_CHOSEN or name in NOT_SETTINGS:
                continue
            assert getattr(settings, name) == field.default, name

    def test_exported_sentinels_cannot_displace_the_placeholders(self):
        from tests.conftest import PLACEHOLDERS

        env = _minimal_env()
        env["MODEL_TRIAGE"] = "sentinel/x"
        env["MODEL_RANKER"] = "sentinel/r"
        env["OPENROUTER_API_KEY"] = "sentinel-key"
        observed = _run_probe(env, cwd=os.getcwd())
        expected = _run_probe(_minimal_env(), cwd=os.getcwd())
        assert observed == expected
        assert observed["model_triage"] == PLACEHOLDERS["MODEL_TRIAGE"]
        assert observed["openrouter_api_key"] == ""

    def test_a_dotenv_in_the_working_directory_cannot_displace_them(
            self, tmp_path):
        """Built under tmp_path — no step of this work touches a .env inside
        the repo (G-3)."""
        from tests.conftest import PLACEHOLDERS

        (tmp_path / ".env").write_text(
            "MODEL_TRIAGE=sentinel/from-dotenv\n"
            "MODEL_RANKER=sentinel/r\n"
            "OPENROUTER_API_KEY=sentinel-key\n"
            "RUN_SPEND_CEILING_USD=99.0\n"
            "MAX_ITERATIONS=20\n")
        observed = _run_probe(_minimal_env(), cwd=tmp_path)
        expected = _run_probe(_minimal_env(), cwd=os.getcwd())
        assert observed == expected
        assert observed["model_triage"] == PLACEHOLDERS["MODEL_TRIAGE"]
        assert observed["run_spend_ceiling_usd"] == 0.50
        assert observed["max_iterations"] == 5

    def test_the_suite_reads_no_dotenv_file_at_all(self):
        """The mechanism, asserted where it lives: under AUTORND_TESTING the
        settings have no dotenv file to read — a checkout holding the owner's
        .env and one that does not are the same configuration."""
        assert os.environ.get("AUTORND_TESTING") == "1"
        assert Settings.model_config.get("env_file") is None


class TestTheGuardRefusesNonLoopback:
    """(b) The guard fails a test that opens a non-loopback connection — by
    name, even when the code under test catches the error. Proved in a child
    pytest so this suite's own record stays empty: the child's attempt is the
    guard working, not a leak."""

    def _run_child(self, tmp_path, body: str) -> subprocess.CompletedProcess:
        scratch = tmp_path / "test_zz_guard_probe.py"
        scratch.write_text(body)
        return subprocess.run(
            [sys.executable, "-m", "pytest", str(scratch),
             "-p", "tests.conftest", "-q", "-p", "no:cacheprovider"],
            env=_minimal_env(), cwd=os.getcwd(),
            capture_output=True, text=True, timeout=180)

    def test_a_test_that_reaches_out_is_failed_by_name(self, tmp_path):
        proc = self._run_child(tmp_path, (
            "import socket\n"
            "def test_reaches_out_and_survives():\n"
            "    try:\n"
            "        socket.getaddrinfo('guard-proof.invalid', 80)\n"
            "    except OSError:\n"
            "        pass          # swallowed: the teardown must still fail it\n"))
        assert proc.returncode != 0, proc.stdout
        assert "attempted network access" in proc.stdout
        assert "test_reaches_out_and_survives" in proc.stdout
        assert "guard-proof.invalid" in proc.stdout

    def test_loopback_stays_available(self, tmp_path):
        proc = self._run_child(tmp_path, (
            "import socket\n"
            "def test_loopback_is_allowed():\n"
            "    socket.getaddrinfo('localhost', 80)\n"
            "    socket.getaddrinfo('127.0.0.1', 80)\n"))
        assert proc.returncode == 0, proc.stdout
        assert "attempted network access" not in proc.stdout

    def test_a_catching_test_is_still_the_one_named(self, tmp_path):
        """The clause the five leaks rode on: the code under test swallowed
        the error and the test passed while the provider was reached."""
        proc = self._run_child(tmp_path, (
            "import socket\n"
            "def test_catches_the_refusal():\n"
            "    try:\n"
            "        socket.create_connection(('198.51.100.1', 80), timeout=1)\n"
            "    except OSError:\n"
            "        return\n"
            "    raise AssertionError('connected')\n"))
        assert proc.returncode != 0
        assert "test_catches_the_refusal" in proc.stdout
        assert "attempted network access" in proc.stdout

    def test_the_classification(self):
        from tests.conftest import _NetworkGuard

        assert _NetworkGuard._is_loopback("127.0.0.1")
        assert _NetworkGuard._is_loopback("::1")
        assert _NetworkGuard._is_loopback("[::1]")
        assert _NetworkGuard._is_loopback("localhost")
        assert _NetworkGuard._is_loopback(None)
        assert not _NetworkGuard._is_loopback("openrouter.ai")
        assert not _NetworkGuard._is_loopback("198.51.100.1")
        assert not _NetworkGuard._is_loopback(b"openrouter.ai")
