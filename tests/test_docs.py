"""Free guards on the documents a user reads.

Two failure classes have each happened more than once and neither is visible to
any other test, because both live in prose rather than in code.

**Model names in user-facing docs.** Selection is anonymous; the record is not.
No model id belongs in code, configuration defaults, profiles, workflow files or
any user-facing passage that recommends or defaults to a model. It has leaked
three times: a model-routing table in an earlier CLAUDE.md, a model nickname in
the changelog, and a named search model in the README and `.env.example`.

`HANDOVER.md` and everything under `docs/` are **exempt by policy**, not by
oversight. They are the lab notebook: §6 records what was measured and naming
the subject of a measurement is the whole point of a record. The rule tightens
the closer a document sits to configuration.

**A test count that drifts.** The README badge said 339 while the suite was 501.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Read by users, so anonymous. HANDOVER.md and docs/ are deliberately absent.
USER_FACING = ["README.md", ".env.example", "CLAUDE.md",
               "CONTRIBUTING.md", "CHANGELOG.md"]

# The families that have actually leaked, plus the vendor prefixes an id uses.
MODEL_NAMES = re.compile(
    r"glm|deepseek|minimax|sonar|perplexity|gemini|kimi|qwen|gpt-|mistral"
    r"|llama|claude|openai|anthropic|moonshot|z-ai",
    re.IGNORECASE,
)

# Not selections. "OpenAI chat-completions" is the wire protocol's industry
# name and there is no vendor-neutral synonym for it; the others are this
# repo's own filenames and tooling.
ALLOWED = [
    "OpenAI-compatible",
    "OpenAI chat-completions",
    "CLAUDE.md",
    "Claude Code",
]


def _offending_lines(text: str) -> list[tuple[int, str]]:
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line
        for allowed in ALLOWED:
            stripped = stripped.replace(allowed, "")
        if MODEL_NAMES.search(stripped):
            hits.append((n, line.strip()))
    return hits


class TestNoModelNamesInUserFacingDocs:
    def test_every_user_facing_doc_is_anonymous(self):
        found: list[str] = []
        for name in USER_FACING:
            path = ROOT / name
            assert path.exists(), f"{name} is missing"
            for n, line in _offending_lines(path.read_text(encoding="utf-8")):
                found.append(f"{name}:{n}: {line}")
        assert not found, (
            "model ids in user-facing documentation — keep the measurement, "
            "anonymize the subject, and put the named version in HANDOVER.md "
            "§6 or docs/handover-review.md:\n  " + "\n  ".join(found)
        )

    def test_the_guard_would_actually_catch_one(self):
        """A guard nobody has seen fail is a guard nobody knows works."""
        assert _offending_lines("we run deepseek-v4 on triage")
        assert not _offending_lines("any OpenAI-compatible endpoint works")


class TestReadmeBadgeMatchesTheSuite:
    """The badge is a claim about this repo, so it is checked like one.

    Collection is run in a subprocess rather than read off the current session,
    because the session count is wrong whenever anyone runs a subset — which is
    most of the time while developing.
    """

    def test_badge_count_matches_collected_tests(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        badge = re.search(r"tests-(\d+)%20passing", readme)
        assert badge, "the README tests badge is missing or has changed shape"

        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
            cwd=ROOT, capture_output=True, text=True,
        )
        collected = re.search(r"(\d+) tests? collected", proc.stdout)
        assert collected, f"could not read a collected count:\n{proc.stdout[-500:]}"

        assert int(badge.group(1)) == int(collected.group(1)), (
            f"README badge says {badge.group(1)} tests, collection found "
            f"{collected.group(1)}. Update the badge, the Testing section and "
            f"the Project Structure comment together — they drifted to 339 "
            f"against a real 501 once already."
        )
