"""The tier-4 pilot tooling (Ruling D52, command ARCH-20261017-122).

Tier 4 is the capacity test: does the pipeline's structure recover
answers a single call misses, on work hard enough for a single call
to miss it? The frozen pilot batch (evals/tier4/pilot/candidates.json,
D44) carries five questions — four F1 (everything given but hard) and
one F2 (the data lives in a fictional corpus profile) — and this
runner makes the batch runnable in two modes under the registered
ceilings and gates, proven by a mocked dry run:

* the calibration mode — nine units, one repetition each: arm A on
  T4-02..T4-05, arm D on T4-02..T4-05, arm D-pages on T4-06 — the
  two single-call arms on the F1 questions, and arm D holding the
  corpus pages on the F2 one, under the $2.00 registered ceiling;
* the pilot mode — the named question ids (at most four, from the
  frozen batch only) x their family's arms x one repetition: F1 arms
  A, D, F, E; F2 arms D-pages, F, E — under the $5.00 registered
  ceiling.

The model-visible text is the candidate's ``request`` only — plus,
for arm D on F2 (D-pages), the three corpus pages, verbatim and in
name order, each preceded by its file name, under the registered
separator. Never the requirements, the reference design, the worked
solution, the wrong designs or the difficulty rationale: the leakage
guard below asserts it, with its break-proof, for every unit of both
modes. The F2 units of arms F and E run under the tier-4 corpus
profile (``AUTORND_PROFILE=tier4`` — ``profiles/tier4.yaml``, whose
manifest's globals are the corpus pages), so the pipeline's own
grounding node loads the corpus into every request that reads it; the
F1 units of every arm run without it, so no corpus text reaches an
F1 question. Arm A does not run on F2.

Every figure the record carries is registered here: the per-unit
ceilings (A $0.10, D $0.30, F $0.40, E $1.50), the 3600-second
deadline, the two mode ceilings, the seeds, the manifest version, the
batch and corpus sha256 values the freeze guard holds the batch to.
The gates are the owner's: TIER3_SPEND_AUTHORIZED in .env.tier3 must
equal the mode's registered ceiling exactly (R4), and the servings map
is the owner's standing pins, fingerprint e0dc92a3aecb, refused
otherwise. Both modes refuse to start unless the freeze guard holds —
candidates.json and the corpus hash to the evidence's sha256 values,
and docs/tier4/ carries byte-identical copies of the corpus pages.

    python3 evals/tier4/runner.py preflight [calibration|pilot --ids IDS]
    python3 evals/tier4/runner.py plan [calibration|pilot --ids IDS]
    python3 evals/tier4/runner.py worst-case
    python3 evals/tier4/runner.py dry-run      # both modes, mocked, free
    python3 evals/tier4/runner.py reading-sheet RESULTS_FILE
    python3 evals/tier4/runner.py run calibration|pilot --ids IDS   # paid

The dry run is free by construction: the real machinery — the freeze
guard, the gates, the plan and its seeded order, the preflight, the
arm executors, the deadline, the fit-rule budget, the records, the
reading sheet — with the model-serving layer mocked the way the tier-3
dry run mocks it (a scripted client that bills through the real guard
and accounting, a fixture catalogue, a stand-in at the pipeline
boundary for arms E and F). No network, no spend. The calibration and
the pilot themselves wait for the owner's gate line.

The tier-3 runner (evals/tier3/runner.py) is imported by path, the
way the tests import it: evals/ is not an installed package. The arm
executors, the unit client, the worst-case tables, the preflight's
catalogue classes, the results log, the failure census and the dry
run's doubles are its; tier 4 registers its own ceilings, seeds,
scenario ids, function labels and prompt floors on top of them.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import importlib.util
import json
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# The repository root, and the tier-3 runner imported by path.
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TIER4 = Path(__file__).resolve().parent
TIER3 = ROOT / "evals" / "tier3"
RESULTS_DIR = ROOT / "evals" / "results"

# The tier-3 runner, imported by path (evals/ is not an installed
# package — the tests do the same). The registration in sys.modules
# precedes exec_module, and an instance the tests already loaded is
# reused, so a process that runs both suites holds one tier-3 module.
tier3 = sys.modules.get("tier3_runner")
if tier3 is None:
    _TIER3_SPEC = importlib.util.spec_from_file_location(
        "tier3_runner", TIER3 / "runner.py")
    tier3 = importlib.util.module_from_spec(_TIER3_SPEC)
    sys.modules["tier3_runner"] = tier3
    _TIER3_SPEC.loader.exec_module(tier3)

from autornd.profiles import (          # noqa: E402
    DEFAULT_PROFILE, get_profile, load_profile, set_profile)
from autornd.knowledge.context import load_docs_context  # noqa: E402

# The tier-3 machinery this runner reuses, named at module scope so
# the call sites below read as what they are.
ExperimentRefused = tier3.ExperimentRefused
OpenRouterClient = tier3.OpenRouterClient
PreflightReport = tier3.PreflightReport
SweepBudget = tier3.SweepBudget
Tier3ResultsLog = tier3.Tier3ResultsLog
Tier3Settings = tier3.Tier3Settings
UnitResult = tier3.UnitResult
_dry_run_client_factory = tier3._dry_run_client_factory
_dry_run_catalogue = tier3._dry_run_catalogue
_dry_run_tool_dispatcher = tier3._dry_run_tool_dispatcher
_env_overrides = tier3._env_overrides
_harness_pin_overrides = tier3._harness_pin_overrides
_answer_call = tier3._answer_call
_provider_failure_call = tier3._provider_failure_call
_shipped = tier3._shipped
_all_servings = tier3._all_servings
_catalogue_index = tier3.catalogue_index
_execute_arm = tier3._execute_arm
_per_request_charge = tier3._per_request_charge
_prompt_bytes = tier3._prompt_bytes
_rates = tier3._rates
_resolve_entry = tier3._resolve_entry
_serving_record = tier3._serving_record
_unit_client = tier3._unit_client
_unboundable_reason = tier3._unboundable_reason
_unpriced = tier3._unpriced
_arm_single = tier3._arm_single
_arm_e = tier3._arm_e
_arm_f = tier3._arm_f
_fetch_catalogue = tier3.fetch_catalogue
_fetch_credit = tier3.fetch_credit
_order_digest = tier3.order_digest
_render_prompt = tier3.render_prompt
_resolve_servings = tier3.resolve_servings
_servings_fingerprint = tier3.servings_fingerprint
_settings_lookup = tier3.settings_lookup
_worst_case_cost = tier3.worst_case_cost
failure_census = tier3.failure_census
isolate = tier3._isolated_store
prompt_text = tier3.prompt_text
run_scenario = tier3.run_scenario
worst_case_cost = tier3.worst_case_cost

__all__ = [
    "CALIBRATION_ARMS_F1", "CALIBRATION_ARMS_F2",
    "CALIBRATION_CEILING", "CALIBRATION_SEED",
    "PILOT_ARMS_F1", "PILOT_ARMS_F2", "PILOT_CEILING",
    "PILOT_ID_LIMIT", "PILOT_SEED", "PAGES_SEPARATOR",
    "TIER4_CEILINGS", "TIER4_DEADLINE_SECONDS",
    "TIER4_MANIFEST_VERSION", "TIER4_PROFILE",
    "BATCH_DATASET_VERSION", "REFUSED_EXIT",
    "ExperimentRefused", "Tier3ResultsLog", "UnitResult",
    "calibration_plan", "check_freeze", "corpus_context",
    "corpus_pages", "d_pages_message", "export_tier4_reading_sheet",
    "leakage_findings", "model_visible_message", "pilot_plan",
    "run_tier4_experiment", "run_tier4_unit", "tier4_dry_run",
    "tier4_gate_report", "tier4_preflight", "tier4_summarize",
    "unit_profile",
]

# ── The registered plan (the command's constraints) ─────
#
# Every constant here is a registered parameter: a value a unit's
# outcome depends on, so it is named in this file and the results
# header rather than buried in a call site.

# The per-unit authorization ceilings the command registers. D-pages
# carries arm D's ceiling: it is arm D's treatment with the corpus
# pages in the user message, so its spend bound is arm D's own.
TIER4_CEILINGS = {"A": 0.10, "D": 0.30, "F": 0.40, "E": 1.50}
TIER4_DEADLINE_SECONDS = 3600.0

# The two modes' registered ceilings (the gate's R4 figures).
CALIBRATION_CEILING = 2.00
PILOT_CEILING = 5.00

# The calibration mode's arms, by family: A and D on the F1
# questions, D-pages on the F2 one. Arm A does not run on F2.
CALIBRATION_ARMS_F1 = ("A", "D")
CALIBRATION_ARMS_F2 = ("D-pages",)
# The pilot mode's arms, by family.
PILOT_ARMS_F1 = ("A", "D", "F", "E")
PILOT_ARMS_F2 = ("D-pages", "F", "E")

# The seeds the two modes' interleaved orders are shuffled with —
# registered, so the order's digest in the results header is the
# figure both the runner and the guard test compute.
CALIBRATION_SEED = 20261017
PILOT_SEED = 20261018

# The pilot's registered limit on named question ids.
PILOT_ID_LIMIT = 4

# The corpus profile the F2 units of arms F and E run under.
TIER4_PROFILE = "tier4"

# The results record's identity: the manifest version the log's
# resume keys on, and the frozen batch's dataset version.
TIER4_MANIFEST_VERSION = "tier4-1"
BATCH_DATASET_VERSION = "tier4-pilot-2026-10-16"

# The registered separator between the request and the corpus pages
# in arm D's F2 user message (the command's ARM D ON F2 constraint).
PAGES_SEPARATOR = "\n\nReference documents:\n\n"

# The frozen batch and the corpus, and the sha256 values the
# evidence (the command file) registers them at — the freeze
# guard's constants. A mode refuses to start unless the tree still
# hashes to these figures.
PILOT_DIR = TIER4 / "pilot"
BATCH_PATH = PILOT_DIR / "candidates.json"
CORPUS_DIR = PILOT_DIR / "corpus"
DOCS_TIER4 = ROOT / "docs" / "tier4"
REGISTERED_BATCH_SHA256 = (
    "9c9109826431778bd203eddfe0ba12887b53434f33e3d656f4bb589"
    "cd216b634")
REGISTERED_CORPUS_SHA256 = (
    "1d27d491195edec184141ba3f8882c27ab509fa3bb7551f7404055fe"
    "9f78f1d9")

# The exit code a refusal returns (the tier-3 CLI's convention).
REFUSED_EXIT = 3

# The F1 and F2 question ids of the frozen batch, in the batch's
# own order.
F1_QUESTION_IDS = ("T4-02", "T4-03", "T4-04", "T4-05")
F2_QUESTION_IDS = ("T4-06",)


# ── The frozen batch and the corpus ─────────────────────

def load_candidates() -> list[dict[str, Any]]:
    """The frozen pilot batch, as it stands on disk."""
    return json.loads(BATCH_PATH.read_text(encoding="utf-8"))


def candidate_index() -> dict[str, dict[str, Any]]:
    """The batch keyed by question id."""
    return {candidate["id"]: candidate
            for candidate in load_candidates()}


def corpus_pages() -> list[tuple[str, str]]:
    """The corpus pages in name order: (file name, content).

    The order is the sorted file names, the way the evidence's
    concatenation and the D-pages message read them."""
    return [(path.name, path.read_text(encoding="utf-8"))
            for path in sorted(CORPUS_DIR.glob("*.md"))]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def batch_sha256() -> str:
    """The sha256 of candidates.json's bytes, as it stands."""
    return sha256_bytes(BATCH_PATH.read_bytes())


def corpus_sha256() -> str:
    """The sha256 of the corpus pages concatenated in name order.

    The evidence's figure: ``cat evals/tier4/pilot/corpus/*.md |
    sha256sum`` — the pages' bytes, no separator, name order."""
    digest = hashlib.sha256()
    for _name, content in corpus_pages():
        digest.update(content.encode("utf-8"))
    return digest.hexdigest()


def check_freeze() -> list[str]:
    """The freeze guard's refusals, each naming the file that drifted.

    Empty means the guard holds: candidates.json hashes to the
    evidence's sha256, the corpus concatenated in name order hashes
    to the evidence's sha256, and every page docs/tier4/ carries is
    byte-identical to the corpus page it copies. A mode refuses to
    start on any refusal here — the run's evidence is the frozen
    batch, and a batch that moved under the run is a different
    experiment from the one the ceilings and the reading were
    registered for."""
    refusals: list[str] = []
    measured = batch_sha256()
    if measured != REGISTERED_BATCH_SHA256:
        refusals.append(
            f"{BATCH_PATH}: sha256 {measured} is not the frozen "
            f"batch's registered sha256 "
            f"{REGISTERED_BATCH_SHA256} — the batch moved under the "
            "run (the freeze guard, command 122)")
    measured = corpus_sha256()
    if measured != REGISTERED_CORPUS_SHA256:
        refusals.append(
            f"{CORPUS_DIR}: the corpus pages concatenated in name "
            f"order hash to {measured}, not the registered corpus "
            f"sha256 {REGISTERED_CORPUS_SHA256} — the corpus moved "
            "under the run (the freeze guard, command 122)")
    for name, _content in corpus_pages():
        corpus_page = CORPUS_DIR / name
        docs_copy = DOCS_TIER4 / name
        if (not docs_copy.exists()
                or docs_copy.read_bytes() != corpus_page.read_bytes()):
            refusals.append(
                f"{docs_copy}: not byte-identical to its corpus "
                f"page {corpus_page} — the profile's grounding copy "
                "must be the frozen page itself (the freeze guard, "
                "command 122)")
    return refusals


# ── The model-visible text ──────────────────────────────

def d_pages_message(candidate: dict[str, Any]) -> str:
    """Arm D's F2 user message: the request, the registered
    separator, and the three corpus pages verbatim and in name
    order, each preceded by its file name."""
    pages = "\n\n".join(
        f"{name}\n\n{content}" for name, content in corpus_pages())
    return candidate["request"] + PAGES_SEPARATOR + pages


def model_visible_message(arm: str,
                          candidate: dict[str, Any]) -> str:
    """The model-visible text the arm's treatment carries: the
    candidate's request only, plus, for arm D on F2, the corpus
    pages under the registered separator. Never the requirements,
    the reference design, the worked solution, the wrong designs or
    the difficulty rationale — the leakage guard below asserts it."""
    if arm == "D-pages":
        return d_pages_message(candidate)
    return candidate["request"]


def message_sha256(arm: str, candidate: dict[str, Any]) -> str:
    """The sha256 of the exact user message the unit's treatment
    carries — the figure the unit record reports."""
    return sha256_bytes(
        model_visible_message(arm, candidate).encode("utf-8"))


# The leakage guard. A string an arm must never see is evidence of
# a leak only where it occurs in the message AND not in the request
# — the request is the one text every arm is given, so a figure the
# request itself states (T4-03's own '0.075') is the question's
# wording, not a leak. The floor keeps single characters and
# two-digit fragments out of the detector: a leak worth stopping
# names a requirement, a value, a sentence.
_FORBIDDEN_VALUE_FLOOR = 4
_FORBIDDEN_SENTENCE_FLOOR = 16
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def _string_leaves(value: Any, floor: int) -> list[str]:
    """The string leaves of a JSON-ish structure, at the floor.

    A number counts by its string form — the reference
    designs' values are mostly figures (27.65, 104.09), and
    a figure the message states is as much a leak as a word it
    states. Booleans and nulls carry nothing."""
    if isinstance(value, str):
        return [value] if len(value.strip()) >= floor else []
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, (int, float)):
        text = str(value)
        return [text] if len(text) >= floor else []
    if isinstance(value, dict):
        leaves: list[str] = []
        for item in value.values():
            leaves.extend(_string_leaves(item, floor))
        return leaves
    if isinstance(value, list):
        leaves = []
        for item in value:
            leaves.extend(_string_leaves(item, floor))
        return leaves
    return []


def forbidden_strings(candidate: dict[str, Any]) -> list[str]:
    """The strings an arm must never see, for this candidate:
    every requirement statement, every reference-design value, every
    worked-solution sentence, every wrong design's values and
    reason, and every difficulty-rationale sentence."""
    strings: list[str] = [
        requirement["statement"]
        for requirement in candidate.get("requirements", [])
    ]
    strings.extend(_string_leaves(
        candidate.get("reference_design", {}),
        _FORBIDDEN_VALUE_FLOOR))
    for source in ("worked_solution", "difficulty_rationale"):
        for sentence in _SENTENCE_SPLIT.split(
                candidate.get(source, "") or ""):
            if len(sentence.strip()) >= _FORBIDDEN_SENTENCE_FLOOR:
                strings.append(sentence.strip())
    for wrong in candidate.get("wrong_designs", []):
        strings.extend(_string_leaves(
            wrong.get("values", {}), _FORBIDDEN_VALUE_FLOOR))
        reason = (wrong.get("reason") or "").strip()
        if len(reason) >= _FORBIDDEN_SENTENCE_FLOOR:
            strings.append(reason)
    return strings


def leakage_findings(message: str,
                     candidate: dict[str, Any],
                     given: tuple[str, ...] = ()
                     ) -> list[str]:
    """The leakage findings for one unit: the forbidden strings
    that occur in the message but in none of the texts the arm
    is given.

    The request is the one text every arm is given, so a
    forbidden string the request itself states is the
    question's own wording — measured on the frozen batch:
    T4-03's request states its own '0.075' twice. An F2 unit
    is additionally given the corpus pages — D-pages inlines
    them in its user message, and the F2 units of arms F and
    E ground on them — so the corpus's own vocabulary (the
    product names the pages describe: VT-50, FC-300, VX-200)
    is the given world, not a leak. Measured on the frozen
    batch: the product names are the only forbidden strings
    the corpus carries; no requirement statement,
    worked-solution sentence, wrong-design reason or
    difficulty-rationale sentence occurs in it. Everything
    else is a leak."""
    given_texts = (candidate["request"],) + tuple(given)
    return [forbidden for forbidden in forbidden_strings(candidate)
            if forbidden in message
            and not any(forbidden in text
                        for text in given_texts)]


# ── The profile selection ───────────────────────────────

def unit_profile(family: str, arm: str) -> str | None:
    """The profile the unit runs under (the command's PROFILES
    constraint): the tier-4 corpus profile for an F2 unit of arm F
    or E — the pipeline's own grounding node loads the corpus into
    the requests that read it — and the process default for every
    other unit, so no corpus text reaches an F1 question. Arm D on
    F2 (D-pages) carries the pages in its user message and runs the
    single-call treatment, so it runs under the default too."""
    if family == "F2" and arm in ("E", "F"):
        return TIER4_PROFILE
    return None


@contextlib.contextmanager
def _profile_selected(name: str | None):
    """Run under the named profile, restoring the previous one.

    ``set_profile`` is the profile mechanism's own resolution path —
    the one ``AUTORND_PROFILE`` drives through ``get_profile()`` —
    so a unit's grounding reads the profile the unit registered,
    whatever the process's environment says."""
    previous = get_profile()
    set_profile(load_profile(name) if name else DEFAULT_PROFILE)
    try:
        yield
    finally:
        set_profile(previous)


def corpus_context() -> str:
    """The grounding context the tier-4 profile carries: the corpus
    pages, exactly as ``load_docs_context`` loads them under
    ``AUTORND_PROFILE=tier4``."""
    with _profile_selected(TIER4_PROFILE):
        return load_docs_context([], [])


def prompt_floor(arms: tuple[str, ...],
                 questions: dict[str, dict[str, Any]]) -> str:
    """The largest prompt the mode's pipeline calls can carry.

    For arms E and F the entry point is the scenario request, and
    the pipeline's own node prompts sit above it — the grounding
    node loads the corpus context into every request an F2 question
    reads, and an F1 question grounds on nothing (the default
    manifest's globals are empty). The floor is the largest request
    with its grounding context, the way the tier-3 tables read the
    largest question: a floor, with the guard's call-time
    computation the binding check."""
    context = corpus_context()
    floors: list[str] = []
    for candidate in questions.values():
        request = candidate["request"]
        if candidate["family"] == "F2":
            floors.append(request + "\n\n" + context)
        else:
            floors.append(request)
    return max(floors, key=lambda text: len(text.encode("utf-8")))


# ── The plan ────────────────────────────────────────────

def ceiling_key(arm: str) -> str:
    """The arm's registered ceiling and serving key: D-pages carries
    arm D's."""
    return "D" if arm == "D-pages" else arm


def tier4_order(seed: int, units: list[list[Any]]) -> list[list[Any]]:
    """The seeded interleaved order: the units enumerated as
    (question_id, repetition, arm), then ``random.Random(seed).shuffle``
    over the list — the tier-3 plan builder's own rule, so no arm
    runs as a block and time-of-day and serving-load confounds
    distribute across arms."""
    shuffled = [list(unit) for unit in units]
    random.Random(seed).shuffle(shuffled)
    return shuffled


def calibration_plan() -> list[list[Any]]:
    """The calibration mode's nine units, in the seeded interleaved
    order: arm A on T4-02..T4-05, arm D on T4-02..T4-05, arm
    D-pages on T4-06, one repetition each."""
    units: list[list[Any]] = [
        [question_id, 1, arm]
        for question_id in F1_QUESTION_IDS
        for arm in CALIBRATION_ARMS_F1
    ]
    units.extend([question_id, 1, arm]
                 for question_id in F2_QUESTION_IDS
                 for arm in CALIBRATION_ARMS_F2)
    return tier4_order(CALIBRATION_SEED, units)


def family_arms(family: str, mode: str) -> tuple[str, ...]:
    """The arms the mode runs on a question of this family."""
    if family == "F2":
        return (CALIBRATION_ARMS_F2 if mode == "calibration"
                else PILOT_ARMS_F2)
    return (CALIBRATION_ARMS_F1 if mode == "calibration"
            else PILOT_ARMS_F1)


def pilot_plan(question_ids: list[str],
               arms: tuple[str, ...] | None = None
               ) -> tuple[list[list[Any]], list[str]]:
    """The pilot mode's plan: the named question ids x their
    family's arms x one repetition, in the seeded interleaved order.

    Returns (the order, the refusals). The refusals name what the
    plan cannot run: more than the registered limit of ids, an id
    outside the frozen batch, a repeated id, or an arm the id's
    family does not run (arm A on an F2 question — the command's
    constraint, refused rather than silently skipped). ``arms`` is
    the caller's own restriction of the arms per id; unset, each id
    runs its family's arms."""
    refusals: list[str] = []
    if len(question_ids) > PILOT_ID_LIMIT:
        refusals.append(
            f"the pilot names {len(question_ids)} question ids; "
            f"its registered limit is {PILOT_ID_LIMIT} "
            "(PILOT_ID_LIMIT)")
    candidates = candidate_index()
    for question_id in question_ids:
        if question_id not in candidates:
            refusals.append(
                f"question id {question_id!r} is not in the frozen "
                f"batch ({BATCH_PATH}) — the pilot runs the frozen "
                "batch's questions only")
    if refusals:
        return [], refusals
    if len(set(question_ids)) != len(question_ids):
        refusals.append(
            "the pilot names a question id twice: "
            + ", ".join(sorted(
                {q for q in question_ids
                 if question_ids.count(q) > 1})))
        return [], refusals
    units: list[list[Any]] = []
    for question_id in question_ids:
        family = candidates[question_id]["family"]
        for arm in (arms if arms is not None
                    else family_arms(family, "pilot")):
            if arm not in family_arms(family, "pilot"):
                refusals.append(
                    f"arm {arm} does not run on a question of family "
                    f"{family} ({question_id}'s family runs "
                    + ", ".join(family_arms(family, "pilot"))
                    + " — the command's family arms)")
                continue
            units.append([question_id, 1, arm])
    if refusals:
        return [], refusals
    return tier4_order(PILOT_SEED, units), []


# ── The gate (R4) ───────────────────────────────────────

def tier4_gate_report(tier3_settings: Tier3Settings,
                      servings: dict[str, Any],
                      fingerprint: str,
                      ceiling: float,
                      mode: str) -> list[str]:
    """The tier-4 ratification gates, as the missing ones.

    Empty means every gate holds. The servings map is the owner's
    standing pins (arm E's per-tier lineup included), ratified by
    fingerprint — the same map tier 3 runs under, refused otherwise.
    The spend gate is R4's: TIER3_SPEND_AUTHORIZED must equal the
    mode's registered ceiling exactly — the calibration's $2.00, the
    pilot's $5.00 — an authorization above the ceiling would spend
    past a plan the owner never ratified, one below it stops the
    sweep mid-plan. Arms B and C do not run in tier 4, so their
    treatment gates (arm B's pin equal to arm A's) are not tier 4's
    to check."""
    missing: list[str] = []
    if not tier3_settings.tier3_servings_ratified:
        missing.append("TIER3_SERVINGS_RATIFIED is not set")
    elif tier3_settings.tier3_servings_ratified != fingerprint:
        missing.append(
            f"TIER3_SERVINGS_RATIFIED is "
            f"{tier3_settings.tier3_servings_ratified!r}, which is "
            f"not the servings map's fingerprint {fingerprint!r} "
            "— the map below is what would run")
    authorization = tier3_settings.tier3_spend_authorized
    if not authorization:
        missing.append("TIER3_SPEND_AUTHORIZED is not set")
    else:
        try:
            authorized = float(authorization)
        except ValueError:
            missing.append(
                f"TIER3_SPEND_AUTHORIZED is {authorization!r}, which "
                f"is not a dollar amount (the {mode}'s registered "
                f"ceiling is ${ceiling:.2f})")
        else:
            if authorized != ceiling:
                missing.append(
                    f"TIER3_SPEND_AUTHORIZED is {authorized:.2f}, "
                    f"which is not the {mode}'s registered ceiling "
                    f"${ceiling:.2f} (R4: the authorization must "
                    "equal the ceiling of the run it authorises)")
    return missing


# ── The preflight ───────────────────────────────────────

def _arm_servings(arm: str,
                    servings: dict[str, Any]) -> list[str]:
    """The servings an arm's calls name: arms E and F run the
    pipeline's standing tiers (arm F runs arm E's path on arm
    E's tiers), so their servings are the tier map's; every
    other arm names one serving — arm D-pages carries arm D's."""
    if arm in ("E", "F"):
        return list(servings["E"].values())
    return [servings[ceiling_key(arm)]]


def _single_call_worst_case(
        arm: str, floor_message: str,
        servings: dict[str, Any],
        index: dict[str, dict[str, Any]]) -> float:
    """The worst case of a single-call arm's one call, at the guard's
    own formula: the registered max_tokens against the arm's serving's
    rates, the prompt side the largest message the arm carries. Arm
    D-pages' message is the largest text any tier-4 arm carries —
    the request with the corpus pages inlined."""
    serving = _resolve_serving(arm, servings)
    prompt_rate, completion_rate = _rates(
        index, serving, f"arm {arm}")
    per_request = _per_request_charge(
        _resolve_entry(index, serving))
    system, user = _render_prompt(
        prompt_text(ceiling_key(arm)), floor_message)
    return _worst_case_cost(
        prompt_rate, completion_rate,
        _prompt_bytes(system, user),
        tier3.REGISTERED_MAX_TOKENS, per_request)


def _resolve_serving(arm: str,
                     servings: dict[str, Any]) -> str:
    """The serving the arm's calls name."""
    return servings[ceiling_key(arm)]


def tier4_preflight(
        servings: dict[str, Any],
        catalogue: list[dict[str, Any]],
        credit: float | None,
        ceiling: float,
        arms: tuple[str, ...],
        questions: dict[str, dict[str, Any]]
        ) -> PreflightReport:
    """The tier-4 preflight, before the first unit. Free: it reads
    the catalogue fixture or the free GET's result, and computes.

    It refuses to start, and prints each arm's per-call and per-unit
    worst case at the catalogue's shape, in the command's cases:

    1. any serving the mode's arms name has no catalogue price
       (D49: an unknown price is not free), or is not in the
       catalogue at all;
    2. a single-call arm (A, D, D-pages) whose call's worst case —
       the registered max_tokens at the largest message the arm
       carries, the guard's own formula — exceeds its per-unit
       ceiling: the call would be refused at zero spend, so the arm
       cannot run. The figure is the figure the command's LIMITS
       constraint names: STOP and report it, do not raise the
       ceiling;
    3. arm F: the verify-first workflow's per-call worst cases on
       the standing tiers (the tier-3 table, at the tier-4 prompt
       floor and the tier-4 ceiling) — a call that refuses even at
       zero spend, or a sequence whose worst case exceeds the
       per-unit ceiling, refuses the mode;
    4. arm E: the standing pipeline's per-call worst cases on the
       standing tiers — a call that refuses even at zero spend
       refuses the mode. Arm E's sequence is the pipeline's own,
       bounded by its call limit and the per-call guard at call
       time, so the sequence's worst case is reported, not refused
       (the tier-3 manifest registers it the same way);
    5. the provider's remaining credit, read by the free GET, below
       the mode's ceiling — the refusal names the shortfall. A
       balance that could not be read is no evidence, and a paid run
       that cannot establish its balance does not start.
    """
    report = PreflightReport()
    index = _catalogue_index(catalogue)

    # Case 1, for every serving the mode's arms name — the worst
    # cases below need rates, and a serving with no price is refused
    # whatever else is true of it.
    for arm in arms:
        for serving in _arm_servings(arm, servings):
            entry = _resolve_entry(index, serving)
            if entry is None:
                report.refusals.append(
                    f"arm {arm}: the serving {serving!r} is not in the "
                    "provider catalogue")
            elif _unpriced(entry):
                report.refusals.append(
                    f"arm {arm}: the serving {serving} has no catalogue "
                    f"price the guard can bound "
                    f"({_unboundable_reason(entry)}; D49: an unknown "
                    "price is not free)")
    if report.refusals:
        return report

    # Case 2: each single-call arm's one call, at the largest
    # message the arm carries among the mode's questions.
    for arm in ("A", "D", "D-pages"):
        if arm not in arms:
            continue
        floor = max(
            (model_visible_message(arm, candidate)
             for candidate in questions.values()),
            key=lambda text: len(text.encode("utf-8")))
        worst = _single_call_worst_case(arm, floor, servings, index)
        arm_ceiling = TIER4_CEILINGS[ceiling_key(arm)]
        report.reports.append(
            f"arm {arm}: one call, the largest message the mode "
            f"carries — worst case ${worst:.4f} against the "
            f"${arm_ceiling:.2f} per-unit ceiling "
            f"({'refused even at zero spend' if worst > arm_ceiling else 'within the ceiling'}; "
            "the prompt side is the largest message, a floor — the "
            "guard computes the real bytes at call time)")
        if worst > arm_ceiling:
            report.refusals.append(
                f"arm {arm}: the worst case of its one call is "
                f"${worst:.4f}, above its per-unit ceiling "
                f"${arm_ceiling:.2f} (the registered max_tokens "
                f"{tier3.REGISTERED_MAX_TOKENS} at the largest "
                f"message the arm carries) — STOP and report the "
                "figure; the ceiling is not raised")

    # Cases 3 and 4: the tier-3 worst-case tables, at the tier-4
    # prompt floor and the tier-4 per-unit ceilings. Every row is
    # reported — the preflight prints each arm's per-call and
    # per-unit worst case at the catalogue's shape — and a row
    # that refuses even at zero spend refuses the mode.
    floor = prompt_floor(arms, questions)
    if "F" in arms:
        for row in tier3.arm_f_worst_case(
                servings, catalogue, prompt_floor=floor,
                unit_ceiling=TIER4_CEILINGS["F"]):
            if row.get("unknown"):
                report.refusals.append(
                    f"arm F/{row['tier']}: {row['serving']} — no "
                    f"worst case the guard can bound: "
                    f"{row.get('reason')}")
                continue
            calls = row.get("calls")
            if row.get("tier_worst_case") is not None:
                figures = (
                    f"worst case per call "
                    f"${row['worst_case']:.4f}, the "
                    f"workflow's {calls} calls on this "
                    f"tier: ${row['tier_worst_case']:.4f}")
            else:
                # The bound row: its worst case is the
                # sequence the workflow's counts compose.
                figures = (f"the sequence's worst case, "
                           f"its bound of {calls} calls "
                           f"composed: ${row['worst_case']:.4f}")
            report.reports.append(
                f"arm F/{row['tier']}: {row['serving']} — "
                f"{figures} against the "
                f"${TIER4_CEILINGS['F']:.2f} per-unit ceiling "
                f"({'refused even at zero spend' if row['refuses_even_at_zero_spend'] else 'within the ceiling'}; "
                "the prompt side is the largest prompt, a floor — "
                "the guard computes the real bytes at call time)")
            if row.get("refuses_even_at_zero_spend"):
                report.refusals.append(
                    f"arm F/{row['tier']}: the worst case "
                    f"${row['worst_case']:.4f} refuses even at zero "
                    f"spend, above the "
                    f"${TIER4_CEILINGS['F']:.2f} per-unit ceiling "
                    "(the ceiling is not raised)")
    if "E" in arms:
        for row in tier3.arm_e_worst_case(
                servings, catalogue, prompt_floor=floor,
                unit_ceiling=TIER4_CEILINGS["E"]):
            if row.get("unknown"):
                report.refusals.append(
                    f"arm E/{row['tier']}: {row['serving']} — no "
                    f"worst case the guard can bound: "
                    f"{row.get('reason')}")
                continue
            report.reports.append(
                f"arm E/{row['tier']}: {row['serving']} — "
                f"worst case per call ${row['worst_case']:.4f} "
                f"against the ${TIER4_CEILINGS['E']:.2f} per-unit "
                f"ceiling "
                f"({'refused even at zero spend' if row['refuses_even_at_zero_spend'] else 'within the ceiling'}; "
                "the prompt side is the largest prompt, a floor — "
                "the guard computes the real bytes at call time; "
                "arm E's sequence is the pipeline's own, bounded "
                "by its call limit and the per-call guard at call "
                "time, so the sequence's worst case is reported by "
                "the worst-case command, not refused here)")
            if row.get("refuses_even_at_zero_spend"):
                report.refusals.append(
                    f"arm E/{row['tier']}: the worst case "
                    f"${row['worst_case']:.4f} refuses even at zero "
                    f"spend, above the "
                    f"${TIER4_CEILINGS['E']:.2f} per-unit ceiling "
                    "(the ceiling is not raised)")

    # Case 5: the account's remaining credit against the mode's
    # own ceiling.
    if credit is None:
        report.refusals.append(
            "the provider's remaining credit could not be read — no "
            "evidence of a balance, and a paid run that cannot "
            "establish its balance does not start")
    elif credit < ceiling:
        report.refusals.append(
            f"the provider's remaining credit ${credit:.2f} is below "
            f"the {mode_name(ceiling)}'s registered ceiling "
            f"${ceiling:.2f} (shortfall "
            f"${ceiling - credit:.2f})")
    return report


def mode_name(ceiling: float) -> str:
    """The mode's name, for a refusal that names its ceiling."""
    return ("calibration" if ceiling == CALIBRATION_CEILING
            else "pilot" if ceiling == PILOT_CEILING
            else f"the ${ceiling:.2f}-ceiling")


# ── The unit executor ───────────────────────────────────

async def _tier4_execute_arm(
        arm: str, message: str, question_id: str,
        repetition: int, servings: dict[str, Any],
        budget: SweepBudget | None, deadline: float,
        client_factory: Any, tool_dispatcher: Any,
        scenario_runner: Any, spec: Any,
        spec_f: Any = None,
        pipeline_client_factory: Any = None,
        client_holder: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
    """Dispatch to the arm's executor and shape its payload — the
    tier-3 executor's own dispatch, at the tier-4 registrations:
    the tier-4 ceilings, the tier-4 scenario ids and function
    labels, and D-pages as arm D's single call carrying the corpus
    pages in its user message.

    ``client_holder`` receives the unit's client as soon as it
    exists, so the unit's record carries the figures the client
    booked (spend, unreconciled liability) even when a call fails
    mid-flight — the manifest's outstanding-liability rule."""
    unit_key = (question_id, repetition, arm)
    if arm in ("A", "D", "D-pages"):
        serving = servings[ceiling_key(arm)]
        client = _unit_client(
            unit_key, arm, serving,
            TIER4_CEILINGS[ceiling_key(arm)], 1,
            factory=client_factory)
        if client_holder is not None:
            client_holder["client"] = client
        # D-pages is arm D's treatment — arm D's own system prompt
        # (evals/tier3/prompts/arm_d.md, unchanged) — with the
        # corpus pages in the user message; the call bills to the
        # experiment's own function label.
        answer, finish_reasons = await _arm_single(
            ceiling_key(arm), message, serving, client,
            function_prefix="tier4")
        return {"answer": answer, "client": client,
                "calls": client.calls,
                "finish_reasons": finish_reasons}
    # Arms E and F: the pipeline builds its own clients (run_scenario's
    # BoundedRunner sets their ceilings from the scenario's max_calls
    # and the sweep's per-unit cap), so its factory takes no
    # arguments — a separate seam from the arms A-D factory above.
    # Arm F runs the verify-first workflow (D51 (8)); arm E runs the
    # standing workflow. Both run under the tier-4 per-unit ceiling,
    # with the tier-4 scenario ids and the tier-4 delivery reader.
    pipeline_factory = (pipeline_client_factory
                        if pipeline_client_factory is not None
                        else (lambda: OpenRouterClient()))
    arm_spec = spec_f if arm == "F" else spec
    arm_runner = _arm_f if arm == "F" else _arm_e
    run, answer, kind = await arm_runner(
        message, question_id, repetition, deadline, budget,
        arm_spec, _settings_lookup(), pipeline_factory,
        scenario_runner=scenario_runner,
        scenario_prefix="tier4",
        unit_ceiling=TIER4_CEILINGS[arm])
    calls_after_asks = sum(
        calls for tier, calls in
        (getattr(run, "calls_by_tier", {}) or {}).items()
        if tier != "triage")
    return {"answer": answer, "run": run,
            "delivered_kind": kind,
            "calls": getattr(run, "calls", 0),
            "finish_reasons": [],
            "tool_invocations": [],
            "workflow": (arm_spec.name
                         if getattr(arm_spec, "name", None)
                         else None),
            "calls_after_asks": calls_after_asks}


async def run_tier4_unit(
        unit_key: tuple[str, int, str],
        questions: dict[str, dict[str, Any]],
        servings: dict[str, Any],
        budget: SweepBudget | None,
        deadline: float = TIER4_DEADLINE_SECONDS,
        deadline_overrides: dict[tuple[str, int, str],
                                 float] | None = None,
        client_factory: Any = None,
        tool_dispatcher: Any = None,
        scenario_runner: Any = None,
        spec: Any = None,
        spec_f: Any = None,
        pipeline_client_factory: Any = None,
        ) -> UnitResult:
    """One tier-4 unit, end to end: the arm's treatment under the
    mode's deadline inside ``_isolated_store()`` and under the unit's
    registered profile, with every figure the record carries.

    The deadline is enforced with ``asyncio.wait_for`` around the
    whole unit (arms E and F's runs also carry it as their scenario
    timeout, so the watchdog ends the run by its own terminal and
    this backstop fires only if the watchdog failed). Arms A, D and
    D-pages's spend is booked to the sweep budget here; arms E and
    F's is booked inside run_scenario, which makes the same
    decision with the same fit rule. The failure classes are the
    tier-3 unit's own: a refusal, a serving error, a deadline, an
    incomplete unit, a skipped unit, each counted in its arm's
    denominator, never dropped.
    """
    question_id, repetition, arm = unit_key
    candidate = questions[question_id]
    family = candidate["family"]
    message = model_visible_message(arm, candidate)
    result = UnitResult(
        question_id=question_id, repetition=repetition, arm=arm,
        status="incomplete",
        serving=_serving_record(ceiling_key(arm), servings))
    effective_deadline = (deadline_overrides or {}).get(
        unit_key, deadline)
    profile_name = unit_profile(family, arm) or "default"

    # The fit rule, decided before any client exists. Arms E and F's
    # run_scenario makes the same decision inside itself, with the
    # same budget object, so the two ceilings compose the way the
    # harness's sweeps compose them.
    if (arm not in ("E", "F") and budget is not None
            and not budget.can_start(
                TIER4_CEILINGS[ceiling_key(arm)])):
        result.status = "skipped"
        result.stop_reason = budget.skip(
            TIER4_CEILINGS[ceiling_key(arm)])
        return result

    started = time.perf_counter()
    client: OpenRouterClient | None = None
    run: Any = None
    made: dict[str, Any] = {}
    try:
        with isolate():
            with _profile_selected(profile_name
                                   if profile_name != "default"
                                   else None):
                payload = await asyncio.wait_for(
                    _tier4_execute_arm(
                        arm, message, question_id, repetition,
                        servings, budget, effective_deadline,
                        client_factory=client_factory,
                        tool_dispatcher=tool_dispatcher,
                        scenario_runner=scenario_runner,
                        spec=spec, spec_f=spec_f,
                        pipeline_client_factory=(
                            pipeline_client_factory),
                        client_holder=made),
                    effective_deadline)
        client = payload.get("client")
        run = payload.get("run")
        answer = payload.get("answer")
        result.calls = payload.get("calls", 0)
        result.finish_reasons = payload.get("finish_reasons", [])
        result.tool_invocations = payload.get("tool_invocations", [])
        result.truncated = any(
            reason == "length" for reason in result.finish_reasons)
        if run is not None:
            # Arms E and F: the pipeline run's own accounting, and
            # its internals (R1) — why it ended the way it did.
            result.cost = getattr(run, "cost", 0.0) or 0.0
            result.cost_by_tier = dict(
                getattr(run, "cost_by_tier", {}) or {})
            result.providers_by_tier = {
                tier: list(providers)
                for tier, providers in
                (getattr(run, "providers_by_tier", {}) or {}).items()}
            result.retries_by_kind = dict(
                getattr(run, "retries", {}) or {})
            result.unreconciled_liability = float(
                getattr(run, "unreconciled_liability", 0.0) or 0.0)
            if getattr(run, "credit_exhausted", False):
                result.credit_exhausted = True
            result.pipeline = _pipeline_record(run)
            result.workflow = payload.get("workflow")
            result.calls_after_asks = payload.get("calls_after_asks")
        elif client is not None:
            result.cost = client.spend
            result.cost_by_tier = dict(client.spend_by_function)
            result.providers_by_tier = {
                function: list(providers)
                for function, providers in
                client.providers_by_function.items()}
            result.retries_by_kind = dict(client.retries_by_kind)
            result.unreconciled_liability = (
                client.unreconciled_liability)
        # The delivered answer, and the failure classes — the tier-3
        # unit's own classification (a tier-4 unit is the same
        # instrument, so it fails the same ways).
        if arm in ("E", "F"):
            kind = payload.get("delivered_kind", "")
            result.delivered_kind = kind
            if getattr(run, "was_skipped", False) or (
                    getattr(run, "skipped", False)):
                result.status = "skipped"
                result.stop_reason = (
                    getattr(run, "error", None)
                    or "the sweep's budget stopped the unit")
            elif kind == "no answer":
                result.status = "incomplete"
                result.stop_reason = (
                    f"the pipeline ended without an answer "
                    f"(terminal status: "
                    f"{getattr(run, 'status', None)!r})")
            else:
                result.status = "delivered"
        elif answer is None or not str(answer).strip():
            if (result.finish_reasons
                    and result.finish_reasons[-1] == "error"):
                result.status = "serving_error"
                result.stop_reason = (
                    "the serving returned an empty reply with finish "
                    "'error' - a provider failure, not a refusal")
            else:
                result.status = "refusal"
                result.stop_reason = (
                    "the serving returned an empty reply "
                    f"(finish_reason: "
                    f"{result.finish_reasons[-1] if result.finish_reasons else None!r})")
        else:
            result.status = "delivered"
        result.answer = answer
    except asyncio.TimeoutError:
        result.status = "deadline"
        result.stop_reason = (
            f"the unit deadline ({effective_deadline:.0f}s) "
            "stopped the unit")
        client = made.get("client")
        if client is not None:
            result.cost = client.spend
            result.unreconciled_liability = (
                client.unreconciled_liability)
        elif run is not None:
            result.cost = getattr(run, "cost", 0.0) or 0.0
            result.unreconciled_liability = float(
                getattr(run, "unreconciled_liability", 0.0) or 0.0)
            # The outer backstop fired before the pipeline could book
            # its spend to the sweep: charge the full ceiling as
            # liability, the conservative bound on what the unit may
            # have spent.
            if budget is not None:
                budget.record(TIER4_CEILINGS[ceiling_key(arm)])
                result.unreconciled_liability += (
                    TIER4_CEILINGS[ceiling_key(arm)])
    except (tier3.ProviderFailure, tier3.SpendGuardRefused,
            tier3.BudgetExceeded) as exc:
        # A provider that consumed its budget and emitted nothing, or
        # a call the guard refused: the unit did not conclude, and
        # the figures say which.
        result.status = "incomplete"
        result.stop_reason = f"{type(exc).__name__}: {exc}"
        client = made.get("client")
        if client is not None:
            result.cost = client.spend
            result.unreconciled_liability = (
                client.unreconciled_liability)
    except httpx.HTTPStatusError as exc:
        # An error status the serving returned. A 402 is the
        # account's credit exhausted (the ruling of 2026-10-15): the
        # unit is recorded as it ended, and the flag says the sweep
        # stops here. The status code is the typed field the
        # provider's own error carries, never the message's prose
        # (non-negotiable 3).
        client = made.get("client")
        if (getattr(getattr(exc, "response", None),
                    "status_code", None) == 402):
            result.status = "incomplete"
            result.stop_reason = (
                "provider credit exhausted: "
                f"{type(exc).__name__}: {exc}")
            result.credit_exhausted = True
        else:
            result.status = "incomplete"
            result.stop_reason = f"{type(exc).__name__}: {exc}"
        if client is not None:
            result.cost = client.spend
            result.unreconciled_liability = (
                client.unreconciled_liability)
        elif run is not None:
            result.cost = getattr(run, "cost", 0.0) or 0.0
            result.unreconciled_liability = float(
                getattr(run, "unreconciled_liability", 0.0) or 0.0)
    except Exception as exc:      # a broken run is a result, not a crash
        result.status = "incomplete"
        result.stop_reason = f"{type(exc).__name__}: {exc}"
        client = made.get("client")
        if client is not None:
            result.cost = client.spend
            result.unreconciled_liability = (
                client.unreconciled_liability)
    finally:
        result.seconds = time.perf_counter() - started

    # No scorer: the frozen tier-2 scorer carries no keys for the
    # tier-4 questions, and tier 4's primary measure is the two blind
    # hand readings against the requirement statements (D52 §5) — the
    # requirement checker is the first growth step's, not this
    # command's (the command's constraint). The reading sheet is the
    # record a reading reads.
    # Arms A, D and D-pages book their spend to the sweep here; arms
    # E and F's run_scenario already booked it.
    if (arm not in ("E", "F") and budget is not None
            and result.status not in ("skipped",)):
        budget.record(result.cost)
    return result


def _pipeline_record(run: Any) -> dict[str, Any]:
    """The pipeline run's internals, as the unit record carries them
    (the tier-3 record's own shape, read from the tier-3 module so
    the two records cannot drift)."""
    return tier3._pipeline_record(run)


def tier4_unit_record(result: UnitResult,
                      candidate: dict[str, Any],
                      arm: str,
                      profile_name: str,
                      message: str) -> dict[str, Any]:
    """The tier-4 unit record: the tier-3 unit record's own fields,
    plus the tier-4 ones — the question's family, the profile the
    unit ran under, the sha256 of the exact user message the
    treatment carried, and the pipeline record's candidate,
    iterations and reason surfaced where the command's RECORDS
    constraint names them. A pipeline figure that never ran is None,
    not an empty shell (convention 28: no evidence is a different
    claim from a measured zero)."""
    record = result.record()
    record["family"] = candidate["family"]
    record["profile"] = profile_name
    record["message_sha256"] = sha256_bytes(
        message.encode("utf-8"))
    pipeline = record.get("pipeline")
    record["candidate"] = (pipeline or {}).get("candidate")
    record["iterations"] = (pipeline or {}).get("iterations")
    record["reason"] = (pipeline or {}).get("reason")
    return record


# ── The experiment driver ───────────────────────────────

def default_results_path(mode: str) -> Path:
    """evals/results/<utc-timestamp>-tier4-<mode>.jsonl"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return RESULTS_DIR / f"{stamp}-tier4-{mode}.jsonl"


def mode_arms(mode: str) -> tuple[str, ...]:
    """Every arm the mode can run, in the plan's own order."""
    if mode == "calibration":
        return CALIBRATION_ARMS_F1 + CALIBRATION_ARMS_F2
    return PILOT_ARMS_F1 + PILOT_ARMS_F2


async def run_tier4_experiment(
        mode: str,
        question_ids: list[str] | None = None,
        results_path: str | Path | None = None,
        client_factory: Any = None,
        tool_dispatcher: Any = None,
        scenario_runner: Any = None,
        pipeline_client_factory: Any = None,
        catalogue: list[dict[str, Any]] | None = None,
        credit: float | None = None,
        deadline_overrides: dict[tuple[str, int, str],
                                      float] | None = None,
        ) -> dict[str, Any]:
    """One tier-4 experiment run: the freeze guard, the gates, the
    plan, the free preflight, then every unit of the plan in the
    seeded interleaved order, under the sweep budget, each recorded
    as it finishes.

    The freeze guard, the gates and the preflight come before any
    network call, and a refusal names each missing gate, each
    drifted file and each refusal case. On a 402 the sweep stops:
    every unit after it is recorded not_run (provider credit),
    outside the arm denominators, the way the tier-3 run records
    them. The records carry the header's batch and corpus sha256
    values, the mode, the order digest and the servings fingerprint,
    and each unit's family, arm, profile, message sha256 and
    tier-3 unit fields.
    """
    tier3_settings = Tier3Settings()
    servings = _resolve_servings(tier3_settings)
    fingerprint = _servings_fingerprint(servings)
    authorization = (CALIBRATION_CEILING if mode == "calibration"
                     else PILOT_CEILING)

    # The freeze guard: the batch and the corpus as they stand are
    # the ones the evidence registered.
    freeze = check_freeze()
    if freeze:
        raise ExperimentRefused(
            "the freeze guard refused to start",
            servings, fingerprint, freeze)

    # The ratification gates, before any network call.
    missing = tier4_gate_report(
        tier3_settings, servings, fingerprint, authorization, mode)
    if missing:
        raise ExperimentRefused(
            "the ratification gates are not cleared",
            servings, fingerprint, missing)

    # The plan: the calibration's nine units, or the pilot's named
    # ids x their family's arms.
    if mode == "calibration":
        order = calibration_plan()
        questions = {question_id: candidate
                     for question_id, candidate
                     in candidate_index().items()
                     if question_id in F1_QUESTION_IDS
                     or question_id in F2_QUESTION_IDS}
        named_ids = list(F1_QUESTION_IDS + F2_QUESTION_IDS)
    else:
        order, refusals = pilot_plan(question_ids or [])
        if refusals:
            raise ExperimentRefused(
                "the pilot plan refused to start",
                servings, fingerprint, refusals)
        questions = {question_id: candidate
                     for question_id, candidate
                     in candidate_index().items()
                     if question_id in set(question_ids or [])}
        named_ids = list(question_ids or [])
    arms = tuple(sorted({unit[2] for unit in order}))
    digest = _order_digest(order)

    # The free preflight, before the first unit.
    if catalogue is None:
        catalogue = await _fetch_catalogue(
            confirm={serving for serving in _all_servings(servings)})
    if credit is None:
        credit = await _fetch_credit()
    report = tier4_preflight(
        servings, catalogue, credit=credit, ceiling=authorization,
        arms=arms, questions=questions)
    if report.refusals:
        raise ExperimentRefused(
            "the preflight refused to start",
            servings, fingerprint, report.refusals)

    path = (Path(results_path) if results_path is not None
            else default_results_path(mode))
    log = Tier3ResultsLog(path, config={
        "record": "header",
        "mode": mode,
        "manifest_version": TIER4_MANIFEST_VERSION,
        "dataset_version": BATCH_DATASET_VERSION,
        "batch_sha256": batch_sha256(),
        "corpus_sha256": corpus_sha256(),
        "seed": (CALIBRATION_SEED if mode == "calibration"
                 else PILOT_SEED),
        "question_ids": named_ids,
        "repetitions": 1,
        "arms": list(arms),
        "order_sha256": digest,
        "order_units": len(order),
        "servings": servings,
        "servings_fingerprint": fingerprint,
        "ceilings": dict(TIER4_CEILINGS),
        "authorization_ceiling": authorization,
        "max_tokens": tier3.REGISTERED_MAX_TOKENS,
        "temperature": tier3.REGISTERED_TEMPERATURE,
        "deadline_seconds": TIER4_DEADLINE_SECONDS,
        "pins": {name: getattr(tier3_settings, name) for name in (
            "tier3_arm_a", "tier3_arm_d", "tier3_servings_ratified",
            "tier3_spend_authorized")},
    })

    budget = SweepBudget(cap=authorization)
    spec = tier3._standing_spec() if "E" in arms else None
    spec_f = tier3._verify_first_spec() if "F" in arms else None
    records: list[dict[str, Any]] = []
    log.header()

    # Resume: skip every unit already recorded, and charge the
    # unit in flight at the interruption its full ceiling as
    # unreconciled liability before re-running it.
    recorded = log.recorded_units()
    in_flight = log.in_flight()
    charged = 0.0
    if in_flight is not None:
        charged = TIER4_CEILINGS[ceiling_key(in_flight[2])]
        budget.record(charged)

    started = 0
    for index, unit_key in enumerate(order):
        key = tuple(unit_key)
        if key in recorded:
            continue
        log.unit_started(*key)
        result = await run_tier4_unit(
            key, questions, servings, budget,
            deadline_overrides=deadline_overrides,
            client_factory=client_factory,
            tool_dispatcher=tool_dispatcher,
            scenario_runner=scenario_runner,
            spec=spec, spec_f=spec_f,
            pipeline_client_factory=pipeline_client_factory)
        # The tier-4 record: the unit's own fields, plus the family,
        # the profile and the message sha256 the command's RECORDS
        # constraint names.
        candidate = questions[key[0]]
        record = tier4_unit_record(
            result, candidate, key[2],
            unit_profile(candidate["family"], key[2]) or "default",
            model_visible_message(key[2], candidate))
        log.unit(record)
        records.append(record)
        started += 1
        if result.credit_exhausted:
            # The first 402 stops the sweep. Every unit after this
            # one is recorded not_run (provider credit) — outside the
            # arm denominators, counted by the report — rather than
            # lost: the record states what happened to the plan, and
            # a resume after a top-up re-runs them.
            for rest in order[index + 1:]:
                rest_key = tuple(rest)
                not_run = UnitResult(
                    question_id=rest_key[0], repetition=rest_key[1],
                    arm=rest_key[2], status="not_run",
                    serving=_serving_record(
                        ceiling_key(rest_key[2]), servings),
                    stop_reason=(
                        "not run: the provider's credit was exhausted "
                        "before this unit started (the sweep stopped "
                        "at the first 402)"))
                not_run_record = not_run.record()
                not_run_record["family"] = (
                    questions[rest_key[0]]["family"])
                not_run_record["profile"] = (
                    unit_profile(
                        questions[rest_key[0]]["family"],
                        rest_key[2]) or "default")
                not_run_record["message_sha256"] = message_sha256(
                    rest_key[2], questions[rest_key[0]])
                log.unit(not_run_record)
                records.append(not_run_record)
            break
    log.close()

    all_records = log.all_units()
    measures = {
        "total_units": len(all_records),
        "by_status": _by_status(all_records),
        "total_cost": sum(r.get("cost", 0.0) for r in all_records),
        "total_seconds": sum(r.get("seconds", 0.0)
                             for r in all_records),
        "delivered": sum(
            1 for r in all_records if r.get("status") == "delivered"),
    }
    summary = tier4_summarize(
        all_records,
        f"tier-4 {mode} run — {len(order)} planned units, seed "
        f"{log.config['seed']}, order sha256 {digest[:12]}…")
    return {
        "mode": mode,
        "path": str(path),
        "records": all_records,
        "summary": summary,
        "measures": measures,
        "census": failure_census(all_records),
        "order_sha256": digest,
        "servings": servings,
        "servings_fingerprint": fingerprint,
        "preflight_reports": report.reports,
        "budget": {"cap": budget.cap, "spent": budget.spent,
                   "started": budget.started,
                   "skipped": budget.skipped},
        "order_units": len(order),
        "questions": questions,
        "question_ids": named_ids,
        "seed": log.config["seed"],
        "resumed": in_flight is not None,
        "in_flight": in_flight,
        "charged_liability": charged,
    }


def _by_status(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record["status"]] = (
            counts.get(record["status"], 0) + 1)
    return counts


# ── The summary and the reading sheet ───────────────────

def tier4_summarize(records: list[dict[str, Any]],
                    title: str) -> str:
    """The run summary: per arm, the units by status, the delivered
    count, the spend and the latency; then the totals. Every failure
    class is in its arm's denominator. Tier 4's primary measure is
    the two blind hand readings against the requirement statements
    (D52 §5) — the scorer is not a measure here, so no correctness
    fraction is claimed."""
    lines = [title]
    for arm in sorted({r["arm"] for r in records}):
        arm_records = [r for r in records if r["arm"] == arm]
        by_status: dict[str, int] = {}
        for record in arm_records:
            by_status[record["status"]] = (
                by_status.get(record["status"], 0) + 1)
        status_line = ", ".join(
            f"{count} {status}" for status, count
            in sorted(by_status.items()))
        lines.append(
            f"arm {arm}: {len(arm_records)} units — {status_line}; "
            f"delivered {sum(1 for r in arm_records if r.get('status') == 'delivered')}"
            f"/{len(arm_records)}; "
            f"${sum(r.get('cost', 0.0) for r in arm_records):.4f}; "
            f"{sum(r.get('seconds', 0.0) for r in arm_records):.0f}s")
    totals = _by_status(records)
    lines.append(
        f"total: {len(records)} units, "
        f"${sum(r.get('cost', 0.0) for r in records):.4f} spent, "
        f"${sum(r.get('unreconciled_liability', 0.0) for r in records):.4f} "
        f"unreconciled liability, "
        f"{sum(r.get('seconds', 0.0) for r in records):.0f}s wall clock")
    lines.append("statuses: " + ", ".join(
        f"{count} {status}" for status, count
        in sorted(totals.items())))
    return "\n".join(lines)


def export_tier4_reading_sheet(
        records: list[dict[str, Any]],
        questions: dict[str, dict[str, Any]],
        path: Path,
        seed: int,
        mode: str) -> dict[str, Any]:
    """The tier-4 reading sheet: one entry per answered unit, in a
    seeded order, with no arm label.

    The pilot is read by the advisor alone (D52 §5); the sheet is
    still arm-blind — nothing on it names the arm that produced an
    entry, so a reading cannot lean on the arm. Each entry carries
    everything a reading needs: the question's id, its family, its
    request, its requirement statements (the statements the reading
    grades the answer against), and the delivered answer. The tier-3
    sheet samples because its plans run hundreds of units; the tier-4
    plans run at most sixteen, so every answered unit is an entry.
    """
    answered = [record for record in records
                if record.get("answer")]
    entries: list[dict[str, Any]] = []
    for record in answered:
        candidate = questions[record["question_id"]]
        entries.append({
            "question_id": record["question_id"],
            "family": candidate["family"],
            "request": candidate["request"],
            "requirement_statements": [
                {"id": requirement["id"],
                 "statement": requirement["statement"]}
                for requirement in candidate.get(
                    "requirements", [])],
            "answer": record.get("answer"),
            "reading_1": None,
            "reading_2": None,
            "resolution": None,
        })
    # The seeded order, and no arm label: the readers see the sheet,
    # not the experiment.
    random.Random(seed).shuffle(entries)
    sheet = {
        "record": "reading-sheet",
        "mode": mode,
        "seed": seed,
        "units": len(entries),
        "entries": [
            {"entry": index, **entry}
            for index, entry in enumerate(entries, 1)],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sheet, indent=2, default=str) + "\n",
                    encoding="utf-8")
    return sheet


# ── The mocked dry run ────────────────────────────────────
#
# The dry run runs the real machinery — the freeze guard, the gates,
# the plan and its order, the arm executors, the deadline, the
# fit-rule budget, the records, the reading sheet — with the
# model-serving layer mocked: a scripted client for arms A and D
# (D-pages included), a fixture catalogue, and a stand-in at the
# pipeline boundary for arms E and F. No network, no spend.

# The mock lineup: serving names that are placeholders, not model ids
# (non-negotiable 6) — the tier-3 dry run's own, since the tier-4 run
# runs under the same ratified pins.
DRY_RUN_SERVINGS = {
    "A": "dryrun/arm-a",
    "B": "dryrun/arm-a",
    "C": ["dryrun/arm-c-1", "dryrun/arm-c-2"],
    "D": "dryrun/arm-d",
    "E": {tier: f"dryrun/{tier}" for tier in tier3.PIPELINE_TIERS},
}

# The dry run's fixture credit: a balance above every mode's
# registered ceiling, so the preflight's credit check passes without
# a network GET — the dry run makes no real call.
DRY_RUN_CREDIT = 100.00

# The fixture catalogue's rates, per token (the tier-3 dry run's own
# constants, named here so the scripted token counts are priced at
# exactly these figures in two places).
DRY_RUN_PROMPT_RATE = tier3.DRY_RUN_PROMPT_RATE
DRY_RUN_COMPLETION_RATE = tier3.DRY_RUN_COMPLETION_RATE


def _dry_run_answer(question_id: str) -> str:
    """The dry run's stand-in answer: visibly a stand-in, never a
    claim about the batch's answers (the frozen batch has no recorded
    answers — tier 4 is the capacity test's first run)."""
    return (f"dry-run stand-in answer for {question_id}: the scripted "
            "default of the mocked dry run, not a serving's answer")


def _ceiling_call(ceiling: float, answer: str) -> dict[str, Any]:
    """A single call that bills a hair under the given ceiling (the
    pilot dry run's default): the token counts the fixture's rates
    turn into the ceiling, so the client's own accounting books the
    figure the fit rule budgeted for the unit."""
    prompt_tokens = int(ceiling * 0.999 / DRY_RUN_PROMPT_RATE)
    return {"content": answer, "finish_reason": "stop",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": 0}


def _at_tier4_ceiling(arm: str, answer: str) -> dict[str, Any]:
    """A pipeline run that used a hair under its per-unit ceiling (the
    pilot dry run's E and F default): the workflow's own profile,
    priced at the tier-4 ceiling with the tiers' shares held."""
    outcome = _shipped(
        answer, profile=("verify-first" if arm == "F" else "standing"))
    ceiling = TIER4_CEILINGS[arm] * 0.999
    scale = ceiling / outcome["cost"]
    outcome["cost"] = ceiling
    outcome["cost_by_tier"] = {
        tier: round(amount * scale, 6)
        for tier, amount in outcome["cost_by_tier"].items()}
    return outcome


def _budget_stop_call(answer: str,
                      authorization: float) -> dict[str, Any]:
    """A call that books just under the mode's authorization (the
    calibration budget-stop exhibit): one call whose booked cost takes
    the sweep to the authorization's edge, so the client's own
    post-call check raises BudgetExceeded against the unit's per-unit
    ceiling — the unit ends incomplete at the booked figure, the sweep
    books it, and every unit after it fails the fit rule."""
    prompt_tokens = 900
    completion_tokens = int(
        (authorization * 0.999
         - prompt_tokens * DRY_RUN_PROMPT_RATE)
        / DRY_RUN_COMPLETION_RATE)
    return {"content": answer, "finish_reason": "stop",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens}


def _default_call(question_id: str) -> dict[str, Any]:
    """The dry run's default single call: the stand-in answer at the
    fixture's default token counts."""
    return _answer_call(_dry_run_answer(question_id))


def build_calibration_dry_run_script() -> tier3.DryRunScript:
    """The calibration dry run's script: the nine units' defaults —
    every unit answers its stand-in answer through its arm's
    registered treatment — then the failure-class exhibits the command
    orders, one of each, each keyed to a unit the calibration's plan
    actually runs:

    * a refusal (T4-03, 1, A): a serving that chose to answer
      nothing — its empty reply still bills the call;
    * a deadline (T4-04, 1, D): a call that outlasts the unit's
      shortened deadline, cancelled by the runner's wait_for before
      anything is booked;
    * a provider failure (T4-05, 1, D): a serving that consumed its
      budget and emitted nothing, after dispatch, booked the way the
      real client books a failed call;
    * a budget stop (T4-02, 1, D): one call booking just under the
      $2.00 authorization, which the unit's own $0.30 ceiling
      refuses after the call — the sweep books the booked figure and
      the fit rule stops every unit after it.
    """
    script = tier3.DryRunScript()
    for unit_key in calibration_plan():
        question_id, _repetition, arm = tuple(unit_key)
        script._calls[tuple(unit_key)] = [
            _default_call(question_id)]
    # The failure-class exhibits, one each.
    script._calls[("T4-03", 1, "A")] = [_answer_call("")]
    script._calls[("T4-04", 1, "D")] = [
        _answer_call(_dry_run_answer("T4-04"), sleep=0.25)]
    script._deadlines[("T4-04", 1, "D")] = 0.05
    script._calls[("T4-05", 1, "D")] = [
        _provider_failure_call(
            "scripted: the serving consumed its budget and "
            "emitted nothing")]
    script._calls[("T4-02", 1, "D")] = [
        _budget_stop_call(_dry_run_answer("T4-02"),
                          CALIBRATION_CEILING)]
    return script


def build_pilot_dry_run_script() -> tier3.DryRunScript:
    """The pilot dry run's script: every unit of the pilot's plan
    books a hair under its per-unit ceiling — the dry run exercises
    the sweep's fit rule at the registered ceilings — then the
    failure-class exhibits, one of each, keyed to units the plan
    runs:

    * a deadline (T4-03, 1, A), a refusal (T4-02, 1, A) and a
      provider failure (T4-04, 1, D), each as the calibration's are;
    * a budget stop, composed: the ceiling-tail defaults exhaust the
      $5.00 authorization inside the plan, so the units after the
      crossing skip through the fit rule — the budget-stop class on
      the real rule, at the registered ceilings.
    """
    script = tier3.DryRunScript()
    order, _refusals = pilot_plan(
        ["T4-02", "T4-03", "T4-04", "T4-06"])
    for unit_key in order:
        question_id, _repetition, arm = tuple(unit_key)
        if arm in ("A", "D", "D-pages"):
            script._calls[tuple(unit_key)] = [
                _ceiling_call(TIER4_CEILINGS[
                    ceiling_key(arm)],
                    _dry_run_answer(question_id))]
        else:
            scenario_id = f"tier4_{arm.lower()}_{question_id}_r1"
            if arm == "F":
                script._arm_f[scenario_id] = _at_tier4_ceiling(
                    "F", _dry_run_answer(question_id))
            else:
                script._arm_e[scenario_id] = _at_tier4_ceiling(
                    "E", _dry_run_answer(question_id))
    # The failure-class exhibits, one each.
    script._calls[("T4-03", 1, "A")] = [
        _answer_call(_dry_run_answer("T4-03"), sleep=0.25)]
    script._deadlines[("T4-03", 1, "A")] = 0.05
    script._calls[("T4-02", 1, "A")] = [_answer_call("")]
    script._calls[("T4-04", 1, "D")] = [
        _provider_failure_call(
            "scripted: the serving consumed its budget and "
            "emitted nothing")]
    return script


class Tier4DryRunScenarioRunner(tier3.DryRunScenarioRunner):
    """The dry run's stand-in at the pipeline boundary for arms E
    and F, at the tier-4 scenario ids.

    Everything above this boundary is the real machinery — the unit's
    place in the order, the deadline, the delivery reader, the
    accounting, the record. The pipeline's own execution is replaced
    by scripted ScenarioRun rows, the same way the dry run's client
    replaces the model servings for arms A and D: the dry run proves
    the experiment's machinery, and the pipeline itself is proven by
    the harness's own suite. The budget's fit rule is the real one,
    and the scripted cost is booked to it exactly as run_scenario
    books a real run's.
    """

    async def __call__(self, scenario, spec, client_factory,
                       settings_lookup_dict,
                       timeout: float = tier3.DEADLINE_SECONDS,
                       max_spend: float | None = None,
                       budget: SweepBudget | None = None,
                       ) -> Any:
        if budget is not None and not budget.can_start(max_spend):
            return tier3.ScenarioRun(
                scenario=scenario, results=[], calls=0,
                seconds=0.0, error=budget.skip(max_spend),
                was_skipped=True)
        # The scenario's id names its arm and its experiment:
        # tier4_f_* runs the verify-first workflow, tier4_e_* the
        # standing one.
        if scenario.id.startswith("tier4_f_"):
            outcome = self._script.arm_f_outcome(scenario.id)
        else:
            outcome = self._script.arm_e_outcome(scenario.id)
        if budget is not None:
            budget.record(outcome.get("cost", 0.0))
        return tier3.ScenarioRun(
            scenario=scenario, results=[],
            calls=outcome.get("calls", 0),
            seconds=outcome.get("seconds", 0.0),
            cost=outcome.get("cost", 0.0),
            error=outcome.get("error"),
            cost_by_tier=outcome.get("cost_by_tier", {}),
            calls_by_tier=outcome.get("calls_by_tier", {}),
            providers_by_tier=outcome.get("providers_by_tier", {}),
            verdicts=outcome.get("verdicts", {}),
            status=outcome.get("status", ""),
            # The bound's two fields (D23), carried like every other
            # row the stand-in can express.
            reason=outcome.get("reason"),
            stop_reason=outcome.get("stop_reason"),
            iterations=outcome.get("iterations", []),
            watchdog=outcome.get("watchdog"),
            tokens_by_tier=outcome.get("tokens_by_tier", {}),
            retries=outcome.get("retries", {}),
            candidate=outcome.get("candidate"),
            normalised_by_kind=outcome.get(
                "normalised_by_kind", {}))


async def _tier4_dry_run_mode(
        mode: str, script: tier3.DryRunScript,
        question_ids: list[str] | None = None,
        ) -> dict[str, Any]:
    """One mode's mocked dry run: the real runner, the mocked
    serving layer, the mode's own authorization pin (R4 — the pin
    names the mode's own registered ceiling), at zero spend."""
    servings = DRY_RUN_SERVINGS
    fingerprint = _servings_fingerprint(servings)
    authorization = (CALIBRATION_CEILING if mode == "calibration"
                     else PILOT_CEILING)
    overrides = {
        "TIER3_ARM_A": servings["A"],
        "TIER3_ARM_B": servings["B"],
        "TIER3_ARM_C_1": servings["C"][0],
        "TIER3_ARM_C_2": servings["C"][1],
        "TIER3_ARM_D": servings["D"],
        "TIER3_SERVINGS_RATIFIED": fingerprint,
        "TIER3_SPEND_AUTHORIZED": f"{authorization:.2f}",
    }
    catalogue = _dry_run_catalogue(servings)
    rates = {entry["id"]: (
        float(entry["pricing"]["prompt"]),
        float(entry["pricing"]["completion"]))
        for entry in catalogue}
    deadline_overrides = {
        key: seconds for key, seconds in script._deadlines.items()}
    context = tier3._DryRunContext()
    path = RESULTS_DIR / f"dryrun-tier4-{mode}.jsonl"
    with _env_overrides(overrides), \
            _harness_pin_overrides(servings["E"]):
        _install_rates(catalogue)
        client_factory = _dry_run_client_factory(
            script, rates, context)
        tool_dispatcher = _dry_run_tool_dispatcher(script, context)
        scenario_runner = Tier4DryRunScenarioRunner(script)
        return await run_tier4_experiment(
            mode, question_ids=question_ids,
            results_path=path,
            client_factory=client_factory,
            tool_dispatcher=tool_dispatcher,
            scenario_runner=scenario_runner,
            catalogue=catalogue,
            credit=DRY_RUN_CREDIT,
            deadline_overrides=deadline_overrides)


def _install_rates(catalogue: list[dict[str, Any]]) -> int:
    """The fixture's rates into the client's own pricing table (the
    tier-3 dry run's own installer, so the guard the dry run's calls
    pass through is the real one)."""
    return tier3._install_dry_run_rates(catalogue)


async def tier4_dry_run() -> dict[str, Any]:
    """The mocked dry runs of both modes (the command's acceptance
    criterion (f)): the calibration's nine units and the pilot's
    sixteen, through the real runner with mocked clients — no
    network, no spend.

    Every failure class the command names is included at least once
    per mode: a refusal, a deadline, a provider failure, and a
    budget stop (the calibration's booked by one call that takes the
    sweep to the authorization's edge; the pilot's composed by the
    ceiling-tail defaults exhausting the authorization inside the
    plan). The reading sheet is generated for each mode from its own
    records, arm-blind, one entry per answered unit.
    """
    calibration = await _tier4_dry_run_mode(
        "calibration", build_calibration_dry_run_script())
    pilot = await _tier4_dry_run_mode(
        "pilot", build_pilot_dry_run_script(),
        question_ids=["T4-02", "T4-03", "T4-04", "T4-06"])
    sheets: dict[str, dict[str, Any]] = {}
    for mode, result in (("calibration", calibration),
                         ("pilot", pilot)):
        sheet_path = RESULTS_DIR / f"dryrun-tier4-{mode}.sheet.json"
        sheets[mode] = export_tier4_reading_sheet(
            result["records"], result["questions"],
            sheet_path, result["seed"], mode)
    return {"calibration": calibration, "pilot": pilot,
            "reading_sheets": sheets}


# ── The CLI ─────────────────────────────────────────────

def _print_preflight_findings(report: PreflightReport) -> None:
    for refusal in report.refusals:
        print(f"[REFUSE] {refusal}")
    for note in report.reports:
        print(f"[report] {note}")


def _print_worst_case(arm: str, rows: list[dict[str, Any]],
                      ceiling: float) -> None:
    """The worst-case table, one line per tier — arm E's standing
    tiers, or arm F's verify-first call counts on them (with the
    whole sequence's worst case as its last line)."""
    for row in rows:
        if row.get("unknown"):
            print(f"arm {arm}/{row['tier']}: {row['serving']} — "
                  f"no worst case the guard can bound: "
                  f"{row.get('reason')}")
            continue
        refusal = ("refused even at zero spend"
                   if row["refuses_even_at_zero_spend"]
                   else f"refusable above spend "
                        f"${row['refusable_above_spend']:.4f}")
        priced_as = row.get("priced_as", row["serving"])
        priced = (f", priced as {priced_as} "
                  f"(variant suffix resolved)"
                  if priced_as != row["serving"] else "")
        charge = (f"a per-request charge "
                  f"${row['per_request_charge']:.4f} added "
                  f"once per call; "
                  if row.get("per_request_charge") else "")
        if row["tier"] == "sequence":
            print(
                f"arm {arm}/sequence: {row['calls']} calls "
                f"({row['serving']}) — worst case "
                f"${row['worst_case']:.4f} against the "
                f"${ceiling:.2f} per-unit ceiling ({refusal})")
            continue
        calls = row.get("calls")
        on_tier = (f" — the workflow's {calls} calls on "
                   f"this tier: ${row['tier_worst_case']:.4f}"
                   if calls is not None else "")
        print(
            f"arm {arm}/{row['tier']}: {row['serving']}{priced} — "
            f"standing cap {row['cap']}, worst case per call "
            f"${row['worst_case']:.4f}{on_tier} against the "
            f"${ceiling:.2f} per-unit ceiling "
            f"({refusal}; {charge}the prompt side is the largest "
            f"question, a floor — the guard computes the real "
            f"bytes at call time)")


def _mode_and_ids(args: argparse.Namespace
                  ) -> tuple[str, list[str] | None]:
    """The CLI's mode and its named ids: the calibration names none,
    the pilot names its question ids."""
    mode = args.mode
    if mode == "calibration":
        return mode, None
    ids = [question_id.strip()
           for question_id in (args.ids or "").split(",")
           if question_id.strip()]
    return mode, ids


async def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tier4-runner",
        description="The tier-4 pilot runner "
                    "(Ruling D52, command "
                    "ARCH-20261017-122)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
            ("preflight", "the freeze guard, the gates and the free "
                          "preflight, before any paid call"),
            ("plan", "the mode's plan: its units and the order's "
                     "digest (free)"),
            ("run", "the mode's run (paid)")):
        command_p = sub.add_parser(name, help=help_text)
        command_p.add_argument(
            "mode", choices=("calibration", "pilot"),
            help="the mode: calibration ($2.00, nine units) or "
                 "pilot ($5.00, the named question ids x their "
                 "family's arms)")
        command_p.add_argument(
            "--ids", default=None, metavar="IDS",
            help="pilot only: the comma-separated question ids from "
                 "the frozen batch (at most four)")
        command_p.add_argument("--results-file", default=None,
                               metavar="PATH")
    sub.add_parser("worst-case",
                   help="the per-arm worst-case tables at the fixture "
                        "catalogue's shape (free)")
    sub.add_parser("dry-run",
                   help="the mocked dry runs of both modes (free)")
    sheet_p = sub.add_parser(
        "reading-sheet",
        help="export the reading sheet from a results file")
    sheet_p.add_argument("results_file", metavar="RESULTS_FILE")
    args = parser.parse_args(argv)

    if args.command == "reading-sheet":
        path = Path(args.results_file)
        records = [json.loads(line)
                   for line in path.read_text(
                       encoding="utf-8").splitlines()
                   if line.strip()]
        unit_records = [record for record in records
                        if record.get("record") == "unit"]
        header = (records[0] if records else {})
        questions = candidate_index()
        mode = header.get("mode", "pilot")
        seed = header.get("seed", PILOT_SEED)
        sheet = export_tier4_reading_sheet(
            unit_records, questions,
            path.with_suffix(".sheet.json"), seed, mode)
        print(f"reading sheet: {sheet['units']} answered units, "
              f"seed {seed}, written to "
              f"{path.with_suffix('.sheet.json')}")
        return 0

    if args.command == "worst-case":
        # The fixture catalogue's shape, so the table is readable
        # without a network call; a real preflight reads the live
        # catalogue's own rates.
        catalogue = _dry_run_catalogue(DRY_RUN_SERVINGS)
        floor = prompt_floor(mode_arms("pilot"), candidate_index())
        print("arm A: one call — worst case per call and per unit "
              "are the same figure (a single-call arm)")
        index = _catalogue_index(catalogue)
        for arm in ("A", "D", "D-pages"):
            floor_message = max(
                (model_visible_message(arm, candidate)
                 for candidate in candidate_index().values()),
                key=lambda text: len(text.encode("utf-8")))
            worst = _single_call_worst_case(arm, floor_message, DRY_RUN_SERVINGS, index)
            print(f"arm {arm}: one call, the largest message the "
                  f"batch carries — worst case ${worst:.4f} against "
                  f"the ${TIER4_CEILINGS[ceiling_key(arm)]:.2f} "
                  f"per-unit ceiling")
        print("arm F, at the tier-4 prompt floor and the $0.40 "
              "per-unit ceiling:")
        _print_worst_case("F", tier3.arm_f_worst_case(
            DRY_RUN_SERVINGS, catalogue, prompt_floor=floor,
            unit_ceiling=TIER4_CEILINGS["F"]),
            TIER4_CEILINGS["F"])
        print("arm E, at the tier-4 prompt floor and the $1.50 "
              "per-unit ceiling:")
        _print_worst_case("E", tier3.arm_e_worst_case(
            DRY_RUN_SERVINGS, catalogue, prompt_floor=floor,
            unit_ceiling=TIER4_CEILINGS["E"]),
            TIER4_CEILINGS["E"])
        return 0

    if args.command == "plan":
        mode, question_ids = _mode_and_ids(args)
        order = (calibration_plan() if mode == "calibration"
                 else pilot_plan(question_ids or [])[0])
        print(f"the {mode}'s plan: {len(order)} units, seed "
              f"{(CALIBRATION_SEED if mode == 'calibration' else PILOT_SEED)}, "
              f"order sha256 {_order_digest(order)}")
        for unit_key in order:
            print(f"  {unit_key[0]} r{unit_key[1]} arm {unit_key[2]}")
        return 0

    if args.command == "dry-run":
        result = await tier4_dry_run()
        for mode in ("calibration", "pilot"):
            outcome = result[mode]
            print(outcome["summary"])
            print(f"records: {outcome['path']}")
        return 0

    # preflight and run share the gate-and-preflight path.
    mode, question_ids = _mode_and_ids(args)
    tier3_settings = Tier3Settings()
    servings = _resolve_servings(tier3_settings)
    fingerprint = _servings_fingerprint(servings)
    authorization = (CALIBRATION_CEILING if mode == "calibration"
                     else PILOT_CEILING)
    print("servings map:")
    print(json.dumps(servings, indent=2, sort_keys=True))
    print(f"servings fingerprint: {fingerprint}\n")
    freeze = check_freeze()
    if freeze:
        print("the freeze guard refused to start — the batch on "
              "disk is not the frozen batch the evidence registered:")
        for refusal in freeze:
            print(f"  [FREEZE] {refusal}")
        return REFUSED_EXIT
    print("the freeze guard holds\n")
    missing = tier4_gate_report(
        tier3_settings, servings, fingerprint, authorization, mode)
    if missing:
        print("the ratification gates are not cleared — refusing "
              "before any network call:")
        for gate in missing:
            print(f"  [GATE] {gate}")
        return REFUSED_EXIT
    print("the ratification gates hold\n")
    if mode == "pilot" and not question_ids:
        print("the pilot names no question ids: --ids names at most "
              f"{PILOT_ID_LIMIT} question ids from the frozen batch "
              "(e.g. --ids T4-02,T4-03,T4-04,T4-06)")
        return REFUSED_EXIT
    catalogue = await _fetch_catalogue(
        confirm={serving for serving in _all_servings(servings)})
    report = tier4_preflight(
        servings, catalogue, credit=await _fetch_credit(),
        ceiling=authorization,
        arms=(tuple(sorted(
            {unit[2] for unit in (
                calibration_plan() if mode == "calibration"
                else pilot_plan(question_ids)[0])}))),
        questions=(candidate_index() if mode == "calibration"
                   else {question_id: candidate
                         for question_id, candidate
                         in candidate_index().items()
                         if question_id in set(question_ids)}))
    _print_preflight_findings(report)
    if report.refusals:
        return REFUSED_EXIT
    if args.command == "preflight":
        return 0
    result = await run_tier4_experiment(
        mode, question_ids=question_ids,
        results_path=args.results_file)
    print(result["summary"])
    print(f"records: {result['path']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_cli(argv))


if __name__ == "__main__":
    raise SystemExit(main())
