"""The tier-3 experiment manifest is a frozen plan, and a frozen plan
is checked like a frozen dataset (ARCH-20261002-118; the runner
registered by ARCH-20261003-119, manifest tier3-2).

The manifest (evals/tier3/manifest.json) registers the five-arm
experiment over the frozen tier-2 question set: the plan arithmetic,
the arm treatments, the serving pins (environment names, never model
ids - non-negotiable 6), the ceilings, the execution rules, the
failure treatment, the success measures and the two ratification
gates that stop paid execution. This file checks every registered
invariant holds on the tree, that the checks can fail (the seeded
order is re-derived, and a different seed must NOT reproduce it),
and that nothing the models must not see - key material, model ids -
leaked into any tier-3 file. The prompts are checked structurally:
arm D's prompt is arm A's byte-for-byte (the same request, only the
serving differs), and arm B's is arm A's with exactly two
registered differences - the first paragraph and the tool
registration - so that replacing the first and removing the tools
reconstructs arm A exactly (equal information access: the question,
the deadline and the answer format are identical).
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TIER3 = ROOT / "evals" / "tier3"
TIER2 = ROOT / "evals" / "tier2"
MANIFEST = json.loads((TIER3 / "manifest.json").read_text(encoding="utf-8"))
TIER2_MANIFEST = json.loads((TIER2 / "manifest.json").read_text(encoding="utf-8"))
TIER2_VERSIONS = json.loads((TIER2 / "versions.json").read_text(encoding="utf-8"))
QUESTIONS = json.loads((TIER2 / "questions.json").read_text(encoding="utf-8"))
KEYS = json.loads((TIER2 / "keys.json").read_text(encoding="utf-8"))
ARMS = ("A", "B", "C", "D", "E")
PROMPTS = TIER3 / "prompts"


def _tier3_files() -> list[Path]:
    files = [TIER3 / "manifest.json", TIER3 / "README.md",
             TIER3 / "runner.py"]
    files.extend(sorted(PROMPTS.glob("*.md")))
    return files


def _key_strings() -> list[str]:
    """Every string keys.json holds that an answer could leak.

    Four key strings are shorter than 12 characters and are scorer
    vocabulary or a bare disjunct ("PASS", "FAIL", "OR") - a probe
    would match ordinary prose and prove nothing (the tier-2 lesson:
    a probe that a question itself answers is a false positive, not
    a leak test). The distinctive short selections stay probed.
    """
    probes = [q["model_answer"] for q in KEYS]
    for q in KEYS:
        probes.extend(it["value"] for it in q["required_items"])
        probes.extend(w["answer"] for w in q["common_wrong_answers"])
    distinctive = {"XNOR", "$0,1,1,0$", "$I=hb^3/12$"}
    return [p for p in probes if len(p) >= 12 or p in distinctive]


class TestThePlan:
    def test_the_plan_arithmetic_holds(self):
        plan = MANIFEST["plan"]
        assert plan["stage"].startswith("stage 1")
        assert plan["questions"] == 7
        assert plan["repetitions_per_question"] == 3
        assert plan["arms"] == 5
        assert plan["planned_question_runs"] == 7 * 3 * 5 == 105
        assert plan["planned_units_per_arm"] == 21
        assert "questions.json" in plan["question_source"]

    def test_the_questions_are_the_frozen_set(self):
        ids = [q["id"] for q in QUESTIONS]
        assert ids == [f"Q{i}" for i in range(1, 26)], (
            "the frozen tier-2 set is not the 25-question set the "
            "experiment plans over - the manifest's question_source "
            "names a different dataset than the tree holds")
        # The stage-1 plan runs seven of the frozen set's
        # questions, and every one of them is a member of
        # the frozen set the tree holds.
        selection = MANIFEST["plan"]["question_selection"]
        assert len(selection["selected"]) == 7
        assert set(selection["selected"]) <= set(ids)
        assert MANIFEST["plan"]["questions"] == len(
            selection["selected"])

    def test_the_arms_carry_their_registered_treatments(self):
        arms = MANIFEST["arms"]
        # The registered call limits and tool budgets are the treatment.
        assert arms["A"]["call_limit"] == 1 and arms["A"]["tool_invocations"] == 0
        assert arms["B"]["call_limit"] == 3 and arms["B"]["tool_invocations"] == 20
        assert set(arms["B"]["tools"]) == {"fetch_primary_source", "recompute"}
        assert arms["C"]["call_limit"] == 3 and arms["C"]["tool_invocations"] == 0
        assert arms["D"]["call_limit"] == 1 and arms["D"]["tool_invocations"] == 0
        assert arms["E"]["call_limit"] == 40

    def test_the_serving_pins_are_named_not_models(self):
        arms = MANIFEST["arms"]
        assert arms["A"]["model_pin_env"] == "TIER3_ARM_A"
        assert arms["B"]["model_pin_env"] == "TIER3_ARM_B"
        assert arms["C"]["model_pin_env"] == ["TIER3_ARM_C_1", "TIER3_ARM_C_2"]
        assert arms["D"]["model_pin_env"] == "TIER3_ARM_D"
        assert "standing pins" in arms["E"]["model_pin_env"]
        # Arm B isolates the tool treatment, so its pin must resolve to
        # arm A's serving - the manifest registers the equality, and the
        # ratification gate repeats it as a requirement on the owner.
        assert "same" in arms["B"]["model_selection_criterion"].lower()
        # The gate is mechanized on a fingerprint of the
        # resolved servings map, and arm B's pin must equal
        # arm A's when resolved.
        gate_1 = MANIFEST["ratification_gates"]["gate_1_servings"]
        assert "TIER3_ARM_B equals TIER3_ARM_A" in gate_1
        assert "TIER3_SERVINGS_RATIFIED" in gate_1
        assert "fingerprint" in gate_1


class TestTheStage1Selection:
    """The selection rule, fixed by rule before any run
    (the owner's 2026-10-05 directive, specification 1):
    from Q6-Q25 only, one question per shape, then two
    more from two different shapes, all by
    random.Random(seed). The guard reconstructs the
    selection from the rule and the seed independently of
    the runner's own implementation, and fails under a
    different seed."""

    def _reconstruct(self, seed: int) -> list[str]:
        """The rule, rebuilt here from the manifest's own
        text - not from the runner's code."""
        candidates = [q for q in QUESTIONS
                      if 6 <= int(q["id"][1:]) <= 25]
        by_shape: dict[str, list[str]] = {}
        for question in candidates:
            by_shape.setdefault(question["shape"], []).append(
                question["id"])
        rng = random.Random(seed)
        selected = [rng.choice(pool) for pool in by_shape.values()]
        for shape in rng.sample(list(by_shape), 2):
            taken = set(selected)
            remaining = [q for q in by_shape[shape]
                         if q not in taken]
            selected.append(rng.choice(remaining))
        frozen_order = [q["id"] for q in QUESTIONS]
        return sorted(selected, key=frozen_order.index)

    def test_the_selection_is_the_rule_executed(self):
        selection = MANIFEST["plan"]["question_selection"]
        seed = selection["seed"]
        assert seed == 20261005
        reconstructed = self._reconstruct(seed)
        assert reconstructed == selection["selected"], (
            "the manifest's recorded selection is not the "
            "selection rule executed with the recorded seed - "
            "the rule, the seed and the ids must agree before "
            "any paid unit")
        # And the runner's own constant is the same seven.
        from evals.tier3 import runner
        assert list(runner.STAGE1_QUESTION_IDS) == reconstructed
        assert [q["id"] for q in runner.stage1_questions()] == (
            reconstructed)

    def test_the_selection_fails_under_a_different_seed(self):
        """The seed is load-bearing: a different seed must
        not reconstruct the recorded selection, or the
        guard proves nothing."""
        selection = MANIFEST["plan"]["question_selection"]
        other = self._reconstruct(selection["seed"] + 1)
        assert other != selection["selected"]

    def test_the_selection_covers_the_shapes_the_rule_requires(self):
        selection = MANIFEST["plan"]["question_selection"]
        shapes = selection["selected_shapes"]
        assert set(shapes.values()) == {
            "SANITY", "LOOKUP", "DERIVATION", "SPECIFICATION",
            "PROCEDURE"}, (
            "the rule takes one question per shape - the "
            "selection must cover all five shapes")
        counts: dict[str, int] = {}
        for shape in shapes.values():
            counts[shape] = counts.get(shape, 0) + 1
        assert sorted(counts.values()) == [1, 1, 1, 2, 2], (
            "the rule takes one per shape then two more from "
            "two different shapes - exactly two shapes "
            "contribute a second question")
        # Every selected question is from Q6-Q25: Q1-Q5 are
        # calibration-exposed and reserved for stage 2.
        for question_id in selection["selected"]:
            assert 6 <= int(question_id[1:]) <= 25, (
                f"{question_id} is not from Q6-Q25 - the rule "
                "draws from Q6-Q25 only")

    def test_the_stage_2_remainder_is_the_rest_of_the_set(self):
        selection = MANIFEST["plan"]["question_selection"]
        remainder = selection["stage_2_remainder"]
        # The remaining 18: Q1-Q5 (calibration-exposed)
        # plus the 13 Q6-Q25 questions not selected.
        expected = [f"Q{i}" for i in range(1, 6)]
        expected += [f"Q{i}" for i in range(6, 26)
                     if f"Q{i}" not in selection["selected"]]
        assert len(expected) == 18
        assert sorted(remainder) == sorted(expected), (
            "the registered stage-2 remainder is not the rest "
            "of the frozen set - stage 2 runs the questions the "
            "selection did not take, Q1-Q5 included, and nothing "
            "else")


class TestTheMoney:
    def test_the_ceiling_arithmetic_holds(self):
        ceilings = {a: MANIFEST["arms"][a]["spend_ceiling_per_question_run"]
                    for a in ARMS}
        assert ceilings == {"A": 0.10, "B": 0.50, "C": 0.50, "D": 0.20, "E": 0.50}
        per_unit_total = sum(ceilings.values())
        assert per_unit_total == pytest.approx(1.80)
        # The stage-1 compositional ceiling: 21 units
        # per arm at the per-unit ceilings. The owner's
        # ratified amount ($30.00, authorized 2026-10-05)
        # is below the compositional ceiling, and the
        # ratification gate carries both.
        compositional = (MANIFEST["plan"]["planned_units_per_arm"]
                         * per_unit_total)
        assert compositional == pytest.approx(37.80)
        gate_2 = MANIFEST["ratification_gates"]["gate_2_spend"]
        assert "$30.00" in gate_2 and "$37.80" in gate_2


class TestTheVersions:
    def test_the_versions_name_the_frozen_tier2_set(self):
        versions = MANIFEST["versions"]
        assert versions["dataset"] == "frozen-2026-10-03"
        assert versions["scorer"] == "frozen-2026-10-03.2"
        frozen = {v["version"] for v in TIER2_VERSIONS["versions"]}
        assert versions["dataset"] in frozen, (
            "the manifest names a tier-2 version the version record "
            "does not hold")
        # The scorer repair is a NEW version under the freeze
        # (Ruling D50 (1)): the version record holds it, and
        # it is the version the runner scores with.
        assert versions["scorer"] in frozen, (
            "the manifest names a scorer version the version "
            "record does not hold")
        assert versions["manifest"] == "tier3-6"
        # tier3-5 registers the advisor's R2 (the stage-1
        # report's repair list, 2026-10-06): arm B's final
        # call keeps the tools declared with tool_choice
        # "none", and an empty reply with finish "error" is
        # its own failure class, serving_error.
        # tier3-6 registers the advisor's R6 (the same
        # list, 2026-10-06): the experiment's pins are
        # read from .env.tier3, not .env - the harness's
        # settings forbid unknown keys, so a TIER3_* line
        # in .env stops the harness at startup.
        note = versions["version_note"]
        assert "tier3-5" in note
        assert 'tool_choice "none"' in note
        assert "serving_error" in note
        assert "tier3-6" in note
        assert ".env.tier3" in note
        # The tier-2 freeze itself: the signoff the owner ratified.
        assert TIER2_MANIFEST["dataset_version"] == "frozen-2026-10-03"
        assert TIER2_MANIFEST["frozen"] is True
        assert TIER2_MANIFEST["freeze"]["signed_off_by"] == "owner"


class TestThePrompts:
    def test_all_five_prompts_exist(self):
        for arm in ARMS:
            # The D and E prompt fields carry a parenthetical note
            # after the path; the file is the first token.
            declared = MANIFEST["arms"][arm]["prompt"].split()[0]
            assert declared.startswith("prompts/"), declared
            assert (TIER3 / declared).exists(), (
                f"arm {arm} declares {declared}, which is not in the tree")

    def test_arm_d_prompt_is_arm_a_prompt_verbatim(self):
        a = (PROMPTS / "arm_a.md").read_bytes()
        d = (PROMPTS / "arm_d.md").read_bytes()
        assert a == d, (
            "arm D's prompt is not arm A's prompt byte-for-byte - the "
            "strong-reference arm must pose the identical request so the "
            "A-vs-D gap is a serving gap, not a prompt gap")

    def test_arm_b_prompt_is_arm_a_prompt_plus_the_tool_registration(self):
        a = (PROMPTS / "arm_a.md").read_text(encoding="utf-8")
        b = (PROMPTS / "arm_b.md").read_text(encoding="utf-8")
        # D50 (2): arm B's prompt adds only the tools. The
        # reconstruction is mechanical: replace arm B's
        # intro paragraph with arm A's and remove the tool
        # section (from the TOOLS heading to just before
        # the closing "Answer now."), and arm A is
        # recovered exactly.
        # The old test asserted arm A's full text was
        # contained in arm B's; the earlier draft kept arm
        # A's "no tools are available" paragraph while
        # registering tools - self-contradictory, and the
        # old test enforced the contradiction. Rule 17:
        # the test was the bug.
        a_blocks = a.split("\n\n")
        b_blocks = b.split("\n\n")
        # The title is shared; the intro paragraph is the
        # first difference.
        diff = next(i for i, (x, y) in
                    enumerate(zip(a_blocks, b_blocks)) if x != y)
        assert diff > 0, "the prompts' titles differ"
        rest_blocks = list(b_blocks)
        rest_blocks[diff] = a_blocks[diff]
        rest = "\n\n".join(rest_blocks)
        tools_start = rest.index("## TOOLS (registered for this run)")
        answer_now = rest.rindex("Answer now.")
        reconstructed = rest[:tools_start] + rest[answer_now:]
        assert reconstructed == a, (
            "arm B's prompt is not arm A's prompt plus exactly "
            "the tool registration: replacing the intro "
            "paragraph and removing the tool section must "
            "reconstruct arm A byte-for-byte - equal "
            "information access requires the question, the "
            "deadline and the answer format to be identical")
        assert "fetch_primary_source" in b and "recompute" in b
        # And arm B must not retain arm A's "no tools" text.
        assert "no tools" not in b.lower()

    def test_the_cooperation_protocol_is_fixed_in_the_prompt(self):
        c = (PROMPTS / "arm_c.md").read_text(encoding="utf-8")
        for stage in ("STAGE 1", "STAGE 2", "STAGE 3"):
            assert stage in c
        # The protocol's bounds: one bounded revision round,
        # no voting, no third model, and a typed verdict -
        # concur true exactly when the objections list is empty.
        assert '{"concur": true, "objections": []}' in c
        assert '{"concur": false, "objections":' in c
        assert "no voting" in c and "no third model" in c


class TestTheSecrecy:
    def test_no_key_material_leaks_into_any_tier3_file(self):
        probes = _key_strings()
        # Convention 28: the probe must have computed its subject. An
        # empty keys.json would otherwise pass this vacuously.
        assert len(probes) >= 100, (
            f"only {len(probes)} key strings probed - the probe set "
            "did not read the frozen keys")
        for path in _tier3_files():
            text = path.read_text(encoding="utf-8")
            for probe in probes:
                assert probe not in text, (
                    f"key material from the frozen keys.json leaked "
                    f"into {path.relative_to(ROOT)}: {probe[:60]!r}")

    def test_no_model_id_in_any_tier3_file(self):
        # The same families test_docs.py guards in user-facing docs,
        # re-declared here because tests do not import each other.
        # The tier-3 files are user-facing documentation of the
        # experiment, so non-negotiable 6 applies to them in full.
        model_names = re.compile(
            r"glm|deepseek|minimax|sonar|perplexity|gemini|kimi|qwen|gpt-"
            r"|mistral|llama|claude|openai|anthropic|moonshot|z-ai",
            re.IGNORECASE)
        allowed = ["OpenAI-compatible", "OpenAI chat-completions",
                   "CLAUDE.md", ".claude/", "Claude Code"]
        for path in _tier3_files():
            for n, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line
                for word in allowed:
                    stripped = stripped.replace(word, "")
                hit = model_names.search(stripped)
                assert not hit, (
                    f"model id in {path.relative_to(ROOT)}:{n}: "
                    f"{line.strip()[:80]} - non-negotiable 6: the "
                    "manifest names pin environment variables, and the "
                    "serving proposals live in the owner's .env.tier3")


class TestTheExecution:
    def test_the_seeded_order_is_reconstructable(self):
        order_rule = MANIFEST["execution"]["interleaved_order"]
        seed = order_rule["seed"]
        assert seed == 20261003
        # The order runs the stage-1 selection: the 105
        # units over the seven selected questions, not
        # the frozen set's full 375.
        selected = MANIFEST["plan"]["question_selection"]["selected"]
        units = [(q["id"], rep, arm)
                 for q in QUESTIONS if q["id"] in selected
                 for rep in (1, 2, 3) for arm in ARMS]
        expected = set(units)
        order = list(units)
        random.Random(seed).shuffle(order)
        # A permutation: every unit once, none invented, none dropped.
        assert len(order) == 105
        assert len(set(order)) == 105
        assert set(order) == expected
        # Determinism: the seed reconstructs the order exactly.
        again = list(units)
        random.Random(seed).shuffle(again)
        assert order == again
        # The seed is load-bearing: a different seed must not
        # reproduce the order, or the reconstruction proves nothing.
        other = list(units)
        random.Random(seed + 1).shuffle(other)
        assert other != order

    def test_the_execution_registers_isolation_deadline_and_record(self):
        execution = MANIFEST["execution"]
        assert "_isolated_store()" in execution["isolation"]
        assert execution["common_deadline_seconds"] == 1800
        assert "ResultsLog" in execution["record"]
        assert "keys.json" in execution["no_model_access_to_keys"]
        assert "retry" in execution["retry_rules"].lower()
        assert "SweepBudget" in execution["spend_enforcement"]

    def test_the_registered_call_parameters(self):
        # Every parameter a unit's outcome depends on is
        # registered here, not buried in a call site.
        params = MANIFEST["execution"]["registered_call_parameters"]
        assert params["max_tokens"] == 8000
        assert params["temperature"] == 0.3
        assert "finish_reason" in params
        assert "truncated" in params["finish_reason"]

    def test_the_pilot_is_registered(self):
        pilot = MANIFEST["execution"]["pilot"]
        assert pilot["arms"] == ["A", "D"]
        assert pilot["repetitions_per_question"] == 1
        assert pilot["planned_units"] == 50
        assert pilot["seed"] == 20261004
        assert "TIER3_PILOT_AUTHORIZED" in pilot["authorization"]
        assert "$7.50" in pilot["authorization"]
        # Stage 1 supersedes the pilot's calibration role;
        # whether the mode is deleted is the advisor's ruling,
        # recorded as a question in the 119 response.
        assert "Superseded in role by stage 1" in pilot["supersession"]

    def test_the_stage_2_rule_is_pre_registered(self):
        rule = MANIFEST["execution"]["stage_2_rule"]
        # Pre-registered before the first paid unit, and
        # fixed: not adjusted after stage 1's results.
        assert "before the first paid unit" in rule
        assert "not adjusted after stage 1" in rule
        # The threshold: |E - A| >= 7 of the 21 units per arm.
        assert "7 or more of the 21" in rule
        assert "the pipeline question is answered" in rule
        assert "stage 2 is the owner's option" in rule
        # The advisor's 2026-10-05 review struck the causal
        # clause, before any paid unit: arms E and A differ in
        # both serving and treatment, and separating the two
        # is what the A-vs-D comparison is for - the rule is
        # a stopping rule only, and names no cause.
        assert "measurable cause" not in rule
        # The clause change is recorded in the manifest, with
        # the struck text and its reason.
        change = MANIFEST["execution"]["stage_2_rule_change_2026_10_05"]
        assert "measurable cause" in change
        assert "struck" in change
        assert "A-vs-D" in change
        # The otherwise-branch: the remaining 18 questions,
        # Q1-Q5 reported separately as calibration-exposed.
        assert "remaining 18 questions" in rule
        assert "calibration-exposed" in rule
        # The remainder the rule names is the plan's registered
        # remainder: the 18 the selection guard checks above.
        assert "stage_2_remainder" in rule
        assert len(MANIFEST["plan"]["question_selection"][
            "stage_2_remainder"]) == 18

    def test_the_preflight_is_registered(self):
        preflight = MANIFEST["execution"]["preflight"]
        # Five refusals: the worst-case ceilings, tool support,
        # context, the unboundable servings and the registered
        # max_tokens against the endpoint's max_completion_tokens.
        assert len(preflight["refuses"]) == 5
        assert any("worst case" in r for r in preflight["refuses"])
        assert any("tool support" in r for r in preflight["refuses"])
        assert any("context window" in r for r in preflight["refuses"])
        assert any("guard can bound" in r for r in preflight["refuses"])
        assert any("max_completion_tokens" in r for r in preflight["refuses"])
        # Reports: the catalogue's blindness, arm E's standing
        # caps, and the arm-E worst-case table.
        assert len(preflight["reports"]) == 3
        assert any("blind" in r for r in preflight["reports"])
        assert any("standing tier caps" in r for r in preflight["reports"])
        assert any("worst-case table" in r for r in preflight["reports"])

    def test_the_dry_run_and_reading_sheet_are_registered(self):
        dry_run = MANIFEST["execution"]["dry_run"]
        assert "mocked" in dry_run["what"]
        for failure in ("refusal", "deadline", "tool failure",
                        "invalid arm C verdict", "incomplete unit",
                        "resume after a kill"):
            assert failure in dry_run["failure_classes"], (
                f"the dry run does not register the {failure} "
                "failure class")
        sheet = MANIFEST["execution"]["reading_sheet"]
        assert "FAIL" in sheet["what"]
        assert "seeded" in sheet["what"]
        assert "no arm label" in sheet["what"]

    def test_arm_b_call_structure_is_registered(self):
        structure = MANIFEST["arms"]["B"]["call_structure"]
        assert "Calls 1 and 2 offer the tools" in structure
        # R2: the final call keeps the tools declared with
        # tool_choice "none" - the model sees the tools it
        # may not use, and answers. Withdrawing them
        # changed the request the serving saw.
        assert ('call 3 keeps them declared with '
                'tool_choice "none"') in structure
        assert "20 tool invocations" in structure

    def test_arm_c_check_is_a_typed_verdict(self):
        check = MANIFEST["arms"]["C"]["check"]
        assert '{"concur": boolean, "objections": [string]}' in check
        assert "concur true exactly when objections is empty" in check
        # The bounded retries are a hard whole-sequence bound:
        # the revision runs only when the check objected AND a
        # call remains.
        assert "hard whole-sequence bound" in check
        assert "starvation" in check

    def test_arm_e_delivery_is_the_completed_terminal(self):
        treatment = MANIFEST["arms"]["E"]["treatment"]
        assert "completed terminal" in treatment
        # Approved-not-shipped is scored and reported beside
        # the delivered count, never counted as delivered.
        assert "approved, not shipped" in treatment
        assert "never counted as delivered" in treatment

    def test_the_086_shootout_is_corrected(self):
        # The shootout graded escalation output, not direct
        # answers to questions - the manifest says so where
        # it cites the 19/20-against-13/20 result.
        for arm in ("C", "D"):
            criterion = MANIFEST["arms"][arm]["model_selection_criterion"]
            assert "086 escalation shootout" in criterion
            assert "docs/traces/086-escalation-shootout.jsonl" in criterion
            assert "19/20" in criterion and "13/20" in criterion
            assert "graded escalation output, not direct answers" in criterion

    def test_the_five_success_measures_are_defined(self):
        measures = MANIFEST["success_measures"]
        assert set(measures) == {
            "delivered_correctness_per_arm",
            "per_question_repeat_outcomes",
            "paired_wins_and_losses_against_A",
            "comparison_with_D",
            "total_cost_and_latency_including_failures"}
        for name, text in measures.items():
            assert text.strip(), f"success measure {name} is empty"
        # The denominator is the planned units, not the shipped ones:
        # 21 units per arm in stage 1.
        assert "21" in measures["delivered_correctness_per_arm"]
        assert "0/3" in measures["per_question_repeat_outcomes"]
        # And the measures name the stage-1 frame they score in.
        assert "105" in measures["total_cost_and_latency_including_failures"]
        assert "7 selected questions" in measures[
            "paired_wins_and_losses_against_A"]

    def test_the_failure_treatment_counts_every_failure_class(self):
        treatment = MANIFEST["failure_treatment"]
        assert set(treatment) == {"refusal", "serving_error",
                                  "timeout", "tool_failure",
                                  "incomplete_runs",
                                  "outstanding_liability"}
        # Incomplete runs are counted in the denominator, never
        # dropped, and the liability is part of what a unit cost.
        assert "denominator" in treatment["incomplete_runs"]
        assert "unreconciled_liability" in treatment["outstanding_liability"]
        # R2: the serving's own failure is its own class, beside
        # and never inside the refusal count - an empty reply
        # with finish "error" is the provider failing the call,
        # not the model refusing the question.
        assert "never a refusal" in treatment["serving_error"]
        assert "finish" in treatment["serving_error"]

    def test_the_ratification_stop_is_registered(self):
        assert MANIFEST["status"] == "manifest-frozen-awaiting-ratification"
        gates = MANIFEST["ratification_gates"]
        assert set(gates) == {"gate_1_servings", "gate_2_spend", "stop"}
        assert "$30.00" in gates["gate_2_spend"]
        assert "$37.80" in gates["gate_2_spend"]
        assert "not predicted costs" in gates["gate_2_spend"]
        # A lower authorization is allowed: the fit rule then
        # decides which units start, and a unit the rule does not
        # start is recorded as not started - never silently dropped.
        assert "lower" in gates["gate_2_spend"].lower() or (
            "not started" in MANIFEST["spend_enforcement"])
        # The STOP is mechanized, not just stated: the runner
        # refuses to start unless the environment shows both
        # gates cleared - the servings fingerprint and the
        # spend (or the pilot's own authorization).
        stop = gates["stop"]
        assert "TIER3_SERVINGS_RATIFIED" in stop
        assert "TIER3_SPEND_AUTHORIZED" in stop
        assert "TIER3_PILOT_AUTHORIZED" in stop
        assert "does not start" in stop
