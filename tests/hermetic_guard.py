"""The suite's hermetic guard: no test may reach the network.

Installed by tests/conftest.py before any test module is imported, so
it covers module-level code as well as every call the code under test
makes. The guard is independent of the code under test: it patches the
socket primitives themselves, so no library, client or double can
reach a non-loopback address without this module seeing it — the
suite cannot be made hermetic by asking its own code to behave.

What it enforces, per ARCH-20261002-112's constraint (implemented
under ARCH-20261002-116, which found the command unexecuted on main):

- every connection to a non-loopback address is refused, covering
  both name resolution (getaddrinfo) and connect (connect/connect_ex);
- each attempt is recorded — test, target, outcome — and fails the
  test that made it, by name, even when the code under test catches
  the error (the record is checked at teardown, so a swallowed
  refusal still fails the test);
- loopback, httpx.MockTransport and ASGITransport stay available
  (transports never touch a socket; a loopback server, as the
  watchdog tests use, is a connection this guard allows);
- attempted connections are reported separately from completed ones:
  a record's `outcome` says whether the connection was refused
  ("refused-nonloopback"), allowed and completed ("loopback"), or
  allowed and failed ("loopback-error").

The session's attempts are written to the path in AUTORND_HERMETIC_LOG
(JSONL, one record per attempt) when the session ends, and counted in
the terminal summary, so a suite run carries its own network-attempt
evidence.
"""

from __future__ import annotations

import json
import os
import socket
import time

# One record per attempt. `test` is the nodeid of the test in flight
# when the attempt was made, so a refused attempt fails that test by
# name. `outcome` is one of "refused-nonloopback", "loopback",
# "loopback-error".
ATTEMPTS: list[dict] = []

# The test in flight. Set by the hooks in tests/conftest.py.
CURRENT: dict[str, str | None] = {"nodeid": None}

_INSTALLED = False

_LOOPBACK_HOSTNAMES = {"localhost"}


class HermeticRefusal(OSError):
    """A non-loopback connection the suite may not make.

    Subclasses OSError rather than socket.error's siblings so a caller
    that catches network errors still catches the refusal — and the
    teardown check fails the test even if it catches this and moves on.
    """


def _is_loopback_address(host: str) -> bool:
    """Is this host a loopback address or name?

    An IP literal is judged directly; the only name this guard resolves
    is "localhost", so a name that is not "localhost" is never resolved
    at all — that is the denial, not a side effect of it.
    """
    host = (host or "").strip().strip("[]")
    if not host:
        return False
    if host in _LOOPBACK_HOSTNAMES:
        return True
    if host.startswith("127."):
        return True
    if host == "::1":
        return True
    # An IPv6 literal with a scope or a mapped form still names this
    # machine's loopback only in the ::1 case above; anything else is
    # remote.
    return False


def _record(target: str, outcome: str) -> dict:
    entry = {
        "test": CURRENT.get("nodeid"),
        "target": target,
        "outcome": outcome,
        "time": round(time.time(), 3),
    }
    ATTEMPTS.append(entry)
    return entry


def _connect(original):
    def guarded_connect(self, address):
        host = address[0] if isinstance(address, (tuple, list)) else address
        port = address[1] if isinstance(address, (tuple, list)) and len(address) > 1 else None
        target = f"{host}:{port}" if port is not None else str(host)
        if not _is_loopback_address(host):
            _record(target, "refused-nonloopback")
            raise HermeticRefusal(
                f"the test suite may not connect to {target} "
                f"(hermetic guard, ARCH-20261002-112/116): loopback "
                f"and in-process transports only")
        # asyncio connects non-blockingly: connect() raises
        # BlockingIOError while the connection is still being made, and
        # a second connect on the now-connected socket raises EISCONN.
        # Both are the allowed attempt completing, not a failure — only
        # a genuine OSError is one.
        try:
            result = original(self, address)
        except BlockingIOError:
            _record(target, "loopback")
            raise
        except OSError:
            _record(target, "loopback-error")
            raise
        else:
            _record(target, "loopback")
            return result
    return guarded_connect


def _connect_ex(original):
    def guarded_connect_ex(self, address):
        host = address[0] if isinstance(address, (tuple, list)) else address
        target = str(host)
        if not _is_loopback_address(host):
            _record(target, "refused-nonloopback")
            raise HermeticRefusal(
                f"the test suite may not connect to {target} "
                f"(hermetic guard, ARCH-20261002-112/116)")
        code = original(self, address)
        # connect_ex reports in-flight (EINPROGRESS/EAGAIN) and
        # already-connected (EISCONN) as error codes that are not
        # failures; the errno module names them portably.
        import errno
        if code == 0 or code in (errno.EISCONN, errno.EINPROGRESS,
                                 errno.EAGAIN):
            _record(target, "loopback")
        else:
            _record(target, "loopback-error")
        return code
    return guarded_connect_ex


def _getaddrinfo(original):
    def guarded_getaddrinfo(host, *args, **kwargs):
        # A name that is not "localhost" is never resolved: name
        # resolution for remote hosts is denied here, before any
        # connection is attempted.
        if not _is_loopback_address(str(host)):
            _record(str(host), "refused-nonloopback")
            raise HermeticRefusal(
                f"the test suite may not resolve {host!r} "
                f"(hermetic guard, ARCH-20261002-112/116)")
        return original(host, *args, **kwargs)
    return guarded_getaddrinfo


def install() -> None:
    """Patch the socket primitives. Idempotent; one guard per session."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    socket.socket.connect = _connect(socket.socket.connect)
    socket.socket.connect_ex = _connect_ex(socket.socket.connect_ex)
    socket.getaddrinfo = _getaddrinfo(socket.getaddrinfo)


def attempts_for(test: str) -> list[dict]:
    return [a for a in ATTEMPTS if a.get("test") == test]


def refused_for(test: str) -> list[dict]:
    return [a for a in attempts_for(test)
            if a["outcome"] == "refused-nonloopback"]


def summary() -> dict[str, int]:
    """Attempted connections, split by outcome — the session's evidence."""
    counts: dict[str, int] = {
        "attempts": len(ATTEMPTS),
        "refused_nonloopback": 0,
        "loopback_completed": 0,
        "loopback_failed": 0,
    }
    for entry in ATTEMPTS:
        if entry["outcome"] == "refused-nonloopback":
            counts["refused_nonloopback"] += 1
        elif entry["outcome"] == "loopback":
            counts["loopback_completed"] += 1
        elif entry["outcome"] == "loopback-error":
            counts["loopback_failed"] += 1
    return counts


def write_log(path: str) -> None:
    """The session's attempt log, one JSON record per line."""
    with open(path, "w", encoding="utf-8") as handle:
        for entry in ATTEMPTS:
            handle.write(json.dumps(entry) + "\n")
