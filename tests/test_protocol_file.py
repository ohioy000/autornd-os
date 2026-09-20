"""The executor protocol is one file with two names, and it stays that way.

**Why this exists.** The protocol that produced fifteen blueprints lived in
chat transcripts. Blueprint 015 moved it into `AGENTS.md` — the cross-tool
convention — with `CLAUDE.md` as a symlink so the tool-specific name keeps
working. **Two copies would drift**, which is convention 24's whole subject: a
hand-maintained duplicate of anything in this repo has been wrong within two
blueprints, every time it has been tried.

So the symlink is pinned. If someone replaces it with a copy "to be safe", this
fails and says why. And the protocol's load-bearing parts are pinned by name,
because a protocol file that quietly loses its permission boundary is worse than
no protocol file: the boundary is the thing a new executor does not know.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
CLAUDE = ROOT / "CLAUDE.md"


def test_the_protocol_file_exists():
    assert AGENTS.is_file(), "AGENTS.md is the protocol file; it is missing"


def test_claude_md_is_a_symlink_to_it_not_a_copy():
    """A copy drifts. This repo has twelve documented drifts to prove it."""
    assert CLAUDE.is_symlink(), (
        "CLAUDE.md must be a symlink to AGENTS.md, not a copy — two copies of "
        "the protocol drift, and convention 24 exists because of exactly that"
    )
    assert CLAUDE.resolve() == AGENTS.resolve()


def test_both_names_give_the_same_protocol():
    assert CLAUDE.read_text(encoding="utf-8") == AGENTS.read_text(encoding="utf-8")


@pytest.mark.parametrize("must_carry", [
    # the boundary a new executor cannot infer from the code
    "permission boundary",
    "instrument repair",
    # who may do what
    "advisor",
    "executor",
    "owner",
    # the gates the owner owns
    "G-1",
    "G-2",
    "G-3",
    # the orientation targets
    "HANDOVER.md",
    "docs/handover-review.md",
    "docs/successor-prompt.md",
])
def test_the_protocol_keeps_its_load_bearing_parts(must_carry):
    assert must_carry in AGENTS.read_text(encoding="utf-8"), (
        f"AGENTS.md no longer mentions {must_carry!r} — a protocol file that "
        f"loses this is worse than none, because it reads as complete")


def test_the_convention_digest_covers_17_to_24():
    """§4.4 has 25 conventions; a new executor trips over these eight."""
    text = AGENTS.read_text(encoding="utf-8")
    missing = [n for n in range(17, 25) if f"**{n}**" not in text]
    assert not missing, f"the convention digest is missing {missing}"


def test_the_successor_prompt_exists_and_is_referenced():
    prompt = ROOT / "docs" / "successor-prompt.md"
    assert prompt.is_file(), "docs/successor-prompt.md is missing"
    assert "successor-prompt.md" in AGENTS.read_text(encoding="utf-8")


def test_the_orchestration_channel_is_documented():
    """A protocol that lives only in chat is the failure mode the notebook
    warns about — and a guard that does not name both directories would pass
    on a section that documented only half the channel (convention 22)."""
    text = AGENTS.read_text(encoding="utf-8")
    for path in (".orchestration/commands/", ".orchestration/responses/"):
        assert path in text, f"AGENTS.md no longer documents {path}"


def test_the_channel_requires_checkable_evidence():
    """A command citing a sha, path or figure must be verifiable before it acts.

    Written after a command cited an entire paid run that had never happened.
    Asserts the rule and its exhibit, not the heading — a section that kept the
    heading and lost the rule would otherwise pass (convention 22)."""
    text = AGENTS.read_text(encoding="utf-8")
    for phrase in ("verify", "is not evidence",
                   "ARCH-20260921-002.response.json"):
        assert phrase in text, f"the checkable-evidence precondition lost {phrase!r}"
