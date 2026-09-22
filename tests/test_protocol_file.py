"""The executor protocol is ONE file, and no second copy of it exists.

**Why this exists.** The protocol that produced fifteen blueprints lived in
chat transcripts. Blueprint 015 moved it into `AGENTS.md` — the cross-tool
convention. **Two copies would drift**, which is convention 24's whole subject:
a hand-maintained duplicate of anything in this repo has been wrong within two
blueprints, every time it has been tried.

**Amended 2026-09-22 (owner-ruled).** `CLAUDE.md` was a symlink to `AGENTS.md`
so the tool-specific name resolved to the same bytes, and this file pinned the
symlink. The owner has since made `CLAUDE.md` the repo's *derived working rules*
— naming conventions, code patterns, validation commands, an on-demand context
table — which is a different document with a different job. The symlink
assertion is therefore gone.

**What replaces it is a stronger guard, not a weaker one.** The symlink pinned a
mechanism; convention 24's actual subject is the property, which is that exactly
one copy of the protocol exists. So this now scans the tree for a duplicate by
content. That catches the case the symlink assertion could not: a copy under
some *other* name. It is not hypothetical — a byte-identical copy at
`thisisnottheCLAUDE.md` sat untracked in this repo on the day of this amendment,
and the symlink assertion said nothing about it, because it was only ever
looking at one path (convention 28: a guard must be able to find its subject).

The protocol's load-bearing parts stay pinned by name, because a protocol file
that quietly loses its permission boundary is worse than no protocol file: the
boundary is the thing a new executor does not know.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
CLAUDE = ROOT / "CLAUDE.md"


def test_the_protocol_file_exists():
    assert AGENTS.is_file(), "AGENTS.md is the protocol file; it is missing"


# Where a duplicate would plausibly be dropped. Not the whole tree: docs/ is the
# lab notebook and quotes the protocol at length by design, and .git/ holds every
# historical version of it.
_DUPLICATE_SEARCH = ["*.md", ".claude/*.md", ".claude/*/*.md"]

# Enough of the protocol's own prose to identify a copy, short enough to survive
# ordinary edits to it. Both lines are structural rather than incidental.
_FINGERPRINT = [
    "**This file is the protocol.**",
    "A new executor proposes; it does not rule.",
]


def test_the_protocol_has_exactly_one_copy():
    """A copy drifts. This repo has twelve documented drifts to prove it.

    Searches by CONTENT rather than by path, because the duplicate this guard
    exists to catch appeared under a name nobody predicted.
    """
    protocol = AGENTS.read_text(encoding="utf-8")
    for line in _FINGERPRINT:
        assert line in protocol, (
            f"the fingerprint {line!r} is no longer in AGENTS.md, so this guard "
            f"can no longer recognise a copy of the protocol — fix the "
            f"fingerprint, do not delete the check (convention 28)")

    candidates = []
    for pattern in _DUPLICATE_SEARCH:
        candidates.extend(ROOT.glob(pattern))
    assert candidates, "the duplicate scan matched no files at all"

    copies = []
    for path in sorted(set(candidates)):
        if path.resolve() == AGENTS.resolve() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if all(line in text for line in _FINGERPRINT):
            copies.append(str(path.relative_to(ROOT)))

    assert not copies, (
        f"a second copy of the protocol exists at {copies} — two copies drift, "
        f"and convention 24 exists because of exactly that. AGENTS.md is the "
        f"one copy; point at it rather than duplicating it")


def test_claude_md_is_the_derived_rules_not_the_protocol():
    """CLAUDE.md is this repo's working rules, and says where the protocol is.

    Owner-ruled 2026-09-22. The two documents have different jobs and must not
    be merged back together: the protocol is about who may decide what, and the
    rules are about how this codebase is written.
    """
    assert CLAUDE.is_file(), "CLAUDE.md is missing"
    text = CLAUDE.read_text(encoding="utf-8")
    assert text != AGENTS.read_text(encoding="utf-8"), (
        "CLAUDE.md has become a copy of the protocol again")
    assert "AGENTS.md" in text, (
        "CLAUDE.md must point at AGENTS.md — a new agent reads CLAUDE.md first "
        "and would otherwise never learn the protocol exists")


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


def test_the_command_shape_carries_preconditions():
    """The checkable-evidence rule, made structural rather than stated.

    Asserts the field, the MUST, and that a failure is BLOCKED rather than a
    deviation — the three parts that make it a mechanism instead of advice. A
    section keeping the word `preconditions` while losing the obligation would
    otherwise pass (convention 22)."""
    text = AGENTS.read_text(encoding="utf-8")
    for phrase in ("preconditions", "MUST carry one verifying it",
                   "`BLOCKED` report, not a"):
        assert phrase in text, f"the preconditions schema lost {phrase!r}"


def test_the_executor_checks_commands_on_arrival():
    """Stated, then structural, then enforced — this is the third step.

    Two duties: a non-null parent must already have a response, and every
    command must carry a non-empty preconditions array. Asserts both MUSTs and
    the BLOCKED semantics, because a section keeping the prose while softening
    either obligation is the degradation that actually happens (convention 22).
    The exhibit is real: 010 executed with 009's response missing, undetected
    until the advisor read the directory."""
    text = AGENTS.read_text(encoding="utf-8")
    for phrase in ("On arrival", "a response file for that parent", "**MUST**",
                   "non-empty `preconditions` array", "report on arrival"):
        assert phrase in text, f"the arrival checks lost {phrase!r}"
