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

import pytest
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Read by users, so anonymous. HANDOVER.md and docs/ are deliberately absent.
#
# Shipped configuration counts too, and counts harder: a workflow file and a
# profile are copied and edited rather than read once, so a model id in one
# propagates into every fork of it. The policy calls this the strictest end of
# the rule — the closer a document sits to configuration, the less room there
# is for a vendor name.
USER_FACING = ["README.md", ".env.example", "AGENTS.md", "CLAUDE.md",
               "CONTRIBUTING.md", "CHANGELOG.md"]

SHIPPED_CONFIG = ["profiles/*.yaml", "workflows/*.yaml"]


def _scanned_paths(root):
    paths = [root / name for name in USER_FACING]
    for pattern in SHIPPED_CONFIG:
        paths.extend(sorted(root.glob(pattern)))
    return paths

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
        paths = _scanned_paths(ROOT)
        assert len(paths) > len(USER_FACING), "the config globs matched nothing"
        for path in paths:
            assert path.exists(), f"{path} is missing"
            name = path.relative_to(ROOT)
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


class TestTheReadmeYamlExcerptIsTheRealThing:
    """A hand-copied YAML excerpt drifts. This one is the third exhibit.

    HANDOVER §3.1 carried a hand-copied node table for twelve blueprints and
    was wrong about the loop by two exits when it was finally read; the fix
    there was to generate the table. The README's *Workflows Are Files*
    excerpt is the same shape of claim — real node ids, presented as the file
    — and it drifted the same way: it showed a five-node `build_loop` exiting
    on `validate.green` long after the fold and the block nodes landed.

    So it is compared rather than eyeballed. The excerpt may show a SUBSET of
    the file's nodes and of each node's fields — it is an illustration, and a
    short one is better — but every field it does show must equal the file.
    Drop a node from the excerpt and this says nothing about it; misquote one
    and it fails.
    """

    WORKFLOW = "workflows/engineering-rnd.yaml"

    @staticmethod
    def _excerpt() -> list[dict]:
        import yaml

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```yaml\n(.*?)```", readme, re.DOTALL)
        for block in blocks:
            if "id: build_loop" not in block:
                continue
            return yaml.safe_load(block)
        raise AssertionError(
            "the README no longer carries a yaml block naming build_loop — if "
            "the excerpt moved, move this guard with it rather than deleting it")

    def test_every_excerpted_field_matches_the_workflow_file(self):
        import yaml

        real = {n["id"]: n for n in
                yaml.safe_load((ROOT / self.WORKFLOW).read_text())["nodes"]}
        wrong = []
        for shown in self._excerpt():
            node = real.get(shown["id"])
            if node is None:
                wrong.append(f"{shown['id']}: not a node in {self.WORKFLOW}")
                continue
            for key, value in shown.items():
                if node.get(key) != value:
                    wrong.append(
                        f"{shown['id']}.{key}: README says {value!r}, "
                        f"the file says {node.get(key)!r}")
        assert not wrong, "; ".join(wrong)


class TestTheWorkflowComparisonTableIsTheRealThing:
    """The README's cheapest claim about the graph, re-derived rather than read.

    The table under *Workflows Are Files* says what two shapes cost against the
    same expectations. It said `11`/`24` and `8`/`15` while the harness it
    describes reported `10`/`17` and `7`/`14` — the engineering-rnd
    never-converges figure was out by seven, which is a whole rework loop. The
    provenance of the old numbers is recorded nowhere, so they could not be
    reconciled, only re-measured (convention 18: a reading is a reading).

    Re-derived here with the apparatus the README names — the same scripted
    client and settings as
    `test_evals.py::TestSuiteReports::test_the_same_suite_can_compare_two_workflows`,
    which is what "measured against each other with mocks, in under a second,
    for nothing" refers to. Deterministic: three consecutive runs agreed.

    A number in a document that no test derives is a number that drifts. This
    is the second such guard in this file and the fourth hand-copied fact in
    this repo to have gone stale.
    """

    @staticmethod
    async def _calls(workflow: str, *, green: bool) -> int:
        from tests.test_evals import SETTINGS, make_client, scripted
        from autornd.evals.runner import run_suite
        from autornd.evals.scenario import parse
        from autornd.graph.spec import load

        scenarios = [parse({"id": "s", "request": "Add retry",
                            "expect": {"status": "completed"}})]
        report = await run_suite(
            scenarios, load(f"workflows/{workflow}.yaml"),
            lambda: make_client(scripted(green=green)), SETTINGS)
        return report.calls

    @staticmethod
    def _table() -> dict[str, tuple[int, int]]:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        rows = re.findall(
            r"^\|\s*`(engineering-rnd|lean)`\s*\|\s*\*{0,2}(\d+) calls\*{0,2}\s*"
            r"\|\s*\*{0,2}(\d+) calls\*{0,2}\s*\|$",
            readme, re.MULTILINE)
        assert len(rows) == 2, (
            "the README's workflow comparison table is missing or reshaped — if "
            "it moved, move this guard with it rather than deleting it")
        return {name: (int(happy), int(never)) for name, happy, never in rows}

    @pytest.mark.asyncio
    async def test_both_rows_match_the_harness(self):
        claimed = self._table()
        wrong = []
        for workflow, (happy, never) in claimed.items():
            for label, stated, green in (("happy path", happy, True),
                                         ("never converges", never, False)):
                actual = await self._calls(workflow, green=green)
                if actual != stated:
                    wrong.append(f"{workflow} {label}: README says {stated}, "
                                 f"the harness reports {actual}")
        assert not wrong, "; ".join(wrong)

    @pytest.mark.asyncio
    async def test_lean_is_still_the_cheaper_shape_on_both_arms(self):
        """The table's actual argument, independent of the exact figures."""
        claimed = self._table()
        assert claimed["lean"][0] < claimed["engineering-rnd"][0]
        assert claimed["lean"][1] < claimed["engineering-rnd"][1]
