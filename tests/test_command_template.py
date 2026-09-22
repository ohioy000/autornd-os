"""The command template stays valid, and its always-in-scope set stays true.

**What bought this.** Six commands ran through the channel on 2026-09-22 and six
logged a scope deviation for the same reason: the `include` list omitted a file
the command's own acceptance criteria forced the executor to write. None of them
was a judgement call — every one was arithmetic, because the generated-count
guards re-derive from disk and adding one test file turns four of them red.

**Why a test and not just a document.** The always-in-scope set is a claim about
*other files* — that `HANDOVER.md`, `README.md`, `AGENTS.md`, `CLAUDE.md` and
`.claude/context/testing.md` are the ones a count change reaches. That claim can
go stale silently: move a count into a sixth document and the template still
looks right while being wrong, which is exactly the drift convention 24 exists
to catch. So this checks the set against the files that actually state counts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / ".orchestration" / "COMMAND_TEMPLATE.json"
CHANNEL_README = ROOT / ".orchestration" / "README.md"

ALWAYS_IN_SCOPE = [
    ".orchestration/responses/",
    "HANDOVER.md",
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    ".claude/context/testing.md",
]

# Every document that states the suite size in prose. If a count moves into a
# file not listed here, the template's promise is no longer true and
# `test_every_document_that_states_a_count_is_in_scope` says so.
COUNT_BEARING = ["HANDOVER.md", "README.md", "AGENTS.md", "CLAUDE.md",
                 ".claude/context/testing.md"]


@pytest.fixture(scope="module")
def template() -> dict:
    assert TEMPLATE.is_file(), f"{TEMPLATE.relative_to(ROOT)} is missing"
    text = TEMPLATE.read_text(encoding="utf-8")
    assert text.strip(), "the template is empty"
    return json.loads(text)


class TestTheTemplateIsUsable:
    def test_it_is_valid_json(self, template):
        """A template that does not parse is worse than none — it is copied."""
        assert isinstance(template, dict)

    @pytest.mark.parametrize("field", [
        "command_id", "parent_id", "priority", "status", "objective",
        "evidence", "scope", "constraints", "acceptance_criteria",
        "verification", "rollback", "deliverable", "assumptions",
        "questions", "preconditions",
    ])
    def test_it_carries_every_field_the_channel_requires(self, template, field):
        assert field in template, (
            f"the template dropped {field!r} — a command copied from it would "
            f"arrive malformed, and a missing `preconditions` is a BLOCKED "
            f"arrival by the channel's own rule")

    def test_preconditions_is_non_empty(self, template):
        """An absent or empty preconditions array is a BLOCKED arrival."""
        assert template["preconditions"], (
            "the template ships an empty preconditions array, which is the one "
            "shape the channel rejects on arrival")

    def test_every_precondition_has_a_command_and_an_expected(self, template):
        for pre in template["preconditions"]:
            assert "command" in pre and "expected" in pre, pre

    def test_it_ships_the_suite_precondition(self, template):
        """Green before the change is the one precondition every command needs."""
        commands = " ".join(p["command"] for p in template["preconditions"])
        assert "pytest" in commands, commands


class TestTheAlwaysInScopeSetIsPresent:
    @pytest.mark.parametrize("path", ALWAYS_IN_SCOPE)
    def test_the_template_include_carries_it(self, template, path):
        include = template["scope"]["include"]
        assert path in include, (
            f"{path!r} left the template's default include. Six commands in one "
            f"day logged a deviation for exactly this; putting it back is "
            f"cheaper than logging a seventh")

    @pytest.mark.parametrize("path", ALWAYS_IN_SCOPE)
    def test_the_channel_readme_explains_it(self, path):
        assert path in CHANNEL_README.read_text(encoding="utf-8"), (
            f"{path!r} is in the template's include but the README no longer "
            f"says why — a default nobody can justify gets removed by the next "
            f"person who reads it")


class TestTheSetIsStillTrue:
    """The claim is about other files, so it is checked against them."""

    def test_every_document_that_states_a_count_is_in_scope(self):
        """A count in a sixth document would make the template quietly wrong."""
        stated = []
        for name in COUNT_BEARING:
            path = ROOT / name
            assert path.is_file(), f"{name} is missing — the set names a file that is gone"
            if re.search(r"\b\d{3,4}\s+tests?\b|tests-\d{3,4}%20passing",
                         path.read_text(encoding="utf-8")):
                stated.append(name)
        assert stated, (
            "no document in COUNT_BEARING states a test count any more — either "
            "the counts moved, or the format changed and this guard has stopped "
            "being able to find its subject (convention 28)")
        for name in stated:
            assert name in ALWAYS_IN_SCOPE, (
                f"{name} states a test count but is not in the always-in-scope "
                f"set, so a command that adds a test cannot legally fix it")

    def test_the_paths_in_the_set_exist(self):
        """A default include naming a path that is gone is noise in every command."""
        for path in ALWAYS_IN_SCOPE:
            target = ROOT / path.rstrip("/")
            assert target.exists(), f"{path} is in the set but not on disk"

    def test_the_readme_names_what_is_never_in_scope(self):
        """The exclusions are load-bearing and each cost something to learn."""
        text = CHANNEL_README.read_text(encoding="utf-8")
        for never in [".env", "evals/results/", "milkhouse"]:
            assert never in text, (
                f"the channel README no longer names {never!r} as out of scope")
