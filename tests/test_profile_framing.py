"""Profile-framing tests for Ruling D54: the team is the profile's.

Engineering is unchanged: under the engineering profile, and under every
profile built on it, each prompt renders byte-identical to the golden copy
captured from main before D54. Nothing engineering reaches a model under a
profile that is not engineering. The team words, the triage lists and the
two structural roles all come from the active profile.
"""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

import pytest

from autornd.config import settings
from autornd.engine import phases
from autornd.engine.phases import enforce_triage_composition
from autornd.knowledge.context import reset_rerank_mode
from autornd.models.verdicts import Domain, RiskLevel, SpecialistRole, TriageVerdict, role_key
from autornd.specialists.registry import get_specialist
from tests.prompt_capture import NEUTRAL_SEATS, SITE_FUNCTIONS, capture_all


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "prompts"
PROFILES = ("engineering", "example", "cupline", "tier4")
WRITE_GOLDEN = os.environ.get("WRITE_GOLDEN") == "1"
ROOT = Path(__file__).resolve().parent.parent
SCAN = re.compile(r"engineer|firmware|hardware|backend|frontend|datasheet|pasteuris|EIRP", re.I)


def _use(name: str) -> None:
    from autornd.profiles import load_profile, set_profile
    from autornd.specialists.registry import reload_specialists

    set_profile(load_profile(name))
    reload_specialists()


async def _capture_for(name: str, monkeypatch, seats=None) -> dict[str, dict[str, str]]:
    monkeypatch.setattr(settings, "model_research", "test-provider/test-research")
    monkeypatch.setattr(settings, "model_ranker", "test-provider/test-rank")
    reset_rerank_mode()
    _use(name)
    return await capture_all(seats)


def _leaks(captured: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for site, messages in captured.items():
        for part in ("system", "user"):
            found = sorted({m.lower() for m in SCAN.findall(messages[part])})
            if found:
                hits[f"{site}.{part}"] = found
    return hits


async def test_write_golden_fixture(monkeypatch) -> None:
    """WRITE_GOLDEN=1 writes the four fixtures, one per profile."""
    if not WRITE_GOLDEN:
        pytest.skip("WRITE_GOLDEN is not set")
    for name in PROFILES:
        captured = await _capture_for(name, monkeypatch)
        text = json.dumps(captured, indent=1, ensure_ascii=False, sort_keys=True)
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        (FIXTURE_DIR / f"{name}.json").write_text(text, encoding="utf-8")


class TestEngineeringIsUnchanged:
    async def test_engineering_prompts_are_byte_identical(self, monkeypatch):
        """Every prompt, under engineering and the three profiles built on it,
        equals the copy captured from main's code before D54."""
        for name in PROFILES:
            want = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
            got = await _capture_for(name, monkeypatch)
            changed = sorted(k for k in set(want) | set(got) if want.get(k) != got.get(k))
            assert not changed, f"{name}: these prompts changed: {changed}"


class TestNothingEngineeringLeaks:
    async def test_no_engineering_word_reaches_a_model_under_general(self, monkeypatch):
        hits = _leaks(await _capture_for("general", monkeypatch, NEUTRAL_SEATS))
        assert not hits, f"engineering words under general: {hits}"

    async def test_no_engineering_word_reaches_a_model_under_studio(self, monkeypatch):
        hits = _leaks(await _capture_for("studio", monkeypatch, NEUTRAL_SEATS))
        assert not hits, f"engineering words under studio: {hits}"

    def test_every_model_call_site_is_captured(self):
        """A model call the capture does not cover is a prompt the leak scans never read."""
        excluded = {("routing/openrouter.py", "chat_json"), ("specialists/base.py", "run")}
        found: set[str] = set()
        for path in sorted((ROOT / "autornd").rglob("*.py")):
            rel = path.relative_to(ROOT / "autornd").as_posix()

            def visit(node: ast.AST, outer: str | None) -> None:
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        visit(child, outer or child.name)
                        continue
                    if (isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
                            and outer and (rel, outer) not in excluded):
                        name = child.func.attr
                        first = child.args[0] if child.args else None
                        if name in ("chat_json", "chat") or (
                                name == "run" and isinstance(first, ast.Name)
                                and first.id == "client"):
                            found.add(outer)
                    visit(child, outer)

            visit(ast.parse(path.read_text(encoding="utf-8")), None)
        assert found == set(SITE_FUNCTIONS)


class TestTheProfileOwnsTheTeam:
    async def test_triage_is_offered_the_profiles_own_list(self, monkeypatch):
        shipped_domains = {d.value for d in Domain}
        shipped_roles = {r.value for r in SpecialistRole}

        _use("studio")
        domains = phases._domain_vocabulary().split(", ")
        roles = phases._role_vocabulary().split(", ")
        assert domains == ["brand_strategy", "copywriting", "seo_analytics"]
        assert roles == ["strategist", "copywriter", "editor", "fact_checker", "seo_analyst"]
        assert not set(domains) & shipped_domains
        assert not set(roles) & shipped_roles

        triage = (await _capture_for("general", monkeypatch, NEUTRAL_SEATS))["triage"]["user"]
        assert "Name each domain yourself" in triage
        assert "Prefer these:\n  lead, reviewer, planner." in triage
        assert "Prefer these: firmware" not in triage

    async def test_structural_roles_follow_the_profile(self, monkeypatch):
        for name, checker, viewer in (("studio", "editor", "strategist"),
                                      ("general", "reviewer", "planner")):
            captured = await _capture_for(name, monkeypatch, NEUTRAL_SEATS)

            high = TriageVerdict(domains=["subject_area"], risk=RiskLevel.HIGH,
                                 specialists=["lead"], summary="s")
            enforce_triage_composition(high)
            assert checker in [role_key(s) for s in high.specialists], name

            wide = TriageVerdict(domains=["subject_area", "other_area"], risk=RiskLevel.LOW,
                                 specialists=["lead"], summary="s")
            enforce_triage_composition(wide)
            assert viewer in [role_key(s) for s in wide.specialists], name

            assert captured["plan"]["system"] == get_specialist(viewer).system_prompt, name
            assert captured["validate"]["system"] == get_specialist(checker).system_prompt, name

    def test_no_shipped_role_or_domain_literal_in_code(self):
        literal = re.compile(r"SpecialistRole\.[A-Z]|Domain\.[A-Z]")
        found = []
        for path in sorted((ROOT / "autornd").rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel == "autornd/models/verdicts.py":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if literal.search(line):
                    found.append(f"{rel}:{number}")
        assert not found, f"shipped engineering literals in code: {found}"


class TestDefaultAndBase:
    def test_default_is_general(self, monkeypatch):
        from autornd.profiles import get_profile, reset_profile

        monkeypatch.setattr(settings, "autornd_profile", "")
        reset_profile()
        assert get_profile().frame("team") == "a team"
        assert get_profile().role_that_checks_work() == "reviewer"

    def test_base_lays_own_keys_over_the_base(self):
        from autornd.profiles import load_profile

        engineering = load_profile("engineering")
        example = load_profile("example")
        assert list(example.domains) == list(engineering.domains) + ["field_service"]
        assert "field_technician" in example.roles
        assert example.framing == engineering.framing

    def test_a_base_with_a_base_is_refused(self, tmp_path, monkeypatch):
        from autornd import profiles

        (tmp_path / "top.yaml").write_text('name: "Top"\nbase: middle\n', encoding="utf-8")
        (tmp_path / "middle.yaml").write_text('name: "Middle"\nbase: bottom\n', encoding="utf-8")
        monkeypatch.setattr(profiles, "PROFILES_DIR", tmp_path)
        with pytest.raises(ValueError) as refused:
            profiles.load_profile("top")
        assert "Top" in str(refused.value) and "middle" in str(refused.value)
