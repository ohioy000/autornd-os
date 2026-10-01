"""Response files are single JSON objects with an allowed status.

**What bought this.** ARCH-20260930-094's response shipped with its status
appended twice — one `json.dumps` of a dict followed by a hand-written
`,"status":"DONE"}` tail — so the file held two concatenated fragments and
`json.loads` failed with `Extra data`. Every reader that loads a response
would have choked on it, and the channel's own rule (a command with no
response file has not been executed) says nothing about a response file
that will not parse.

**The guard.** Every file in `.orchestration/responses/` must parse as one
JSON object whose `status` is in the channel's vocabulary. The vocabulary
is the one the protocol states: IN_PROGRESS, DONE, PARTIAL, BLOCKED,
FAILED, REJECTED, NO_ACTION.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESPONSES = ROOT / ".orchestration" / "responses"

ALLOWED = {"IN_PROGRESS", "DONE", "PARTIAL",
           "BLOCKED", "FAILED", "REJECTED", "NO_ACTION"}


def _response_files() -> list[Path]:
    assert RESPONSES.is_dir(), ".orchestration/responses/ is missing"
    files = sorted(RESPONSES.glob("*.response.json"))
    assert files, "no response files — the guard has no subject (convention 28)"
    return files


class TestEveryResponseParses:
    def test_every_response_file_is_one_object_with_an_allowed_status(self):
        """A response that will not parse is not a response (convention 28).

        Parses each file with json.loads (which rejects trailing data) and
        checks the single object's status against the channel vocabulary.
        """
        bad: list[str] = []
        for path in _response_files():
            try:
                obj = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                bad.append(f"{path.name}: will not parse ({e})")
                continue
            if not isinstance(obj, dict) or obj.get("status") not in ALLOWED:
                bad.append(f"{path.name}: status {obj.get('status')!r} "
                           f"not in {sorted(ALLOWED)}")
        assert not bad, ("response files that are not single objects with an "
                         "allowed status:\n" + "\n".join(bad))

    def test_trailing_data_after_the_object_breaks_this_guard(self, tmp_path):
        """Convention 22: prove by breaking. A file with a hand-appended
        status tail — the exact shape 094 shipped — must fail the parse."""
        import json as _json
        broken = tmp_path / "ARCH-20260930-000.response.json"
        broken.write_text(_json.dumps({"status": "IN_PROGRESS"})
                          + ',"status":"DONE"}', encoding="utf-8")
        with pytest.raises(_json.JSONDecodeError):
            _json.loads(broken.read_text(encoding="utf-8"))
