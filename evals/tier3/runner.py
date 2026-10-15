"""The tier-3 experiment runner (ARCH-20261003-119).

This is the machinery the frozen manifest (evals/tier3/manifest.json,
tier3-4, the owner's staged plan) describes and tier3-1 registered
under ``not_prepared_here``: the plan builder with its recorded seed,
the servings map and its ratification fingerprint, the free preflight,
the five arm executors under their registered treatments, the
closed-world source tool and the whitelisted recompute, arm C's
typed check, the append-only results log with resume, the reading
sheet, and the five success measures computed both ways (Ruling D50
(1): the scorer is the screen, two hand readings are the primary
measure).

Nothing starts until the three ratification gates hold — every
arm's serving resolved, arm E's per tier, printed with a
fingerprint the owner ratifies (G-2); arm B's pin equal to arm
A's; and the spend authorization. The gates are checked before any
network call, and a refusal names each missing gate. Every unit
runs inside ``_isolated_store()`` under the common 1800-second
deadline, and every failure class the manifest names is counted in
its arm's 21-unit denominator, never dropped.

    python3 evals/tier3/runner.py preflight      # free: gates, catalogue, preflight
    python3 evals/tier3/runner.py worst-case     # free: the arm-E worst-case table
    python3 evals/tier3/runner.py run            # the 105-unit stage-1 main run (paid)
    python3 evals/tier3/runner.py pilot          # the 50-unit calibration pilot (paid)
    python3 evals/tier3/runner.py dry-run        # the mocked dry runs (free)
    python3 evals/tier3/runner.py reading-sheet RESULTS_FILE

The dry run is free by construction: mocked clients, a fixture
catalogue, and a stand-in at the pipeline boundary for arm E. The
main run and the pilot are paid execution and are not part of
ARCH-20261003-119.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import contextlib
import copy
import functools
import hashlib
import json
import math
import os
import random
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

# The repository root and the two sibling packages this runner
# consumes (the frozen tier-2 scorer and the golden delivery
# reader) are imported by path, the way the tier-2 probes do it:
# evals/ is not an installed package.
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TIER3 = Path(__file__).resolve().parent
TIER2 = ROOT / "evals" / "tier2"
GOLDEN = ROOT / "evals" / "golden"
PROMPTS = TIER3 / "prompts"
SOURCES = TIER2 / "sources"
RESULTS_DIR = ROOT / "evals" / "results"
for _path in (str(TIER2), str(GOLDEN)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import scorer                                    # noqa: E402 — the frozen tier-2 scorer (D50 (1): the screen)
import regression_12                             # noqa: E402 — the recorded real answers, read from the traces
from score_trace import answer_of                # noqa: E402 — arm E's delivery reader (D50 (3))

from autornd.config import settings as harness_settings  # noqa: E402
from autornd.config import settings_lookup         # noqa: E402
from autornd.evals.runner import (                 # noqa: E402
    SweepBudget,
    ScenarioRun,
    _durable_mirror,
    _isolated_store,
    run_scenario,
)
from autornd.evals.scenario import Scenario        # noqa: E402
from autornd.routing.openrouter import (           # noqa: E402
    CHAT_TEMPLATE_ALLOWANCE_BYTES,
    BudgetExceeded,
    ModelResponse,
    OpenRouterClient,
    ProviderFailure,
    SpendGuardRefused,
    _failure_kind,
    _prompt_bytes,
)

__all__ = [
    "ARM_CEILINGS", "ARM_F_CALL_LIMIT", "ARMS",
    "DEADLINE_SECONDS", "DRY_RUN_PROMPT_RATE",
    "DRY_RUN_COMPLETION_RATE", "PILOT_ARMS",
    "PILOT_CEILING", "PILOT_SEED", "PILOT_REPETITIONS",
    "REGISTERED_MAX_TOKENS", "REGISTERED_TEMPERATURE",
    "REMEASURE_ARMS", "REMEASURE_CEILING",
    "REMEASURE_SEED", "SELECTION_SEED", "SEED",
    "STAGE1_QUESTION_IDS",
    "REPITIONS", "MAIN_CEILING",
    "CooperationCheckVerdict", "DryRunScript",
    "ExperimentRefused",
    "PreflightReport", "Tier3ResultsLog", "Tier3Settings",
    "UnitResult",
    "arm_e_worst_case", "arm_f_worst_case",
    "build_order", "build_remeasure_script",
    "compute_measures",
    "default_results_path", "dry_run", "export_reading_sheet",
    "fetch_catalogue", "fetch_primary_source", "gate_report",
    "merge_readings", "order_digest", "parse_check_verdict",
    "recompute", "remeasure_order", "remeasure_report",
    "render_prompt", "resolve_servings", "run_experiment",
    "run_preflight", "run_unit", "servings_fingerprint",
    "stage1_questions",
    "summarize", "worst_case_cost",
]

# ── The registered plan (the manifest, tier3-4) ───────────────────
#
# Every constant here is a registered parameter: a value a unit's
# outcome depends on, so it is named in the manifest and the results
# header rather than buried in a call site.

ARMS = ("A", "B", "C", "D", "E")
PILOT_ARMS = ("A", "D")
SEED = 20261003
PILOT_SEED = 20261004
REPITIONS = 3
PILOT_REPETITIONS = 1
DEADLINE_SECONDS = 1800.0

# The per-unit authorization ceilings the manifest registers.
# For the staged plan's stage 1 they compose to the $37.80
# compositional ceiling (21 units per arm); the owner's
# ratified amount, which the spend gate enforces and the
# sweep's cap carries, is $30.00 (MAIN_CEILING below). The
# pilot composes to the $7.50 pilot authorization (25 units
# per pilot arm). The re-measurement's ceilings compose to
# $48.00 (75 + 75 + 75 + 21 units at $0.10/$0.20/$0.20/
# $0.50) against the owner's $15.00 authorization
# (REMEASURE_CEILING below).
ARM_CEILINGS = {"A": 0.10, "B": 0.50, "C": 0.50, "D": 0.20,
                "E": 0.50, "F": 0.20}
MAIN_CEILING = 30.00
PILOT_CEILING = 7.50

# The D51 re-measurement (command ARCH-20261014-121, the
# manifest's tier3-8 registration): arms A, D and F on all
# 25 questions x 3 repetitions and the D51 pipeline (E') on
# stage 1's seven x 3 - 246 units, 75 + 75 + 75 + 21,
# interleaved under order seed 20261014, under the owner's
# $15.00 authorisation (2026-10-14, 'ok on spend'). Arms B
# and C do not run. Arm F is Ruling D51 (8)'s verify-first
# workflow through arm E's path; arm E' is arm E unchanged -
# the standing workflow, which after #176 is D51's
# engineering-rnd.
REMEASURE_ARMS = ("A", "D", "F", "E")
REMEASURE_SEED = 20261014
REMEASURE_CEILING = 15.00
# Arm F's call bound: triage and asks, then at most 4 model
# calls after them (answer, check, revision, check) - the
# verify-first workflow's own max_iterations: 2 bound, which
# no .env line can widen.
ARM_F_CALL_LIMIT = 6

# The stage-1 question selection (the owner's 2026-10-05
# directive, registered in the manifest as tier3-4): the
# selection rule's seed and the ids it selected, fixed by
# rule before any run. The rule itself is stage1_questions()
# below; the manifest records the seed and the ids, and the
# guard test (tests/test_tier3_manifest.py) reconstructs the
# selection from the rule independently and fails under a
# different seed.
SELECTION_SEED = 20261005
STAGE1_QUESTION_IDS = ("Q6", "Q10", "Q14", "Q15",
                       "Q16", "Q17", "Q23")

# The registered call parameters for arms A-D. 8000 is more than
# 3x the largest completion 107's direct calls used; the client's
# default temperature is 0.3. Arm E runs on the pipeline's own
# standing caps.
REGISTERED_MAX_TOKENS = 8000
REGISTERED_TEMPERATURE = 0.3

# The registered treatment bounds. Arm B: at most 3 model
# calls and 20 tool invocations per unit; calls 1 and 2
# offer the tools, call 3 keeps them declared with
# tool_choice "none". Arm C: 3 calls as a hard
# whole-sequence bound, with the check's bounded retries
# inside it.
ARM_B_CALL_LIMIT = 3
ARM_B_TOOL_INVOCATION_LIMIT = 20
ARM_C_CALL_LIMIT = 3
ARM_C_CHECK_ATTEMPTS = 2
ARM_E_CALL_LIMIT = 40

# D45 amendment (b) retired the harness's CHARS_PER_TOKEN: the
# spend guard bounds a prompt by its UTF-8 byte length, which a
# byte-level tokenizer never exceeds, so the preflight's capacity
# checks use bytes as the token bound and register no constant. The
# one place a constant is unavoidable is text the MODEL produced
# (arm C's draft, re-read in the next prompt): its byte length is
# bounded by nothing the caller holds, so it is estimated at the
# repo's established 4 bytes per token — the mean the retired
# constant used — registered here, not assumed.
DRAFT_BYTES_PER_TOKEN = 4

# The pipeline tiers arm E runs under, in the harness's own tier
# order (autornd/evals/cli.py's _tier_ceilings names the same set).
PIPELINE_TIERS = ("triage", "research", "search",
                  "architecture", "engineering", "judge", "escalation")

# The chat_json default the CLI registers for tiers with no node
# ceiling of their own (autornd/evals/cli.py: _CHAT_DEFAULT_MAX_TOKENS).
_CHAT_DEFAULT_MAX_TOKENS = 16384


# ── The experiment's own settings (the G-2 gate text) ─────────────
#
# "The runner reads TIER3_* the way the harness reads its settings
# (the environment, then its own env file), in its own settings
# class. autornd/config.py does not change."

class Tier3Settings(BaseSettings):
    """The experiment's pins and authorizations, read from
    the environment then .env.tier3 — the owner's to set
    (G-2, G-3).

    The pins live in their own file, not .env: the
    harness's settings forbid unknown keys, so a TIER3_*
    line in .env stops the harness at startup (measured:
    ValidationError, "Extra inputs are not permitted").
    .env.tier3 is git-ignored by the .env* rule
    (ARCH-20260930-097). The class declares only the
    TIER3_* pins; every other variable the environment
    and .env.tier3 carry (the harness's own settings, the
    credentials) is ignored — extra="ignore" — the way
    the harness's Settings ignores variables it does not
    declare. The experiment's settings never touch the
    harness's: ``autornd/config.py`` does not change."""

    model_config = SettingsConfigDict(
        env_file=None if os.environ.get("AUTORND_TESTING")
        else ".env.tier3",
        env_file_encoding="utf-8",
        extra="ignore")

    tier3_arm_a: str = ""
    tier3_arm_b: str = ""
    tier3_arm_c_1: str = ""
    tier3_arm_c_2: str = ""
    tier3_arm_d: str = ""
    tier3_servings_ratified: str = ""
    tier3_spend_authorized: str = ""
    tier3_pilot_authorized: str = ""


# ── The plan and its order ────────────────────────────────────────

def load_questions() -> list[dict[str, Any]]:
    """The frozen 25-question set (the tier-2 dataset, frozen at
    frozen-2026-10-03). Every arm receives exactly this text."""
    with open(TIER2 / "questions.json", encoding="utf-8") as handle:
        return json.load(handle)


def stage1_questions(
        questions: list[dict[str, Any]] | None = None,
        seed: int = SELECTION_SEED) -> list[dict[str, Any]]:
    """The stage-1 selection, the rule executed (the owner's
    2026-10-05 directive, specification 1, registered in the
    manifest as tier3-4): from the frozen set's Q6-Q25 only -
    Q1-Q5 are calibration-exposed (the 2026-10-03/04 golden
    probes answered them) and reserved for stage 2 - one
    question per shape (the five shapes the frozen set carries),
    then two more questions from two different shapes, all by
    ``random.Random(seed)``.

    The rule is fixed by rule before any run: the manifest
    records the seed and the seven ids it selects
    (STAGE1_QUESTION_IDS), and the guard test reconstructs the
    selection from the rule independently of this
    implementation, failing under a different seed. The seven
    are returned in frozen-set order - the order the plan's
    enumeration and the manifest's record both use.
    """
    frozen = load_questions() if questions is None else questions
    candidates = [q for q in frozen
                  if 6 <= int(q["id"][1:]) <= 25]
    by_shape: dict[str, list[dict[str, Any]]] = {}
    for question in candidates:
        by_shape.setdefault(question["shape"], []).append(question)
    rng = random.Random(seed)
    # Step 1 - one question per shape, the shapes in the
    # order they first appear in the frozen set.
    selected = [rng.choice(pool) for pool in by_shape.values()]
    # Step 2 - two more from two different shapes.
    for shape in rng.sample(list(by_shape), 2):
        taken = {q["id"] for q in selected}
        remaining = [q for q in by_shape[shape]
                     if q["id"] not in taken]
        selected.append(rng.choice(remaining))
    frozen_order = {q["id"]: i for i, q in enumerate(frozen)}
    return sorted(selected, key=lambda q: frozen_order[q["id"]])


def build_order(seed: int, repetitions: int,
                arms: tuple[str, ...],
                questions: list[dict[str, Any]] | None = None
                ) -> list[list[Any]]:
    """The manifest's interleaved order, executed rather than
    described: the units enumerated as (question_id, repetition, arm)
    with question_id in the frozen questions.json order, then
    ``random.Random(seed).shuffle`` over the list. No arm runs as a
    block, so time-of-day and serving-load confounds distribute
    across arms.

    The questions default to the frozen set (the pilot and a
    stage-2 run enumerate over their own sets); the staged
    plan's stage-1 main run enumerates over the seven
    selected questions (``stage1_questions()``), so the 105
    units are the plan's and the order's digest is the
    stage-1 plan's.

    The guard test (tests/test_tier3_manifest.py) reconstructs the
    order with the same comprehension and the same seed; this
    function is that reconstruction, and ``order_digest`` is the
    figure both sides compute.
    """
    units = [[question["id"], repetition, arm]
             for question in (load_questions()
                              if questions is None else questions)
             for repetition in range(1, repetitions + 1)
             for arm in arms]
    random.Random(seed).shuffle(units)
    return units


def order_digest(order: list[list[Any]]) -> str:
    """The sha256 of the order's canonical JSON — the figure the
    results header carries and the guard reconstructs."""
    canonical = json.dumps(order, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def remeasure_order(
        seed: int = REMEASURE_SEED,
        questions: list[dict[str, Any]] | None = None
        ) -> list[list[Any]]:
    """The re-measurement's interleaved order (the manifest's
    tier3-8 registration, the command's constraint): the 246
    units enumerated as (question_id, repetition, arm) - A, D
    and F over the frozen set's 25 questions in frozen-set
    order, repetition in 1..3, arm in A, D, F; then E' over
    the seven selected questions in frozen-set order,
    repetition in 1..3 - then ``random.Random(seed).shuffle``
    over the list. No arm runs as a block, so time-of-day and
    serving-load confounds distribute across arms.

    The guard test (tests/test_tier3_runner.py) reconstructs
    the order with the same enumeration and the same seed;
    ``order_digest`` is the figure both sides compute.
    """
    frozen = load_questions() if questions is None else questions
    units = [[question["id"], repetition, arm]
             for question in frozen
             for repetition in (1, 2, 3)
             for arm in ("A", "D", "F")]
    for question_id in STAGE1_QUESTION_IDS:
        for repetition in (1, 2, 3):
            units.append([question_id, repetition, "E"])
    random.Random(seed).shuffle(units)
    return units


# ── The servings map and its fingerprint (G-2) ────────────────────

def resolve_servings(tier3: Tier3Settings) -> dict[str, Any]:
    """Every arm's serving, arm E's per tier.

    Arm E's lineup is the owner's standing pins, resolved from the
    harness settings — the fingerprint shows it, and the choice is
    the owner's (G-2). This function builds the gate; it does not
    choose the lineup.
    """
    return {
        "A": tier3.tier3_arm_a,
        "B": tier3.tier3_arm_b,
        "C": [tier3.tier3_arm_c_1, tier3.tier3_arm_c_2],
        "D": tier3.tier3_arm_d,
        "E": {tier: getattr(harness_settings, f"model_{tier}", "")
              for tier in PIPELINE_TIERS},
    }


def servings_fingerprint(servings: dict[str, Any]) -> str:
    """The first 12 hex digits of the sha256 of the servings map's
    canonical JSON — the fingerprint the owner ratifies in one line
    (TIER3_SERVINGS_RATIFIED), arm E's tiers included."""
    canonical = json.dumps(servings, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def gate_report(tier3: Tier3Settings, servings: dict[str, Any],
                fingerprint: str, pilot: bool,
                mode: str = "main") -> list[str]:
    """The three ratification gates, as the missing ones.

    Empty means every gate holds. Each entry names one missing gate,
    so a refusal says exactly what the owner must set — before any
    network call (the command's gate text). The spend gate names
    the run's own authorization: the main run's $30.00, the pilot's
    $7.50, or the re-measurement's $15.00 (the manifest's tier3-8
    registration), each read from the TIER3_* pin the owner sets in
    .env.tier3.
    """
    missing: list[str] = []
    if not tier3.tier3_servings_ratified:
        missing.append("TIER3_SERVINGS_RATIFIED is not set")
    elif tier3.tier3_servings_ratified != fingerprint:
        missing.append(
            f"TIER3_SERVINGS_RATIFIED is {tier3.tier3_servings_ratified!r}, "
            f"which is not the servings map's fingerprint {fingerprint!r} "
            f"— the map below is what would run")
    if tier3.tier3_arm_b != tier3.tier3_arm_a:
        missing.append(
            "TIER3_ARM_B does not resolve to the same serving as "
            f"TIER3_ARM_A ({tier3.tier3_arm_b!r} vs {tier3.tier3_arm_a!r}) "
            "— arm B isolates the tool treatment, so the two pins must "
            "name the same serving")
    if mode == "remeasure":
        authorization = tier3.tier3_spend_authorized
        ceiling = REMEASURE_CEILING
        name = "TIER3_SPEND_AUTHORIZED"
        label = "re-measurement's"
    elif pilot:
        authorization = tier3.tier3_pilot_authorized
        ceiling = PILOT_CEILING
        name = "TIER3_PILOT_AUTHORIZED"
        label = "pilot's"
    else:
        authorization = tier3.tier3_spend_authorized
        ceiling = MAIN_CEILING
        name = "TIER3_SPEND_AUTHORIZED"
        label = "main run's"
    if not authorization:
        missing.append(f"{name} is not set")
    else:
        try:
            if float(authorization) < ceiling:
                missing.append(
                    f"{name} is {float(authorization):.2f}, below the "
                    f"{label} authorization ceiling ${ceiling:.2f}")
        except ValueError:
            missing.append(
                f"{name} is {authorization!r}, which is not a dollar "
                f"amount (the {label} is "
                f"authorized at ${ceiling:.2f})")
    return missing


# ── The catalogue (a free GET) ────────────────────────────────────

async def fetch_catalogue(
        confirm: set[str] | None = None) -> list[dict[str, Any]]:
    """The provider's public model catalogue. Free (non-negotiable 2):
    the same unauthenticated GET the harness's own preflight makes,
    so a tier id can be checked before a key exists.

    The bulk list does not carry every served id — the per-provider
    variants a pin can name are absent from it — so the ids the
    lineup names that the bulk list does not carry are confirmed
    individually against the per-model endpoint, the same discipline
    the client applies (autornd/routing/openrouter.py:
    _confirm_models), and a confirmed model's own object, pricing
    included, joins the catalogue. A 404 confirms the id is not
    served at all; a network fault leaves it unconfirmed — reported
    as missing, which is the honest answer when it could not be
    checked."""
    headers = {}
    if harness_settings.openrouter_api_key.strip():
        headers["Authorization"] = (
            f"Bearer {harness_settings.openrouter_api_key}")
    base = harness_settings.openrouter_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{base}/models", headers=headers)
        resp.raise_for_status()
        catalogue = resp.json().get("data", [])
    if confirm:
        listed = {entry["id"] for entry in catalogue}
        for model_id in sorted(confirm - listed):
            # The client's own confirmation (autornd/routing/
            # openrouter.py: _confirm_models): the per-model
            # endpoints endpoint returns 200 for a served id
            # whatever its modality, 404 for an unknown one.
            # It carries no pricing, so a confirmed miss is
            # served-but-unrated: the guard is blind for it
            # (D49: an unknown price is not free), which the
            # preflight and the worst-case table say so.
            try:
                async with httpx.AsyncClient(
                        timeout=15.0) as one_client:
                    resp = await one_client.get(
                        f"{base}/models/{model_id}/endpoints",
                        headers=headers)
                if resp.status_code == 200:
                    catalogue.append({
                        "id": model_id,
                        "pricing": {},
                        "confirmed_served": True})
            except Exception:
                continue        # unconfirmed, not absent
    return catalogue


# The catalogue's component classes, as the worst-case bound reads
# them — the same classes the client's guard applies
# (autornd/routing/openrouter.py:
# _prices_what_the_guard_cannot_bound; a test asserts the two
# agree).
_CACHE_COMPONENTS = ("input_cache_read", "input_cache_write")
_REASONING_COMPONENTS = ("internal_reasoning",)
_PER_REQUEST_COMPONENTS = ("web_search", "request")
_MODALITY_COMPONENTS = ("image", "audio", "input_audio_cache")


def catalogue_index(catalogue: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The catalogue keyed by model id."""
    return {entry["id"]: entry for entry in catalogue}


def _resolve_entry(index: dict[str, dict[str, Any]],
                   serving: str) -> dict[str, Any] | None:
    """The catalogue entry that prices a serving, or None when
    the catalogue carries neither the serving nor its base.

    A variant suffix (':exacto' among them) names a serving
    of the base model: the bulk catalogue prices the base
    entry, and the per-model endpoint confirms a variant is
    served but carries no pricing of its own, so a served
    variant is priced at its base entry's published price
    (D49: a known price is not an unknown one). Only an
    entry the catalogue actually carries resolves — an id
    the catalogue never listed and never confirmed stays
    "not in the provider catalogue", never a price borrowed
    for an id that may not be served at all."""
    entry = index.get(serving)
    if entry is None:
        return None
    if entry.get("pricing"):
        return entry
    base, separator, _variant = serving.rpartition(":")
    if separator:
        base_entry = index.get(base)
        if base_entry is not None and base_entry.get("pricing"):
            return base_entry
    return entry


def _unboundable_reason(entry: dict[str, Any]) -> str | None:
    """Why the guard cannot bound a call to this serving,
    or None when it can.

    The same test the client's own catalogue loader applies
    (autornd/routing/openrouter.py:
    _prices_what_the_guard_cannot_bound): a component the
    catalogue does not price is unknown, not free. The bound
    charges the prompt rate for every prompt byte and the
    completion rate for the whole output cap, so a component
    priced at or below the rate the bound already charges
    its side at cannot cost more than the bound does — the
    cache components against the prompt rate, reasoning
    against the completion rate — and a flat per-request
    charge is added once per request. The modality
    components (image, audio) never charge on the
    text-only calls this experiment makes. A component
    priced above the rate its side is charged at, or one
    the bound does not know, is a charge a token-only worst
    case understates. The states say which: served but not
    priced in the catalogue (confirmed via the per-model
    endpoint), a charge the bound cannot cover, and a
    priced entry with a missing side. An unknown price is
    not free (D49)."""
    pricing = entry.get("pricing") or {}
    if not pricing:
        if entry.get("confirmed_served"):
            return ("served but not priced in the catalogue "
                    "(confirmed via the per-model endpoint) — "
                    "the guard is blind for it")
        return "the catalogue entry carries no pricing"
    try:
        prompt = float(pricing.get("prompt"))
    except (TypeError, ValueError):
        prompt = None
    try:
        completion = float(pricing.get("completion"))
    except (TypeError, ValueError):
        completion = None
    charges = []
    for key, value in pricing.items():
        if key in ("prompt", "completion") or value in (None, ""):
            continue
        try:
            rate = float(value)
        except (TypeError, ValueError):
            charges.append(key)
            continue
        if key in _PER_REQUEST_COMPONENTS:
            continue          # added once per request
        if key in _MODALITY_COMPONENTS:
            continue          # text-only calls never carry them
        if key in _CACHE_COMPONENTS:
            if prompt is None or rate > prompt:
                charges.append(key)
            continue
        if key in _REASONING_COMPONENTS:
            if completion is None or rate > completion:
                charges.append(key)
            continue
        charges.append(key)   # a component the bound does not cover
    if charges:
        return ("carries charges beside prompt and completion "
                f"tokens ({', '.join(sorted(charges))}), which "
                "a token-only worst case understates — the guard "
                "is blind for it")
    if "prompt" not in pricing or "completion" not in pricing:
        return "the catalogue prices neither side of the call"
    return None


def _unpriced(entry: dict[str, Any]) -> bool:
    """Whether the guard cannot bound a call to this serving."""
    return _unboundable_reason(entry) is not None


class UnpricedServing(Exception):
    """A serving the catalogue does not price (D49: an
    unknown price is not free). The preflight refuses it
    as its own case; the worst-case table reports the
    tier as unboundable."""


def _rates(index: dict[str, dict[str, Any]], serving: str,
           where: str) -> tuple[float, float]:
    """The serving's (prompt, completion) rates, or an
    UnpricedServing when the catalogue cannot bound them."""
    entry = _resolve_entry(index, serving)
    if entry is None:
        raise UnpricedServing(
            f"{where}: the serving {serving!r} is not in "
            "the provider catalogue")
    if _unpriced(entry):
        raise UnpricedServing(
            f"{where}: the serving {serving} has no catalogue "
            "price the guard can bound (D49: an unknown price "
            "is not free)")
    pricing = entry["pricing"]
    return float(pricing["prompt"]), float(pricing["completion"])


def _per_request_charge(entry: dict[str, Any] | None) -> float:
    """The entry's flat per-request charge: the components
    the worst-case bound adds once per request the call can
    make. An entry the catalogue does not carry carries no
    charge, and an unparseable component is a charge the
    bound cannot read — unboundable, which _unboundable_reason
    has already said by the time any caller reaches this."""
    if entry is None:
        return 0.0
    pricing = entry.get("pricing") or {}
    total = 0.0
    for key in _PER_REQUEST_COMPONENTS:
        value = pricing.get(key)
        if value in (None, ""):
            continue
        try:
            total += float(value)
        except (TypeError, ValueError):
            continue
    return total


# ── The prompts and their rendering ───────────────────────────────

def prompt_text(arm: str) -> str:
    """The arm's prompt template, as the manifest registers it."""
    return (PROMPTS / f"arm_{arm.lower()}.md").read_text(encoding="utf-8")


def render_prompt(template: str, question: str) -> tuple[str, str]:
    """(system, user) for a single-call arm: everything before the
    QUESTION section is the system prompt, the rest the user message."""
    rendered = template.replace("{{QUESTION_TEXT}}", question)
    head, _, tail = rendered.partition("## QUESTION")
    return head.strip(), ("## QUESTION" + tail).strip()


def _stage_section(arm: str, heading: str) -> str:
    """One stage's text, from its heading to the next heading."""
    lines = prompt_text(arm).splitlines()
    start = next(i for i, line in enumerate(lines)
                 if line.startswith("## ") and heading in line)
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).strip()


def _stage_message(stage: str, question: str, draft: str | None,
                   objections: list[str] | None) -> tuple[str, str]:
    """(system, user) for one arm-C stage call: the stage's own
    text, the question, and the inputs that stage names — nothing
    else (D50 (4): each stage is a separate call that shows the
    model only its own stage's text, the question, and the inputs
    that stage names)."""
    head, _, _ = prompt_text("C").partition("## QUESTION")
    section = _stage_section("C", stage)
    if draft is not None:
        section = section.replace("{{MODEL_1_DRAFT}}", draft)
    if objections is not None:
        section = section.replace(
            "{{MODEL_2_OBJECTIONS}}",
            "\n".join(f"- {objection}" for objection in objections))
    user = f"## QUESTION\n\n{question}\n\n{section}"
    return head.strip(), user


# ── The worst case, at the guard's own formula ────────────────────

def worst_case_cost(prompt_rate: float, completion_rate: float,
                    prompt_bytes: int, max_tokens: int,
                    per_request_charge: float = 0.0) -> float:
    """The client's own pre-call guard formula (D45), as the owner's
    addition to this command directs: the worst case of one call at
    the given prompt size and output cap. The guard refuses the call
    when this exceeds what remains of the unit's ceiling. A flat
    per-request charge (a search surcharge among them) is added
    once: the call pays it whatever the token counts."""
    return ((prompt_bytes + CHAT_TEMPLATE_ALLOWANCE_BYTES) * prompt_rate
            + max_tokens * completion_rate + per_request_charge)


def _largest_question() -> str:
    """The largest question the plan carries, by UTF-8 byte length."""
    return max((q["question"] for q in load_questions()),
               key=lambda text: len(text.encode("utf-8")))


@functools.lru_cache(maxsize=1)
def _largest_tool_result() -> str:
    """The largest archived source — arm B's largest possible tool
    result, which the preflight's worst case includes."""
    texts = [path.read_text(encoding="utf-8")
             for path in sorted(SOURCES.glob("CFR-*.txt"))]
    return max(texts, key=len) if texts else ""


def _arm_servings(arm: str, servings: dict[str, Any]) -> list[str]:
    """The servings an arm's calls name."""
    if arm == "C":
        return list(servings["C"])
    if arm == "E":
        return list(servings["E"].values())
    return [servings[arm]]


def _arm_sequence_worst_case(arm: str, servings: dict[str, Any],
                             index: dict[str, dict[str, Any]]) -> tuple[float, int]:
    """(the whole call sequence's worst case, the call limit).

    The command's refusal case 1: the call limit times each call's
    worst case at the registered max_tokens, with the largest prompt
    the call can carry, arm B's largest tool result included. Arm C's
    largest call is the check, which carries model 1's draft; arm B's
    largest call carries the largest archived source inlined.
    """
    question = _largest_question()
    if arm in ("A", "D"):
        system, user = render_prompt(prompt_text(arm), question)
        prompt_bytes = _prompt_bytes(system, user)
        call_limit = 1
    elif arm == "B":
        system, base = render_prompt(prompt_text("B"), question)
        prompt_bytes = _prompt_bytes(system, base, _largest_tool_result())
        call_limit = ARM_B_CALL_LIMIT
    else:                                   # C: the check carries the draft
        system, user = _stage_message(
            "STAGE 2", question,
            "d" * (REGISTERED_MAX_TOKENS * DRAFT_BYTES_PER_TOKEN), None)
        prompt_bytes = _prompt_bytes(system, user)
        call_limit = ARM_C_CALL_LIMIT
    # The dearest serving the arm's calls can name: the worst case
    # is the worst serving, not the average one.
    worst_per_call = 0.0
    for serving in _arm_servings(arm, servings):
        prompt_rate, completion_rate = _rates(index, serving, f"arm {arm}")
        worst_per_call = max(
            worst_per_call,
            worst_case_cost(prompt_rate, completion_rate,
                            prompt_bytes, REGISTERED_MAX_TOKENS,
                            _per_request_charge(
                                _resolve_entry(index, serving))))
    return worst_per_call * call_limit, call_limit


def _tier_output_cap(tier: str) -> int:
    """The standing output ceiling the pipeline's nodes send on this
    tier — the same mapping the eval CLI registers
    (autornd/evals/cli.py: _tier_ceilings), read from the harness's
    own settings so the owner's .env caps are the ones checked."""
    if tier in ("architecture", "engineering"):
        return harness_settings.plan_max_tokens
    if tier == "judge":
        return harness_settings.judge_max_tokens
    if tier == "escalation":
        return harness_settings.escalation_max_tokens
    if tier == "search":
        return harness_settings.search_max_tokens_consequential
    return _CHAT_DEFAULT_MAX_TOKENS


@dataclass
class PreflightReport:
    """The free preflight's verdict, before the first unit.

    ``refusals`` are the cases the command names (plus the owner's
    additions): non-empty means do not start. ``reports`` are facts
    the preflight states without refusing — the catalogue's blindness
    about a parameter, and arm E's standing caps above an endpoint's
    limit, which are reported because arm E runs under the guard as
    it ships.
    """

    refusals: list[str] = field(default_factory=list)
    reports: list[str] = field(default_factory=list)


def run_preflight(servings: dict[str, Any],
                  catalogue: list[dict[str, Any]]) -> PreflightReport:
    """The preflight, before the first unit. Free: it reads the
    catalogue fixture or the free GET's result, and computes.

    It refuses to start, and prints the figures, in the command's
    four cases plus the owner's addition:

    1. the worst case of any of arms A-D over its whole call
       sequence exceeds the arm's per-unit ceiling;
    2. arm B's serving does not list tool support or
       tool_choice support (when the catalogue is blind,
       the preflight reports that and does not guess);
    3. arm B's context window cannot hold its prompt, the largest
       archived source and max_tokens, bounded in bytes;
    4. any serving has no catalogue price (D49: an unknown price is
       not free);
    5. (the owner's addition) an arm A-D call's registered
       max_tokens exceeds the pinned endpoint's max_completion_tokens
       in the catalogue — the client does not clamp, so the call
       would fail at the provider. Arm E's tiers are reported, not
       refused: arm E runs under the guard as it ships.
    """
    report = PreflightReport()
    index = catalogue_index(catalogue)

    # Case 4 first, and for every serving arm E's included: the
    # worst cases below need rates, and a serving with no price is
    # refused whatever else is true of it. A variant serving
    # resolves to the entry that prices it, so a served variant
    # of a priced base is refused only when that price cannot be
    # bounded.
    for arm in ARMS:
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

    # Case 1: the worst case of arms A-D over the whole sequence.
    for arm in ("A", "B", "C", "D"):
        if any(_resolve_entry(index, serving) is None
               or _unpriced(_resolve_entry(index, serving))
               for serving in _arm_servings(arm, servings)):
            continue       # case 4 already refused this arm
        worst, call_limit = _arm_sequence_worst_case(arm, servings, index)
        ceiling = ARM_CEILINGS[arm]
        if worst > ceiling:
            report.refusals.append(
                f"arm {arm}: the worst case of its {call_limit}-call "
                f"sequence is ${worst:.4f}, above its per-unit ceiling "
                f"${ceiling:.2f} (call limit x each call's worst case at "
                f"max_tokens {REGISTERED_MAX_TOKENS}, the largest prompt "
                f"the call can carry, arm B's largest tool result included)")

    # Case 2: arm B's serving must list tool support, and
    # tool_choice beside it - R2's final call keeps the
    # tools declared with tool_choice "none", so an endpoint
    # that cannot take tool_choice would fail the call the
    # treatment depends on. Blind is a report, not a guess
    # (the command's own text). A variant serving reads the
    # entry that prices it.
    b_entry = _resolve_entry(index, servings["B"])
    if b_entry is not None:
        supported = b_entry.get("supported_parameters")
        if supported is None:
            report.reports.append(
                f"arm B: the catalogue is blind about {servings['B']}'s "
                "parameters (the entry carries no supported_parameters), "
                "so tool and tool_choice support is unverified — "
                "reported, not guessed")
        else:
            if "tools" not in supported:
                report.refusals.append(
                    f"arm B: {servings['B']} does not list tool "
                    f"support (supported_parameters: "
                    f"{', '.join(str(name) for name in supported) or 'none'})")
            if "tool_choice" not in supported:
                report.refusals.append(
                    f"arm B: {servings['B']} does not list "
                    f"tool_choice support (supported_parameters: "
                    f"{', '.join(str(name) for name in supported) or 'none'})")

    # Case 3: arm B's context window, bounded in bytes (D45 amendment
    # (b): a byte-level tokenizer never emits more tokens than bytes,
    # so the byte length is the conservative token bound the check
    # needs — the command named the harness's retired CHARS_PER_TOKEN,
    # and the byte bound is its conservative replacement).
    if b_entry is not None:
        context = b_entry.get("context_length")
        system, base = render_prompt(prompt_text("B"), _largest_question())
        prompt_bytes = _prompt_bytes(system, base, _largest_tool_result())
        if context is None:
            report.reports.append(
                f"arm B: the catalogue is blind about "
                f"{servings['B']}'s context length, so the capacity "
                "check could not run — reported, not guessed")
        elif prompt_bytes + REGISTERED_MAX_TOKENS > context:
            report.refusals.append(
                f"arm B: the largest prompt ({prompt_bytes} bytes, the "
                f"registered question, the arm B prompt and the largest "
                f"archived source) plus max_tokens {REGISTERED_MAX_TOKENS} "
                f"exceeds {servings['B']}'s context window of {context}")

    # The owner's addition (1): the registered max_tokens against the
    # endpoint's max_completion_tokens. Arms A-D: a refusal. Arm E's
    # tiers: a report — arm E runs under the guard as it ships.
    for arm in ("A", "B", "C", "D"):
        for serving in _arm_servings(arm, servings):
            entry = _resolve_entry(index, serving)
            if entry is None:
                continue                   # already refused above
            cap = entry.get("max_completion_tokens")
            if cap is None:
                report.reports.append(
                    f"arm {arm}: the catalogue is blind about "
                    f"{serving}'s max_completion_tokens, so the "
                    f"registered max_tokens {REGISTERED_MAX_TOKENS} could "
                    "not be checked against it — reported, not guessed")
            elif REGISTERED_MAX_TOKENS > cap:
                report.refusals.append(
                    f"arm {arm}: the registered max_tokens "
                    f"{REGISTERED_MAX_TOKENS} exceeds {serving}'s "
                    f"max_completion_tokens {cap} — the client does not "
                    "clamp, so the call would fail at the provider")
    for tier, serving in servings["E"].items():
        entry = _resolve_entry(index, serving)
        if entry is None:
            continue
        cap = entry.get("max_completion_tokens")
        standing = _tier_output_cap(tier)
        if cap is None:
            report.reports.append(
                f"arm E/{tier}: the catalogue is blind about "
                f"{serving}'s max_completion_tokens, so the standing cap "
                f"{standing} could not be checked against it")
        elif standing > cap:
            report.reports.append(
                f"arm E/{tier}: the standing cap {standing} exceeds "
                f"{serving}'s max_completion_tokens {cap} — the client "
                "does not clamp, so a call at the cap would fail at the "
                "provider (reported, not refused: arm E runs under the "
                "guard as it ships)")
    return report


def arm_e_worst_case(servings: dict[str, Any],
                     catalogue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The owner's addition (2): the worst case per call for each arm
    E tier under the ratified lineup and the standing caps, against
    the $0.50 per-unit ceiling, with the guard's own formula and the
    catalogue's rates — saying which calls the guard would refuse and
    at what spend.

    The prompt side is the largest prompt this experiment's entry
    point carries, the question as the scenario request the pipeline
    receives; the pipeline's own node prompts sit above it, so these
    figures are floors. The guard computes the real bytes at call
    time and refuses the call then, which is the binding check. A
    serving whose catalogue entry carries no pricing of its own —
    a variant endpoint (':exacto' among them) the per-model
    endpoint confirms is served — is priced at its base entry's
    published rate, and the row says which entry priced it. A flat
    per-request charge is added once per call.
    """
    index = catalogue_index(catalogue)
    question = _largest_question()
    prompt_bytes = _prompt_bytes(question)
    rows: list[dict[str, Any]] = []
    for tier in PIPELINE_TIERS:
        serving = servings["E"][tier]
        cap = _tier_output_cap(tier)
        entry = _resolve_entry(index, serving)
        if entry is None:
            rows.append({"tier": tier, "serving": serving,
                         "cap": cap, "unknown": True,
                         "reason": "not in the provider "
                                   "catalogue"})
            continue
        reason = _unboundable_reason(entry)
        if reason is not None:
            rows.append({"tier": tier, "serving": serving,
                         "cap": cap, "unknown": True,
                         "reason": reason})
            continue
        prompt_rate, completion_rate = _rates(
            index, serving, f"arm E/{tier}")
        per_request = _per_request_charge(entry)
        worst = worst_case_cost(prompt_rate, completion_rate,
                                prompt_bytes, cap, per_request)
        ceiling = ARM_CEILINGS["E"]
        # The guard refuses the call when the worst case exceeds what
        # remains, so the call is refusable once the unit has spent
        # more than the ceiling minus the worst case.
        rows.append({
            "tier": tier,
            "serving": serving,
            "cap": cap,
            "prompt_rate": prompt_rate,
            "completion_rate": completion_rate,
            "per_request_charge": per_request,
            "priced_as": entry["id"],
            "worst_case": worst,
            "unit_ceiling": ceiling,
            "refuses_even_at_zero_spend": worst > ceiling,
            "refusable_above_spend": max(0.0, ceiling - worst),
            "endpoint_max_completion_tokens": entry.get(
                "max_completion_tokens"),
        })
    return rows


def arm_f_worst_case(servings: dict[str, Any],
                     catalogue: list[dict[str, Any]]
                     ) -> list[dict[str, Any]]:
    """The re-measurement's arm F: the worst case per
    call on each standing tier the verify-first workflow
    calls, with the workflow's own call count on that
    tier, against the $0.20 per-unit ceiling.

    Arm F runs arm E's path on arm E's standing tiers —
    the same pins, the same standing caps (D51 (8)
    leaves the tiers, the pins, the budgets and the loop
    bounds untouched), so the per-call worst case on a
    tier is the figure the arm-E table carries. What
    differs is how many calls the workflow makes on it:
    the triage tier carries the triage and the asks
    (two calls), and the verify loop runs the answer and
    the check at most twice (two engineering, two judge)
    — the registered bound, at most four model calls
    after triage and asks. The sequence's worst case is
    the sum those counts compose, against arm F's
    ceiling; a sequence whose worst case exceeds it
    refuses even at zero spend, the way the arm-E
    table's rows say. The prompt side is the largest
    prompt this experiment's entry point carries, as the
    arm-E table's is: a floor, with the guard's call-time
    computation the binding check.
    """
    index = catalogue_index(catalogue)
    question = _largest_question()
    prompt_bytes = _prompt_bytes(question)
    # The verify-first workflow's calls on each tier:
    # the triage and the asks on the triage tier, the
    # answer and its revision on the engineering tier,
    # the check and its re-check on the judge tier.
    counts = {"triage": 2, "engineering": 2, "judge": 2}
    rows: list[dict[str, Any]] = []
    sequence = 0.0
    for tier in ("triage", "engineering", "judge"):
        serving = servings["E"][tier]
        cap = _tier_output_cap(tier)
        calls = counts[tier]
        entry = _resolve_entry(index, serving)
        if entry is None:
            rows.append({"tier": tier, "serving": serving,
                         "cap": cap, "calls": calls,
                         "unknown": True,
                         "reason": "not in the provider "
                                   "catalogue"})
            continue
        reason = _unboundable_reason(entry)
        if reason is not None:
            rows.append({"tier": tier, "serving": serving,
                         "cap": cap, "calls": calls,
                         "unknown": True, "reason": reason})
            continue
        prompt_rate, completion_rate = _rates(
            index, serving, f"arm F/{tier}")
        per_request = _per_request_charge(entry)
        worst = worst_case_cost(prompt_rate, completion_rate,
                                prompt_bytes, cap, per_request)
        sequence += calls * worst
        # The guard refuses the call when the worst case
        # exceeds what remains, so the tier's calls are
        # refusable once the unit has spent more than the
        # ceiling minus the tier's worst case.
        rows.append({
            "tier": tier,
            "serving": serving,
            "cap": cap,
            "calls": calls,
            "prompt_rate": prompt_rate,
            "completion_rate": completion_rate,
            "per_request_charge": per_request,
            "priced_as": entry["id"],
            "worst_case": worst,
            "tier_worst_case": calls * worst,
            "unit_ceiling": ARM_CEILINGS["F"],
            "refuses_even_at_zero_spend": worst > ARM_CEILINGS["F"],
            "refusable_above_spend": max(
                0.0, ARM_CEILINGS["F"] - worst),
            "endpoint_max_completion_tokens": entry.get(
                "max_completion_tokens"),
        })
    # The bound the workflow's own counts compose: the
    # whole sequence's worst case, against the per-unit
    # ceiling. The bound is declared in the workflow, not
    # a setting, so no .env line can widen it.
    rows.append({
        "tier": "sequence",
        "serving": ("the verify-first bound: 2 triage + "
                    "2 engineering + 2 judge"),
        "calls": 6,
        "worst_case": sequence,
        "unit_ceiling": ARM_CEILINGS["F"],
        "refuses_even_at_zero_spend": (
            sequence > ARM_CEILINGS["F"]),
        "refusable_above_spend": max(
            0.0, ARM_CEILINGS["F"] - sequence),
    })
    return rows


# ── Arm B's tools (D50 (5)) ───────────────────────────────────
#
# The source tool is closed-world: it answers from the
# committed archive and opens no socket. The recompute tool
# evaluates arithmetic by walking a whitelisted syntax tree —
# it never evals, execs or compiles model text (hard rule 3).

_CITATION = re.compile(
    r"^\s*\$?(\d+)\$?\s+CFR\s+§?\s*\$?(\d+(?:\.\d+)*)\$?(\([^)]*\))?\s*$",
    re.IGNORECASE)


def _citation_in(text: str) -> str | None:
    """The CFR citation a question states, in the written
    form the tool accepts. The questions wrap their figures
    in LaTeX '$' and may write the '§' or not; the tool
    accepts both, with or without the paragraph."""
    match = re.search(
        r"\$?(\d+)\$?\s+CFR\s+§?\s*\$?(\d+(?:\.\d+)*)\$?(\([^)]*\))?",
        text)
    if not match:
        return None
    title, section, paragraph = match.groups()
    citation = f"{title} CFR {section}"
    if paragraph:
        citation += paragraph
    return citation


@functools.lru_cache(maxsize=1)
def _archive_registry() -> dict[tuple[str, str], Path]:
    """(title, section) -> the committed July 1, 2014 edition.

    The closed world is exactly what the tree holds: the
    registry is built from the committed .txt files under
    evals/tier2/sources/, so a citation resolves only when its
    edition is archived here. A file named
    CFR-2014-title29-vol5-sec1910-146.txt is title 29, section
    1910.146 — the section's hyphen is its dot.
    """
    registry: dict[tuple[str, str], Path] = {}
    for path in sorted(SOURCES.glob("CFR-*.txt")):
        match = re.fullmatch(
            r"CFR-\d{4}-title(\d+)-vol\d+-sec([\d.]+(?:-[\d]+)*)\.txt",
            path.name)
        if match:
            registry[(match.group(1), match.group(2).replace("-", "."))] = path
    return registry


def fetch_primary_source(citation: str) -> dict[str, Any]:
    """Arm B's source tool: closed-world.

    Accepts a CFR citation in the forms the questions write it —
    '29 CFR § 1910.146(b)', '40 CFR 141.62(b)', with or without
    the '§', the paragraph, or the LaTeX '$' wrappers the
    questions wrap their figures in, wherever the wrappers sit
    (the questions wrap each figure separately, so a paragraph
    inside the wrappers leaves a trailing '$' after it) —
    normalises it to title and section, and returns that
    section's July 1, 2014 edition text from the committed
    archive. Any other citation gets a typed not-available
    result: recorded, and not a refusal.
    The tool opens no socket — the archive is the whole world.
    """
    # The wrappers are copied verbatim with the
    # citation, wherever they sit: stripped before
    # the anchored match, which the trailing '$'
    # of a wrapped paragraph would otherwise defeat.
    match = _CITATION.match((citation or "").replace("$", ""))
    if not match:
        return {"available": False, "citation": citation,
                "reason": "not a CFR citation in a form the "
                          "questions write it"}
    title, section = match.group(1), match.group(2)
    path = _archive_registry().get((title, section))
    if path is None:
        return {
            "available": False, "citation": citation,
            "reason": f"{title} CFR {section} is not in the archived "
                      f"July 1, 2014 editions under {SOURCES}"}
    return {
        "available": True, "citation": citation,
        "title": title, "section": section,
        "edition": "July 1, 2014", "source": path.name,
        "text": path.read_text(encoding="utf-8")}


# The whitelisted syntax tree. Every node the evaluator walks
# is named here; anything else is a typed rejection, and the
# expression's own text is never executed.
_ALLOWED_FUNCTIONS = {
    "sqrt": math.sqrt, "exp": math.exp, "ln": math.log,
    "log10": math.log10,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "abs": abs, "min": min, "max": max,
}
_MAX_EXPONENT = 1000
_MAX_RESULT = 1e300


class RecomputeError(ValueError):
    """A typed rejection: the expression is outside the
    whitelisted syntax, or its evaluation is out of bounds."""


def recompute(expression: str) -> dict[str, Any]:
    """Arm B's recompute tool: arithmetic by walking a
    whitelisted syntax tree.

    It accepts numbers, + - * / and powers (written *, x, ×,
    /, ÷ or ^), parentheses, pi, e, and the functions sqrt,
    exp, ln, log10, sin, cos, tan, their inverses, abs, min
    and max. It never evals, execs or compiles model text
    (hard rule 3): the expression is parsed with ast.parse and
    the tree is walked node by node. Exponents and results are
    bounded, and a rejection returns a typed result to the
    model.
    """
    # The written forms the questions and the models use,
    # translated to their ASCII operators before parsing.
    normalized = (expression.strip()
                  .replace("×", "*").replace("∗", "*")
                  .replace("÷", "/").replace("−", "-")
                  .replace("^", "**"))
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        return {"ok": False, "expression": expression,
                "error": f"not a parseable expression: {exc}"}
    try:
        value = _eval_node(tree.body)
    except RecomputeError as exc:
        return {"ok": False, "expression": expression,
                "error": str(exc)}
    if not math.isfinite(value) or abs(value) > _MAX_RESULT:
        return {"ok": False, "expression": expression,
                "error": f"the result {value!r} is outside the "
                         f"bounded range (±{_MAX_RESULT:.0e})"}
    return {"ok": True, "expression": expression, "value": value}


def _eval_node(node: ast.AST) -> float:
    """One node of the whitelisted syntax tree, or a typed
    rejection. The fallthrough is the whitelist: any node type
    not named below is rejected, so nothing outside the
    arithmetic grammar can be built."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        raise RecomputeError(f"the constant {node.value!r} is not a number")
    if isinstance(node, ast.Name):
        if node.id == "pi":
            return math.pi
        if node.id == "e":
            return math.e
        raise RecomputeError(
            f"the name {node.id!r} is outside the whitelist "
            "(pi and e only)")
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise RecomputeError("division by zero")
            return left / right
        if isinstance(node.op, ast.Pow):
            if abs(right) > _MAX_EXPONENT:
                raise RecomputeError(
                    f"the exponent {right!r} exceeds the bound "
                    f"±{_MAX_EXPONENT}")
            try:
                powered = left ** right
            except OverflowError:
                # A power within the exponent bound whose
                # result overflows the float range: the
                # typed rejection the manifest registers
                # ("a result beyond 1e300"), not an
                # exception the model would have to read.
                raise RecomputeError(
                    f"the power {left!r} ** {right!r} "
                    f"overflows the bound ±{_MAX_RESULT:.0e}"
                ) from None
            if not math.isfinite(powered) or abs(powered) > _MAX_RESULT:
                raise RecomputeError(
                    f"the power {left!r} ** {right!r} overflows the "
                    f"bound ±{_MAX_RESULT:.0e}")
            return powered
        raise RecomputeError(
            f"the operator {type(node.op).__name__} is outside the "
            "whitelist (+, -, *, / and powers only)")
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return operand
        raise RecomputeError(
            f"the unary operator {type(node.op).__name__} is "
            "outside the whitelist")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise RecomputeError("only a bare function name can be "
                                 "called, not an attribute or a "
                                 "subscript")
        if node.func.id not in _ALLOWED_FUNCTIONS:
            raise RecomputeError(
                f"the call to {node.func.id!r} is outside the "
                f"whitelist ({', '.join(sorted(_ALLOWED_FUNCTIONS))})")
        if node.keywords:
            raise RecomputeError("keyword arguments are not allowed")
        arguments = [_eval_node(argument) for argument in node.args]
        function = _ALLOWED_FUNCTIONS[node.func.id]
        try:
            return float(function(*arguments))
        except (ValueError, ZeroDivisionError, OverflowError) as exc:
            raise RecomputeError(
                f"{node.func.id}({', '.join(str(a) for a in arguments)})"
                f" failed: {exc}")
    raise RecomputeError(
        f"{type(node).__name__} is outside the whitelisted syntax "
        "(numbers, the four operations and powers, parentheses, "
        "pi, e and the whitelisted functions)")


# The tool registration arm B's calls offer, in the provider's
# tool-call format. The descriptions match what the tools do —
# the closed-world fetch and the whitelisted recompute — which
# is what the manifest's corrected tool descriptions say.
TOOL_SPEC: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_primary_source",
            "description": (
                "Fetch the archived July 1, 2014 text of the CFR "
                "section a question cites, written as the question "
                "writes it (for example '29 CFR § 1910.146(b)'). "
                "Returns the section's archived text verbatim, or a "
                "typed not-available result when the citation is not "
                "one of the archived editions. Opens no network "
                "connection."),
            "parameters": {
                "type": "object",
                "properties": {
                    "citation": {
                        "type": "string",
                        "description": "the CFR citation as the question states it",
                    },
                },
                "required": ["citation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recompute",
            "description": (
                "Evaluate one deterministic arithmetic expression: "
                "numbers, + - * / and powers, parentheses, pi, e, "
                "and sqrt, exp, ln, log10, sin, cos, tan, their "
                "inverses, abs, min and max. Returns the value, or a "
                "typed error naming what is outside the whitelist. "
                "Use it for every numerical derivation rather than "
                "trusting mental arithmetic."),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "the arithmetic expression to evaluate",
                    },
                },
                "required": ["expression"],
            },
        },
    },
]


def _tool_call_parts(tool_call: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """(tool name, arguments) from either tool-call shape the
    provider returns: the function-wrapped form and the bare
    form. Arguments arrive as a JSON string or a mapping."""
    function = tool_call.get("function") or {}
    name = function.get("name") or tool_call.get("name") or ""
    arguments = function.get("arguments",
                             tool_call.get("arguments") or {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {"raw": arguments}
    if not isinstance(arguments, dict):
        arguments = {"value": arguments}
    return str(name), arguments


def _dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """One tool invocation, dispatched to the real tool. A
    citation the archive does not hold and an expression the
    whitelist rejects are typed RESULTS, not failures — the
    model sees the answer to its request either way."""
    if name == "fetch_primary_source":
        return fetch_primary_source(str(arguments.get("citation", "")))
    if name == "recompute":
        return recompute(str(arguments.get("expression", "")))
    return {"ok": False, "error": f"unknown tool {name!r}"}


def _result_size(result: dict[str, Any]) -> int:
    """The invocation record's result size, in bytes."""
    return len(json.dumps(result, default=str).encode("utf-8"))


def _invoke_tool(tool_call: dict[str, Any], remaining: int,
                 dispatcher: Any = None) -> dict[str, Any]:
    """Execute one tool invocation and record it: the tool, its
    arguments, the result's size, any error.

    A failure is recorded and returned, never raised: the model
    continues without the tool, and the delivered answer is
    scored on what it delivered (the manifest's tool_failure
    rule). The dispatcher seam is the dry run's: it replaces
    the tool's execution with a scripted failure, the way a
    real OSError would, while the loop around it stays the real
    machinery.
    """
    name, arguments = _tool_call_parts(tool_call)
    if remaining <= 0:
        return {"tool": name, "arguments": arguments, "ok": False,
                "error": (f"tool invocation budget exhausted "
                          f"({ARM_B_TOOL_INVOCATION_LIMIT} per unit)"),
                "result_size": 0}
    try:
        result = (dispatcher(name, arguments) if dispatcher is not None
                  else _dispatch_tool(name, arguments))
    except Exception as exc:            # a tool failure: recorded, not fatal
        return {"tool": name, "arguments": arguments, "ok": False,
                "error": f"{type(exc).__name__}: {exc}", "result_size": 0}
    return {"tool": name, "arguments": arguments, "ok": True,
            "result": result, "result_size": _result_size(result)}


def _format_tool_result(record: dict[str, Any]) -> str:
    """The invocation's result as the text the next call carries.

    The tool's typed results are said as they are: a
    not-available citation and a rejected expression are
    results, not failures, and the model is told which it got.
    """
    if not record["ok"]:
        return f"Tool {record['tool']} failed: {record['error']}"
    result = record["result"]
    if not result.get("available", True):
        return (f"Tool {record['tool']} result: not available — "
                f"{result.get('reason')}")
    if not result.get("ok", True):
        return (f"Tool {record['tool']} result: error — "
                f"{result.get('error')}")
    if "text" in result:
        return (f"Tool {record['tool']}({json.dumps(record['arguments'])}) "
                f"returned {record['result_size']} bytes:\n{result['text']}")
    return (f"Tool {record['tool']}({json.dumps(record['arguments'])}) "
            f"= {result.get('value')!r}")


# ── Arm C's typed check (D50 (4)) ───────────────────────────────

@dataclass
class CooperationCheckVerdict:
    """Arm C's typed check verdict. Control flow never reads
    prose (hard rule 2): concur is a bool, and objections is a
    list of strings that is non-empty exactly when concur is
    false."""

    concur: bool
    objections: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {"concur": self.concur,
                "objections": list(self.objections)}


def parse_check_verdict(payload: Any) -> CooperationCheckVerdict | None:
    """The typed verdict from the model's JSON reply, or None
    when the reply is not a valid verdict.

    Valid iff concur is a bool AND objections is a list of
    strings AND (concur implies objections is empty) AND (not
    concur implies objections is non-empty). Anything else is
    not a verdict: the caller retries within the bound, and a
    verdict still invalid after the bounded retries is recorded
    as unavailable — never as concurrence (D50 (4)).
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return None
    if not isinstance(payload, dict):
        return None
    concur = payload.get("concur")
    objections = payload.get("objections")
    if not isinstance(concur, bool):
        return None
    if (not isinstance(objections, list)
            or not all(isinstance(obj, str) for obj in objections)):
        return None
    if concur and objections:
        return None
    if not concur and not objections:
        return None
    return CooperationCheckVerdict(concur=concur,
                                   objections=list(objections))


# ── The unit result ─────────────────────────────────────────────

@dataclass
class UnitResult:
    """One unit's record: the manifest's execution rule, as a
    typed row. Every failure class is a status, counted in its
    arm's 75-unit denominator — an incomplete, refused or
    timed-out unit is 0 delivered, never dropped."""

    question_id: str
    repetition: int
    arm: str
    status: str                     # delivered | refusal | serving_error | deadline | incomplete | skipped
    serving: Any = None
    answer: str | None = None
    delivered_kind: str = ""        # arm E: shipped | approved, not shipped | no answer
    scorer: dict[str, Any] | None = None
    calls: int = 0
    seconds: float = 0.0
    cost: float = 0.0
    cost_by_tier: dict[str, float] = field(default_factory=dict)
    providers_by_tier: dict[str, list[str]] = field(default_factory=dict)
    retries_by_kind: dict[str, int] = field(default_factory=dict)
    finish_reasons: list[str | None] = field(default_factory=list)
    truncated: bool = False
    tool_invocations: list[dict[str, Any]] = field(default_factory=list)
    check: dict[str, Any] | None = None
    # arm E: the scenario run's internals (R1) - the plan's
    # success criteria and blockers, the build-loop iterations
    # (verdicts, dissent, findings), the escalation verdict,
    # the tokens by tier and the watchdog's typed record.
    pipeline: dict[str, Any] | None = None
    # Arms E and F: the workflow the unit ran (the standing
    # engineering-rnd for E, verify-first for F) and the model
    # calls after triage and asks - the figure the re-
    # measurement's criterion (c) bounds at 4 for arm F.
    workflow: str | None = None
    calls_after_asks: int | None = None
    stop_reason: str | None = None
    error: str | None = None
    unreconciled_liability: float = 0.0

    @property
    def delivered(self) -> bool:
        """Whether the unit delivered an answer. Arms E and F
        deliver only what the harness ships (D50 (3)): a
        judge-approved draft that has not shipped is scored and
        reported beside the delivered count, never counted as
        delivered."""
        if self.status != "delivered":
            return False
        return self.arm not in ("E", "F") or (
            self.delivered_kind == "shipped")

    def record(self) -> dict[str, Any]:
        return {
            "record": "unit",
            "question_id": self.question_id,
            "repetition": self.repetition,
            "arm": self.arm,
            "status": self.status,
            "serving": self.serving,
            "answer": self.answer,
            "delivered": self.delivered,
            "delivered_kind": self.delivered_kind,
            "scorer": self.scorer,
            "calls": self.calls,
            "seconds": round(self.seconds, 3),
            "cost": self.cost,
            "cost_by_tier": self.cost_by_tier,
            "providers_by_tier": self.providers_by_tier,
            "retries_by_kind": self.retries_by_kind,
            "finish_reasons": self.finish_reasons,
            "truncated": self.truncated,
            "tool_invocations": self.tool_invocations,
            "check": self.check,
            "pipeline": self.pipeline,
            "workflow": self.workflow,
            "calls_after_asks": self.calls_after_asks,
            "stop_reason": self.stop_reason,
            "error": self.error,
            "unreconciled_liability": self.unreconciled_liability,
        }


class ExperimentRefused(RuntimeError):
    """The experiment refused to start, before any paid call.

    Either a ratification gate is missing (the refusal names
    each one) or the preflight refused (each case names its
    figures). Carries the servings map and its fingerprint, so
    the operator sees what was refused, not only why.
    """

    def __init__(self, reason: str, servings: dict[str, Any] | None,
                 fingerprint: str | None, detail: list[str]) -> None:
        self.reason = reason
        self.servings = servings
        self.fingerprint = fingerprint
        self.detail = detail
        text = f"{reason}: " + "; ".join(detail)
        if fingerprint:
            text += f" (servings fingerprint {fingerprint})"
        super().__init__(text)


# ── The five arm executors ──────────────────────────────────────
#
# Each executor runs its arm's registered treatment and
# returns the answer with the call metadata the record carries.
# Every call names its serving directly (the client's additive
# per-call serving parameter), carries the registered
# parameters, and is billed, reserved and reconciled under D45
# like every existing path.

async def _registered_call(client: OpenRouterClient, function: str,
                           serving: str, system: str, user: str,
                           response_format: dict[str, Any] | None = None,
                           tools: list[dict[str, Any]] | None = None,
                           tool_choice: str | None = None,
                           ) -> ModelResponse:
    """One registered call: the arm's serving named directly,
    the registered max_tokens and temperature, the tools
    the call offers, and the tool_choice the call sets
    (arm B's final call keeps the tools declared with
    tool_choice "none")."""
    return await client.chat(
        function, system, user,
        response_format=response_format,
        temperature=REGISTERED_TEMPERATURE,
        max_tokens=REGISTERED_MAX_TOKENS,
        model=serving,
        tools=tools,
        tool_choice=tool_choice,
    )


def _unit_client(unit_key: tuple[str, int, str], arm: str,
                 serving: str, ceiling: float,
                 call_limit: int,
                 factory: Any = None) -> OpenRouterClient:
    """The unit's client, carrying its arm's per-unit ceilings.

    The factory seam is the dry run's: it returns the scripted
    client, which bills through the real guard and accounting so
    the budget machinery the dry run exercises is the real one.
    The factory receives the unit key, so a scripted client can
    find the script's entry for the unit it is running.
    """
    if factory is not None:
        return factory(unit_key, arm, serving, ceiling, call_limit)
    client = OpenRouterClient()
    client.call_ceiling = call_limit
    client.spend_ceiling = ceiling
    return client


async def _arm_single(arm: str, question: str, serving: str,
                      client: OpenRouterClient) -> tuple[str | None,
                                                          list[str | None]]:
    """Arms A and D: one call, the request only. No tools, no
    workflow, no retrieval — the two arms differ only in the
    serving, so the A-vs-D gap is a serving gap, not a
    treatment gap."""
    system, user = render_prompt(prompt_text(arm), question)
    response = await _registered_call(
        client, f"tier3_arm_{arm.lower()}", serving, system, user)
    return response.content, [response.finish_reason]


async def _arm_b(question: str, serving: str,
                 client: OpenRouterClient,
                 tool_dispatcher: Any = None
                 ) -> tuple[str | None, list[str | None],
                            list[dict[str, Any]]]:
    """Arm B's tool loop: the same serving as arm A, with the
    two registered tools.

    At most 3 model calls and 20 tool invocations per unit.
    Calls 1 and 2 offer the tools; call 3 keeps them declared
    with tool_choice "none", so the model sees the tools it
    may not use and must answer. The client's chat() takes no
    conversation history, so each round's tool results are
    inlined into the next call's user message — the same text
    the model would have seen in a tool-result turn. Every
    invocation is recorded: the tool, its arguments, the
    result's size, any error. A tool failure is recorded and
    the model continues without the tool; the delivered answer
    is scored on what it delivered.
    """
    system, base_user = render_prompt(prompt_text("B"), question)
    invocations: list[dict[str, Any]] = []
    finish_reasons: list[str | None] = []
    user = base_user
    answer: str | None = None
    for call_number in range(1, ARM_B_CALL_LIMIT + 1):
        # The final call keeps the tools declared with
        # tool_choice "none" (R2): the model sees the
        # tools it may not use, and answers. Withdrawing
        # them entirely changed the request the serving
        # saw - the stage-1 run's 13 final-call errors
        # (finish "error", 0 tokens) answered a different
        # request, not the question.
        choice = ("none" if call_number == ARM_B_CALL_LIMIT
                  else None)
        response = await _registered_call(
            client, "tier3_arm_b", serving, system, user,
            tools=TOOL_SPEC, tool_choice=choice)
        finish_reasons.append(response.finish_reason)
        if call_number == ARM_B_CALL_LIMIT:
            answer = response.content
            break
        if not response.tool_calls:
            # The model answered without asking: that is a
            # complete arm B unit, delivered on call 2.
            answer = response.content
            break
        results: list[str] = []
        for tool_call in response.tool_calls:
            invocation = _invoke_tool(
                tool_call,
                ARM_B_TOOL_INVOCATION_LIMIT - len(invocations),
                dispatcher=tool_dispatcher)
            invocations.append(invocation)
            results.append(_format_tool_result(invocation))
        user = base_user + "\n\n" + "\n".join(results)
    return answer, finish_reasons, invocations


async def _arm_c(question: str, draft_serving: str,
                 check_serving: str,
                 client: OpenRouterClient) -> tuple[str | None,
                                                     list[str | None],
                                                     dict[str, Any]]:
    """Arm C's cooperation protocol: model 1 drafts, model 2
    checks with a typed verdict, model 1 revises once.

    The three calls are a hard whole-sequence bound (the
    manifest's call_limit), so the check's bounded retries
    compete with the revision for the third call: a revision
    runs only when the check objected AND a call remains, and
    the starvation path is recorded, not hidden. A check that
    returns no valid verdict after the bounded retries is
    recorded as unavailable — never as concurrence — and
    model 1's draft is delivered (D50 (4)).
    """
    finish_reasons: list[str | None] = []
    calls = 0
    # Stage 1 — model 1 drafts.
    calls += 1
    system, user = _stage_message("STAGE 1", question, None, None)
    draft_response = await _registered_call(
        client, "tier3_arm_c_1", draft_serving, system, user)
    finish_reasons.append(draft_response.finish_reason)
    draft = draft_response.content
    # Stage 2 — model 2 checks, requested as JSON through the
    # client's existing response_format handling, with the
    # bounded retries.
    verdict: CooperationCheckVerdict | None = None
    raw_replies: list[str] = []
    for _attempt in range(ARM_C_CHECK_ATTEMPTS):
        if calls >= ARM_C_CALL_LIMIT:
            break               # no call remains for the check
        calls += 1
        system, user = _stage_message("STAGE 2", question, draft, None)
        check_response = await _registered_call(
            client, "tier3_arm_c_2", check_serving, system, user,
            response_format={"type": "json_object"})
        finish_reasons.append(check_response.finish_reason)
        raw_replies.append(check_response.content or "")
        verdict = parse_check_verdict(check_response.content)
        if verdict is not None:
            break
    check_record: dict[str, Any] = {
        "attempts": len(raw_replies),
        "raw_replies": raw_replies,
        "verdict": None if verdict is None else verdict.as_dict(),
    }
    # Stage 3 — model 1 revises, only when the check objected
    # and a call remains.
    if verdict is None:
        check_record["status"] = "unavailable"
        return draft, finish_reasons, check_record
    if verdict.concur:
        check_record["status"] = "concurred"
        return draft, finish_reasons, check_record
    if calls >= ARM_C_CALL_LIMIT:
        # The check objected, but the bounded retries spent the
        # last call: the draft is delivered, the objection
        # recorded beside it.
        check_record["status"] = "starved"
        return draft, finish_reasons, check_record
    calls += 1
    system, user = _stage_message(
        "STAGE 3", question, draft, verdict.objections)
    revised = await _registered_call(
        client, "tier3_arm_c_1", draft_serving, system, user)
    finish_reasons.append(revised.finish_reason)
    check_record["status"] = "objected"
    return revised.content, finish_reasons, check_record


async def _arm_e(question: str, question_id: str, repetition: int,
                 deadline: float, budget: SweepBudget | None,
                 spec, settings_lookup_dict: dict[str, Any],
                 client_factory: Any,
                 scenario_runner: Any = None,
                 ) -> tuple[Any, str | None, str]:
    """Arm E (D50 (3)): the question enters as a request
    through the full harness workflow under the standing pins,
    with the common deadline as its timeout so D38's watchdog
    ends the run by its own terminal.

    Delivered means a completed terminal's
    ``verdicts.implement.summary``, read the way the record
    reads it (evals.golden.score_trace.answer_of). A
    judge-approved iteration with no completed terminal is
    scored and reported beside the delivered count as
    'approved, not shipped' — never counted as delivered.
    A run that ended escalated or blocked after an
    implementation exists keeps its unendorsed candidate
    (Ruling D51 (7)) — read and reported the same way,
    never counted as delivered.
    """
    scenario = Scenario(
        id=f"tier3_e_{question_id}_r{repetition}",
        request=question,
        description=(f"tier-3 arm E unit: question {question_id}, "
                     f"repetition {repetition}, the current pipeline "
                     f"under the standing pins"),
        workflow=None,                  # the standing workflow
        timeout=deadline,
        expect={"max_calls": ARM_E_CALL_LIMIT},
    )
    runner = scenario_runner or run_scenario
    run = await runner(
        scenario, spec, client_factory, settings_lookup_dict,
        timeout=deadline, max_spend=ARM_CEILINGS["E"], budget=budget)
    unit = {
        "status": getattr(run, "status", None),
        "verdicts": getattr(run, "verdicts", None),
        "watchdog": getattr(run, "watchdog", None),
        "iterations": getattr(run, "iterations", None),
        "candidate": getattr(run, "candidate", None),
    }
    answer, kind = answer_of(unit)
    return run, answer, kind


async def _arm_f(question: str, question_id: str, repetition: int,
                 deadline: float, budget: SweepBudget | None,
                 spec, settings_lookup_dict: dict[str, Any],
                 client_factory: Any,
                 scenario_runner: Any = None,
                 ) -> tuple[Any, str | None, str]:
    """Arm F (D51 (8)): verify-first through arm E's
    path — the same boundary arm E runs (the scenario,
    the deadline, the delivery reader, the accounting,
    the record), with Ruling D51 (8)'s verify-first
    workflow as the graph instead of the standing one.

    The workflow answers once and checks against the
    asks: triage, the asks and their anchoring check,
    grounding, one answer on the engineering tier from
    the request and the asks with no plan, the free
    checks, and one check on the judge tier — at most 4
    model calls after triage and asks. A run with no
    anchored dissent ends completed; otherwise one
    revision addresses only the anchored dissents, then
    the free checks and one more check, and a dissent
    that survives ends the run escalated and unresolved,
    with its candidate kept under D51 (7).
    """
    scenario = Scenario(
        id=f"tier3_f_{question_id}_r{repetition}",
        request=question,
        description=(f"tier-3 arm F unit: question {question_id}, "
                     f"repetition {repetition}, the verify-first "
                     f"workflow (D51 (8)) under the standing pins"),
        workflow="verify-first",
        timeout=deadline,
        expect={"max_calls": ARM_F_CALL_LIMIT},
    )
    runner = scenario_runner or run_scenario
    run = await runner(
        scenario, spec, client_factory, settings_lookup_dict,
        timeout=deadline, max_spend=ARM_CEILINGS["F"], budget=budget)
    unit = {
        "status": getattr(run, "status", None),
        "verdicts": getattr(run, "verdicts", None),
        "watchdog": getattr(run, "watchdog", None),
        "iterations": getattr(run, "iterations", None),
        "candidate": getattr(run, "candidate", None),
    }
    answer, kind = answer_of(unit)
    return run, answer, kind


# ── The unit driver ───────────────────────────────────────────

async def run_unit(unit_key: tuple[str, int, str],
                    questions: dict[str, dict[str, Any]],
                    servings: dict[str, Any],
                    budget: SweepBudget | None,
                    deadline: float = DEADLINE_SECONDS,
                    deadline_overrides: dict[tuple[str, int, str],
                                             float] | None = None,
                    client_factory: Any = None,
                    tool_dispatcher: Any = None,
                    scenario_runner: Any = None,
                    spec: Any = None,
                    spec_f: Any = None,
                    pipeline_client_factory: Any = None,
                    ) -> UnitResult:
    """One unit, end to end: the arm's treatment under the
    common deadline inside ``_isolated_store()``, scored with
    the frozen scorer, with every figure the record carries.

    The deadline is enforced with ``asyncio.wait_for`` around
    the whole unit (arms E and F's runs also carry it as their
    scenario timeout, so D38's watchdog ends the run by its
    own terminal and this backstop fires only if the watchdog
    failed). Arms A-D's spend is booked to the sweep budget
    here; arms E and F's is booked inside run_scenario, which
    makes the same decision with the same fit rule.
    """
    question_id, repetition, arm = unit_key
    question = questions[question_id]["question"]
    result = UnitResult(
        question_id=question_id, repetition=repetition, arm=arm,
        status="incomplete",
        serving=_serving_record(arm, servings))
    effective_deadline = (deadline_overrides or {}).get(
        unit_key, deadline)

    # The fit rule, decided before any client exists. Arms
    # E and F's run_scenario makes the same decision inside
    # itself, with the same budget object, so the two
    # ceilings compose the way the harness's sweeps
    # compose them.
    if (arm not in ("E", "F") and budget is not None
            and not budget.can_start(ARM_CEILINGS[arm])):
        result.status = "skipped"
        result.stop_reason = budget.skip(ARM_CEILINGS[arm])
        return result

    started = time.perf_counter()
    client: OpenRouterClient | None = None
    run: Any = None
    # The unit's client, captured as soon as the arm's
    # executor makes it, so the figures it booked (spend,
    # unreconciled liability) reach the unit's record
    # even when a call fails mid-flight and the executor
    # raises before its payload is shaped - the
    # manifest's outstanding-liability rule, and the
    # deadline rule beside it: what the unit spent before
    # the watchdog stopped it is part of what it cost.
    made: dict[str, Any] = {}
    try:
        with _isolated_store():
            payload = await asyncio.wait_for(
                _execute_arm(arm, question, question_id, repetition,
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
        result.check = payload.get("check")
        result.truncated = any(
            reason == "length" for reason in result.finish_reasons)
        if run is not None:
            # Arms E and F: the pipeline run's own accounting.
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
            # The scenario run's internals (R1): the record
            # used to carry the accounting and drop the
            # pipeline's own story - why it ended the way
            # it did.
            result.pipeline = _pipeline_record(run)
            # The workflow the unit ran and the model calls
            # after triage and asks (the re-measurement's
            # criterion (c) bounds arm F's at 4).
            result.workflow = payload.get("workflow")
            result.calls_after_asks = payload.get(
                "calls_after_asks")
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
        # The delivered answer, and the failure classes.
        if arm in ("E", "F"):
            kind = payload.get("delivered_kind", "")
            result.delivered_kind = kind
            if getattr(run, "was_skipped", False) or (
                    getattr(run, "skipped", False)):
                # The fit rule stopped this unit before its
                # first call — run_scenario's own check, the
                # same rule run_unit applies to arms A-D
                # above. A unit the sweep never started is
                # skipped in exactly the sense a not-applicable
                # one is: counted in its arm's denominator,
                # never dropped, with the budget's own words
                # as its stop reason.
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
                # An empty reply with finish "error" is
                # the serving's own failure, never a
                # refusal (R2): the stage-1 run's 13
                # arm-B final-call errors carried finish
                # "error" and 0 tokens - the provider
                # failed the call, the model never
                # answered, and "refusal" would have
                # charged the model for the serving's
                # failure.
                result.status = "serving_error"
                result.stop_reason = (
                    "the serving returned an empty reply "
                    "with finish 'error' - a provider "
                    "failure, not a refusal")
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
            f"the common deadline ({effective_deadline:.0f}s) "
            "stopped the unit")
        client = made.get("client")
        if client is not None:
            # What the unit spent before the deadline, and the
            # calls the guard could not reconcile, are part of
            # what the unit cost.
            result.cost = client.spend
            result.unreconciled_liability = (
                client.unreconciled_liability)
        elif run is not None:
            result.cost = getattr(run, "cost", 0.0) or 0.0
            result.unreconciled_liability = float(
                getattr(run, "unreconciled_liability", 0.0) or 0.0)
            # The outer backstop fired before the pipeline could
            # book its spend to the sweep: charge the full
            # ceiling as liability, the conservative bound on
            # what the unit may have spent.
            if budget is not None:
                budget.record(ARM_CEILINGS[arm])
                result.unreconciled_liability += ARM_CEILINGS[arm]
    except (ProviderFailure, SpendGuardRefused,
            BudgetExceeded) as exc:
        # A provider that consumed its budget and emitted
        # nothing, or a call the guard refused: the unit did
        # not conclude, and the figures say which.
        result.status = "incomplete"
        result.stop_reason = f"{type(exc).__name__}: {exc}"
        client = made.get("client")
        if client is not None:
            result.cost = client.spend
            result.unreconciled_liability = (
                client.unreconciled_liability)
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

    # The frozen scorer scores every delivered answer (D50
    # (1): the scorer is the screen). A truncated answer is
    # scored as delivered and flagged.
    if result.answer:
        result.scorer = scorer.score(question_id, result.answer)
    # Arms A-D book their spend to the sweep here; arms
    # E and F's run_scenario already booked it.
    if (arm not in ("E", "F") and budget is not None
            and result.status not in ("skipped",)):
        budget.record(result.cost)
    return result


def _pipeline_record(run: Any) -> dict[str, Any]:
    """Arm E's internals, as the unit record carries them.

    The plan's success criteria and blockers, the run's
    final verdicts (review, rework_review, domain_review,
    judges, feasibility, triage - as the eval traces carry
    them; the review findings live in the review verdict,
    not in the iterations), the build-loop iterations (each
    carries its own verdicts, dissent and findings), the
    escalation verdict, the tokens by tier and the watchdog's
    typed record. An internals piece that never ran is None,
    not an empty shell: a run that never escalated has no
    escalation verdict, and a plan that never ran has no
    criteria to carry (convention 28: no evidence is a
    different claim from a measured zero).

    Ruling D51 adds what the run judged against and how it
    ended (record shape only): the asks - anchored, with
    the quotes that did not anchor beside them; every open
    dissent with its anchor; the notes the run counted; and
    the unendorsed candidate a terminal that is not
    completed kept, with its open dissents and their
    anchors.
    """
    verdicts = getattr(run, "verdicts", None) or {}
    plan = verdicts.get("plan")
    asks_anchored = verdicts.get("asks_anchored")
    return {
        "status": getattr(run, "status", None),
        "plan": (
            {
                "ready": plan.get("ready"),
                "success_criteria": list(
                    plan.get("success_criteria") or []),
                "blockers": list(plan.get("blockers") or []),
            }
            if isinstance(plan, dict) else None),
        "escalation": verdicts.get("escalation"),
        # The run's final verdicts, as the eval
        # traces carry them. A verdict whose node
        # never ran is None, not an empty shell.
        "verdicts": {
            name: verdicts.get(name) for name in (
                "review", "rework_review",
                "domain_review", "judges",
                "feasibility", "triage")},
        "iterations": list(getattr(run, "iterations", None) or []),
        "tokens_by_tier": dict(
            getattr(run, "tokens_by_tier", None) or {}),
        "watchdog": getattr(run, "watchdog", None),
        # Ruling D51 (1): the asks the run judged
        # against - the anchored quotes, and the
        # proposals that did not anchor, beside them.
        "asks": (
            {
                "anchored": list(
                    asks_anchored.get("anchored") or []),
                "quotes": list(
                    asks_anchored.get("quotes") or []),
                "demoted": list(
                    asks_anchored.get("demoted") or []),
            }
            if isinstance(asks_anchored, dict) else None),
        # Ruling D51 (3), (7): every open dissent with
        # its anchor, as the terminal's candidate carries
        # it; the notes the run counted; and the
        # unendorsed candidate itself.
        "open_dissents": list(
            (getattr(run, "candidate", None) or {}).get(
                "open_dissents") or []),
        # Ruling D51 (3): the notes the run counted —
        # judgments recorded and counted, never blocking
        # and not sent to the next revision. The harness
        # counts each demotion by kind (an unanchored ask
        # quote, an unanchored dissent, a red with no
        # anchor, a blocked_on entry that names no ask, a
        # consistency disagreement) in normalised_by_kind;
        # the count beside them is the notes total.
        "notes": dict(
            getattr(run, "normalised_by_kind", None) or {}),
        "notes_count": sum(
            (getattr(run, "normalised_by_kind", None)
             or {}).values()),
        "candidate": getattr(run, "candidate", None),
    }


def _serving_record(arm: str, servings: dict[str, Any]) -> Any:
    """The pin that served the unit, as the record carries it."""
    if arm == "C":
        return {"model_1": servings["C"][0],
                "model_2": servings["C"][1]}
    if arm in ("E", "F"):
        # Arm F runs arm E's path on arm E's standing
        # tiers — the same lineup, so the owner's one
        # ratified fingerprint covers both arms and the
        # stage-1 pins serve the whole re-measurement.
        return dict(servings["E"])
    return servings[arm]


async def _execute_arm(arm: str, question: str, question_id: str,
                        repetition: int, servings: dict[str, Any],
                        budget: SweepBudget | None,
                        deadline: float,
                        client_factory: Any,
                        tool_dispatcher: Any,
                        scenario_runner: Any,
                        spec: Any,
                        spec_f: Any = None,
                        pipeline_client_factory: Any = None,
                        client_holder: dict[str, Any] | None = None,
                        ) -> dict[str, Any]:
    """Dispatch to the arm's executor and shape its payload.

    ``client_holder`` receives the unit's client as soon as
    it exists, so the unit's record carries the figures the
    client booked (spend, unreconciled liability) even when
    a call fails mid-flight and the executor raises before
    its payload is shaped - the manifest's
    outstanding-liability rule.
    """
    unit_key = (question_id, repetition, arm)
    if arm in ("A", "D"):
        serving = servings[arm]
        client = _unit_client(
            unit_key, arm, serving, ARM_CEILINGS[arm], 1,
            factory=client_factory)
        if client_holder is not None:
            client_holder["client"] = client
        answer, finish_reasons = await _arm_single(
            arm, question, serving, client)
        return {"answer": answer, "client": client,
                "calls": client.calls,
                "finish_reasons": finish_reasons}
    if arm == "B":
        serving = servings["B"]
        client = _unit_client(
            unit_key, arm, serving, ARM_CEILINGS["B"],
            ARM_B_CALL_LIMIT, factory=client_factory)
        if client_holder is not None:
            client_holder["client"] = client
        answer, finish_reasons, invocations = await _arm_b(
            question, serving, client,
            tool_dispatcher=tool_dispatcher)
        return {"answer": answer, "client": client,
                "calls": client.calls,
                "finish_reasons": finish_reasons,
                "tool_invocations": invocations}
    if arm == "C":
        draft_serving, check_serving = servings["C"]
        client = _unit_client(
            unit_key, arm, draft_serving, ARM_CEILINGS["C"],
            ARM_C_CALL_LIMIT, factory=client_factory)
        if client_holder is not None:
            client_holder["client"] = client
        answer, finish_reasons, check = await _arm_c(
            question, draft_serving, check_serving, client)
        return {"answer": answer, "client": client,
                "calls": client.calls,
                "finish_reasons": finish_reasons,
                "check": check}
    # Arms E and F. The pipeline builds its own clients
    # (run_scenario's BoundedRunner sets their ceilings
    # from the scenario's max_calls and the sweep's
    # per-unit cap), so its factory takes no arguments —
    # a separate seam from the arms A-D factory above,
    # which names the arm's serving per unit. Arm E runs
    # the standing workflow (the harness's own
    # engineering-rnd after D51, #176); arm F runs the
    # same path through the verify-first workflow (D51
    # (8)), whose build loop is bounded to two
    # iterations — triage and asks, then at most four
    # model calls.
    pipeline_factory = (pipeline_client_factory
                        if pipeline_client_factory is not None
                        else (lambda: OpenRouterClient()))
    arm_spec = spec_f if arm == "F" else spec
    arm_runner = _arm_f if arm == "F" else _arm_e
    run, answer, kind = await arm_runner(
        question, question_id, repetition, deadline, budget,
        arm_spec, settings_lookup(),
        pipeline_factory, scenario_runner=scenario_runner)
    # The model calls after triage and asks: the triage
    # tier carries both the triage and the asks node,
    # so every other tier's calls are the ones that
    # happened after the asks were on the table.
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


# ── The results log: append-only, with resume ────────────────

class Tier3ResultsLog:
    """The experiment's append-only record.

    One JSONL line per unit, flushed as it is written, so an
    interrupted run keeps everything it paid for (the harness
    ResultsLog's discipline, B20's mirror included: the
    primary path sits in a git-ignored directory, and the
    mirror sits outside the repo where no git operation can
    reach it).

    Resume: on a restart with the same manifest version and
    order digest, the runner skips every unit already recorded
    and runs nothing twice or out of order. A unit in flight
    at the interruption — a ``unit_started`` with no ``unit``
    record — is charged its full ceiling against the sweep as
    unreconciled liability, then re-run.
    """

    def __init__(self, path: Path, config: dict[str, Any]) -> None:
        self.path = Path(path)
        self.config = config
        self.mirror_path = _durable_mirror(self.path)
        self._existing = self._read()
        self._header_written = bool(self._existing)
        self._check_plan_unchanged()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records

    def _check_plan_unchanged(self) -> None:
        """Resume only the same plan: the same manifest version
        and the same order digest, or refuse."""
        if not self._existing:
            return
        header = self._existing[0]
        if header.get("record") != "header":
            raise ValueError(
                f"{self.path}: the first record is not a header")
        for key in ("manifest_version", "order_sha256"):
            if header.get(key) != self.config.get(key):
                raise ValueError(
                    f"{self.path}: the recorded {key} is "
                    f"{header.get(key)!r}, this run's is "
                    f"{self.config.get(key)!r} — resume only the "
                    "same plan (the same manifest version and "
                    "order digest)")

    def _append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")
            handle.flush()
        if self.mirror_path is not None:
            self.mirror_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.mirror_path, "a",
                      encoding="utf-8") as handle:
                handle.write(json.dumps(record, default=str) + "\n")
                handle.flush()

    def header(self) -> None:
        """The header, once: the configuration the record is
        self-describing with (the manifest's execution rule)."""
        if self._header_written:
            return
        self._append({"record": "header", **self.config})
        self._header_written = True

    def unit_started(self, question_id: str, repetition: int,
                     arm: str) -> None:
        """The unit is in flight. A kill between this and the
        unit record leaves exactly this line, which is how the
        resume finds the unit to charge and re-run."""
        self._append({"record": "unit_started",
                      "question_id": question_id,
                      "repetition": repetition, "arm": arm})

    def unit(self, record: dict[str, Any]) -> None:
        self._append(record)

    def recorded_units(self) -> set[tuple[str, int, str]]:
        """Every unit with a complete record."""
        return {
            (r["question_id"], r["repetition"], r["arm"])
            for r in self._existing
            if r.get("record") == "unit"}

    def all_units(self) -> list[dict[str, Any]]:
        """Every unit record in the file, re-read from
        disk — the records this invocation wrote included.
        A resumed run's summary and measures cover the
        whole experiment, not only the units this
        invocation ran."""
        return [r for r in self._read()
                if r.get("record") == "unit"]

    def in_flight(self) -> tuple[str, int, str] | None:
        """The unit that was in flight when the run stopped:
        the last ``unit_started`` with no ``unit`` record.

        Read from disk, not the in-memory list: a kill
        writes its ``unit_started`` after this log was
        constructed, and the restart — and the run that
        left the unit in flight — must both see it."""
        existing = self._read()
        done = {
            (r["question_id"], r["repetition"], r["arm"])
            for r in existing
            if r.get("record") == "unit"}
        started: list[tuple[str, int, str]] = [
            (r["question_id"], r["repetition"], r["arm"])
            for r in existing
            if r.get("record") == "unit_started"]
        for key in reversed(started):
            if key not in done:
                return key
        return None

    def close(self) -> None:
        """Nothing to flush: every line is flushed as written.
        The mirror is the same file's copy, already flushed."""
        return None

    def __enter__(self) -> "Tier3ResultsLog":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


def default_results_path(mode: str) -> Path:
    """evals/results/<utc-timestamp>-tier3-<mode>.jsonl"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return RESULTS_DIR / f"{stamp}-tier3-{mode}.jsonl"


# ── The five success measures, computed both ways ──────
#
# D50 (1): the scorer is the screen, two hand readings are
# the primary measure. Every measure is computed scorer-only
# and again with the readers' verdicts where they read —
# the read verdict where read, the scorer's elsewhere — and
# the two are reported side by side.

def _effective_verdict(record: dict[str, Any],
                        readings: dict[tuple[str, int, str],
                                            str] | None) -> str:
    """The unit's verdict: the readers' where they read,
    the scorer's elsewhere. An unscored unit (a failure
    class) is not a pass either way."""
    key = (record["question_id"], record["repetition"],
           record["arm"])
    if readings and key in readings:
        return readings[key]
    return ((record.get("scorer") or {}).get("verdict")
            or "NOT_SCORED")


def compute_measures(records: list[dict[str, Any]],
                     readings: dict[tuple[str, int, str],
                                         str] | None = None
                     ) -> dict[str, Any]:
    """The manifest's five success measures, over the unit
    records. The denominator is the planned units, so an
    incomplete, refused or timed-out unit is 0 delivered,
    never dropped."""
    arms = sorted({record["arm"] for record in records})
    planned_per_arm: dict[str, int] = {}
    for record in records:
        planned_per_arm[record["arm"]] = (
            planned_per_arm.get(record["arm"], 0) + 1)

    # 1. Delivered correctness per arm: the count of the
    # planned units whose delivered answer the scorer (or
    # the readers, where they read) scores PASS.
    delivered_correctness = {}
    for arm in arms:
        arm_records = [r for r in records if r["arm"] == arm]
        delivered = [r for r in arm_records
                     if _effective_verdict(r, readings) == "PASS"
                     and (r.get("delivered")
                          or r.get("delivered_kind") == "shipped")]
        delivered_correctness[arm] = {
            "delivered_correct": len(delivered),
            "planned": planned_per_arm[arm],
            "fraction": (len(delivered) / planned_per_arm[arm]
                         if planned_per_arm[arm] else 0.0),
            "not_delivered": sum(
                1 for r in arm_records if not r.get("delivered")),
            "approved_not_shipped": sum(
                1 for r in arm_records
                if r.get("delivered_kind") == "approved, not shipped"),
        }

    # 2. Per-question repeat outcomes: for each question
    # and arm, how many of its repetitions delivered
    # correct — the 0/3..3/3 distribution.
    repeat_outcomes: dict[str, dict[str, int]] = {}
    for arm in arms:
        distribution: dict[str, int] = {}
        for question_id in sorted(
                {r["question_id"] for r in records
                 if r["arm"] == arm}):
            correct = sum(
                1 for r in records
                if r["arm"] == arm and r["question_id"] == question_id
                and _effective_verdict(r, readings) == "PASS"
                and (r.get("delivered")
                     or r.get("delivered_kind") == "shipped"))
            key = f"{correct}/{REPITIONS if arm in ARMS else PILOT_REPETITIONS}"
            distribution[key] = distribution.get(key, 0) + 1
        repeat_outcomes[arm] = distribution

    # 3 and 4. Paired wins and losses, against A and
    # against D: for each question, arm X's correct-
    # repetition count against the reference arm's.
    def _correct_counts(arm: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for question_id in {r["question_id"] for r in records
                            if r["arm"] == arm}:
            counts[question_id] = sum(
                1 for r in records
                if r["arm"] == arm and r["question_id"] == question_id
                and _effective_verdict(r, readings) == "PASS"
                and (r.get("delivered")
                     or r.get("delivered_kind") == "shipped"))
        return counts

    def _paired(reference: str) -> dict[str, dict[str, int]]:
        if reference not in arms:
            return {}
        reference_counts = _correct_counts(reference)
        paired: dict[str, dict[str, int]] = {}
        for arm in arms:
            if arm == reference:
                continue
            wins = losses = ties = 0
            for question_id, reference_count in reference_counts.items():
                arm_count = _correct_counts(arm).get(question_id, 0)
                if arm_count > reference_count:
                    wins += 1
                elif arm_count < reference_count:
                    losses += 1
                else:
                    ties += 1
            paired[arm] = {"wins": wins, "losses": losses,
                             "ties": ties}
        return paired

    # 5. Total cost and latency, including every failure.
    total_cost = sum(r.get("cost", 0.0) for r in records)
    liability = sum(r.get("unreconciled_liability", 0.0)
                    for r in records)
    seconds = [r.get("seconds", 0.0) for r in records]
    by_status: dict[str, int] = {}
    for record in records:
        by_status[record["status"]] = (
            by_status.get(record["status"], 0) + 1)

    return {
        "delivered_correctness_per_arm": delivered_correctness,
        "per_question_repeat_outcomes": repeat_outcomes,
        "paired_wins_and_losses_against_A": _paired("A"),
        "comparison_with_D": _paired("D"),
        "total_cost_and_latency_including_failures": {
            "total_cost": total_cost,
            "unreconciled_liability": liability,
            "total_seconds": sum(seconds),
            "mean_seconds": (sum(seconds) / len(seconds)
                             if seconds else 0.0),
            "max_seconds": max(seconds) if seconds else 0.0,
            "units": len(records),
            "by_status": by_status,
        },
    }


# ── The reading sheet (D50 (1)) ────────────────────────

READING_SAMPLE_PER_ARM = 10


def export_reading_sheet(records: list[dict[str, Any]],
                          questions: dict[str, dict[str, Any]],
                          keys: list[dict[str, Any]],
                          path: Path,
                          seed: int) -> dict[str, Any]:
    """The reading sheet: every scorer FAIL and a seeded
    sample of ten scorer PASSes per arm, in a seeded order,
    with no arm label.

    Two readers fill it in independently, item by item,
    each with a verdict. The sheet carries the question,
    the delivered answer and the key's required items —
    everything a reading needs, and nothing that names the
    arm (the readers are blind to it).
    """
    key_by_id = {key["id"]: key for key in keys}
    entries: list[dict[str, Any]] = []
    per_arm: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for arm in sorted({r["arm"] for r in records}):
        arm_records = [r for r in records if r["arm"] == arm]
        fails = [r for r in arm_records
                 if ((r.get("scorer") or {}).get("verdict")
                     == "FAIL")]
        passes = [r for r in arm_records
                  if ((r.get("scorer") or {}).get("verdict")
                      == "PASS")]
        # The seeded sample of ten, from the seeded order.
        sample_size = min(READING_SAMPLE_PER_ARM, len(passes))
        sampled = (random.Random(seed)
                   .sample(sorted(passes, key=_record_sort_key),
                           sample_size) if sample_size else [])
        per_arm[arm] = {"fails": fails, "sampled": sampled,
                         "passes": len(passes),
                         "fails_total": len(fails)}
        entries.extend(fails)
        entries.extend(sampled)
    # The seeded order, and no arm label: the readers see
    # the sheet, not the experiment.
    random.Random(seed).shuffle(entries)
    sheet_entries = []
    for index, record in enumerate(entries, 1):
        key = key_by_id.get(record["question_id"], {})
        sheet_entries.append({
            "entry": index,
            "question_id": record["question_id"],
            "question": questions.get(
                record["question_id"], {}).get("question"),
            "answer": record.get("answer"),
            "required_items": key.get("required_items", []),
            "scorer_verdict": (record.get("scorer") or {}).get(
                "verdict"),
            "scorer_items": (record.get("scorer") or {}).get(
                "items", []),
            "reading_1": None,
            "reading_2": None,
            "resolution": None,
        })
    sheet = {
        "record": "reading-sheet",
        "seed": seed,
        "sample_per_arm": READING_SAMPLE_PER_ARM,
        "per_arm": {arm: {"passes": info["passes"],
                           "fails": info["fails_total"],
                           "sampled": len(info["sampled"])}
                    for arm, info in per_arm.items()},
        "entries": sheet_entries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sheet, indent=2, default=str)
                    + "\n", encoding="utf-8")
    return sheet


def _record_sort_key(record: dict[str, Any]) -> tuple[str, int, str]:
    return (record["question_id"], record["repetition"],
            record["arm"])


def merge_readings(sheet: dict[str, Any],
                    reader_1: dict[int, str],
                    reader_2: dict[int, str]
                    ) -> dict[str, Any]:
    """The merge step: the two readers' verdicts side by
    side, their disagreements listed, each carrying the
    resolution the adjudication records.

    A disagreement is reported, never settled by editing
    the scorer inside the run that found it (D50 (1)).
    """
    merged: dict[int, str] = {}
    disagreements: list[dict[str, Any]] = []
    unread: list[int] = []
    for entry in sheet["entries"]:
        index = entry["entry"]
        first = reader_1.get(index)
        second = reader_2.get(index)
        if first is None or second is None:
            unread.append(index)
            continue
        if first == second:
            merged[index] = first
        else:
            disagreements.append({
                "entry": index,
                "question_id": entry["question_id"],
                "reading_1": first,
                "reading_2": second,
                "resolution": None,
            })
    return {"merged": merged, "disagreements": disagreements,
            "unread": unread}


# ── The summary ────────────────────────────────────────

def summarize(records: list[dict[str, Any]],
               measures: dict[str, Any],
               title: str,
               charged_liability: float = 0.0) -> str:
    """The run summary: per arm, the units by status, the
    delivered correctness (scorer-only), the spend and the
    latency; then the totals. Every failure class is in its
    arm's denominator, and the line says so.

    The charged liability is the in-flight unit's ceiling,
    booked to the sweep by the restart that discovered it —
    part of what the sweep spent, and said so."""
    lines = [title]
    correctness = measures["delivered_correctness_per_arm"]
    for arm in sorted(correctness):
        arm_records = [r for r in records if r["arm"] == arm]
        by_status: dict[str, int] = {}
        for record in arm_records:
            by_status[record["status"]] = (
                by_status.get(record["status"], 0) + 1)
        status_line = ", ".join(
            f"{count} {status}" for status, count
            in sorted(by_status.items()))
        row = correctness[arm]
        lines.append(
            f"arm {arm}: {row['planned']} units — {status_line}; "
            f"delivered correctness {row['delivered_correct']}"
            f"/{row['planned']} ({row['fraction']:.4f}); "
            f"${sum(r.get('cost', 0.0) for r in arm_records):.4f}; "
            f"{sum(r.get('seconds', 0.0) for r in arm_records):.0f}s")
    totals = measures["total_cost_and_latency_including_failures"]
    lines.append(
        f"total: {totals['units']} units, "
        f"${totals['total_cost'] + charged_liability:.4f} spent"
        + (f" (${charged_liability:.4f} of it the in-flight "
           f"unit's liability charge)" if charged_liability else "")
        + f", ${totals['unreconciled_liability']:.4f} unreconciled "
        f"liability, {totals['total_seconds']:.0f}s wall clock "
        f"(mean {totals['mean_seconds']:.1f}s, max "
        f"{totals['max_seconds']:.1f}s)")
    lines.append("statuses: " + ", ".join(
        f"{count} {status}" for status, count
        in sorted(totals["by_status"].items())))
    return "\n".join(lines)


def failure_census(records: list[dict[str, Any]]) -> dict[str, int]:
    """Every failure class, counted. The census is the
    dry run's proof that each class the command names is
    included at least once, and each is counted in its
    arm's denominator."""
    census: dict[str, int] = {}
    for record in records:
        census[record["status"]] = census.get(record["status"], 0) + 1
        if record["arm"] == "C" and record.get("check"):
            census[f"check:{record['check'].get('status')}"] = (
                census.get(f"check:{record['check'].get('status')}",
                           0) + 1)
        if record["arm"] in ("E", "F") and record.get("delivered_kind"):
            census[f"delivery:{record['delivered_kind']}"] = (
                census.get(f"delivery:{record['delivered_kind']}",
                           0) + 1)
        # The budget-stop class: a unit the sweep's fit
        # rule did not start — its stop reason names the
        # budget — counted in its arm's denominator, never
        # dropped (the dry run's proof that the class is
        # included at least once).
        if (record.get("status") == "skipped"
                and "budget" in str(
                    record.get("stop_reason", "")).lower()):
            census["budget_stop"] = (
                census.get("budget_stop", 0) + 1)
        # The tool-failure class: a unit whose tool loop
        # recorded a failed invocation (the tool failed;
        # the model continued without it).
        if any(not invocation.get("ok", True)
               for invocation in record.get("tool_invocations")
               or []):
            census["tool_failure"] = (
                census.get("tool_failure", 0) + 1)
    return census


# ── The re-measurement's report (command 121) ───────
#
# The eight tables the manifest's tier3-8 registration
# lists, computed from the units' own records. Every
# figure re-derives from the records the run wrote;
# none is carried in from anywhere else.

def _keys_at_3sf(
        keys: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The frozen keys with Q23's two force items widened
    to the tolerance that accepts every 3-significant-figure
    rounding — K1, not ruled, reported side by side with the
    key-strict column, never instead of it. 12.35 and 17.65
    kN at ±0.01 kN become ±0.05 kN, which accepts 12.3 and
    12.4, and 17.6 and 17.7 kN; every other item scores
    identically under both columns. A deep copy — the frozen
    keys the scorer holds are never touched."""
    widened = copy.deepcopy(keys)
    for key in widened:
        if key.get("id") != "Q23":
            continue
        for item in key.get("required_items") or []:
            if str(item.get("item", "")).endswith("force"):
                item["tolerance_or_variants"] = str(
                    item.get("tolerance_or_variants", "")
                ).replace("\\pm0.01", "\\pm0.05")
    return widened


def _delivered(record: dict[str, Any]) -> bool:
    """The delivered predicate, as the record carries it:
    arms A-D delivered on status, arms E and F on the
    delivery kind (D50 (3): an unendorsed candidate is
    read and reported, never counted as delivered)."""
    if record.get("arm") in ("E", "F"):
        return record.get("delivered_kind") == "shipped"
    return record.get("status") == "delivered"


def _verdict(record: dict[str, Any],
             keys: list[dict[str, Any]]) -> str | None:
    """The scorer's verdict of the unit's answer against
    a keys list — None when the unit has no answer to
    score (an incomplete, refused, deadline or skipped
    unit is not a FAIL; it is its own failure class)."""
    answer = record.get("answer")
    if not answer or not str(answer).strip():
        return None
    return scorer.score(
        record["question_id"], str(answer),
        keys=keys).get("verdict")


def _quantity_signature(answer: str) -> list[tuple[str, float]]:
    """The answer's stated quantities as the signature
    repetition agreement is measured on (prediction 8):
    every (value, unit) pair the answer states, converted
    to its base unit and rounded, so two answers that
    state the same values in different units or units of
    the same dimension agree."""
    signature: list[tuple[str, float]] = []
    for value, unit in scorer.extract_quantities(answer):
        base = scorer._to_base(value, unit)
        if base is not None:
            dimension, base_value = base
            signature.append(
                (dimension, round(base_value, 6)))
    return sorted(signature)


def _open_dissents(record: dict[str, Any]) -> list[dict[str, Any]]:
    """The record's open dissents, with their anchors, as
    the pipeline record carries them (D51 (3), (7))."""
    return list(((record.get("pipeline") or {}).get(
        "open_dissents")) or [])


def _unanchored_blocks(record: dict[str, Any]) -> list[dict[str, Any]]:
    """The dissent entries the record carries with no
    anchor (prediction 3's exhibit): an entry with no ask,
    no quote and no hazard — a judgment that failed the
    work without pointing at the request."""
    return [entry for entry in _open_dissents(record)
            if entry.get("ask") is None
            and not str(entry.get("quote") or "")
            and not entry.get("hazard")]


def remeasure_report(records: list[dict[str, Any]],
                     questions: dict[str, dict[str, Any]]
                     | list[dict[str, Any]],
                     keys: list[dict[str, Any]]
                     ) -> dict[str, Any]:
    """The re-measurement's report: the eight tables the
    manifest's tier3-8 registration lists, from the units'
    own records. ``records`` are the unit records the run
    wrote (``result.record()``); ``questions`` the frozen
    set as a dict by id (or a list of the same); ``keys``
    the frozen keys."""
    keys_3sf = _keys_at_3sf(keys)
    if isinstance(questions, dict):
        question_map = questions
    else:
        question_map = {q["id"]: q for q in questions}
    arms = REMEASURE_ARMS

    # Table 1 — per-arm delivered-correct of planned
    # units, key-strict (primary) and 3 s.f. side by
    # side. A skipped unit stays in its arm's
    # denominator: the fit rule counts it, never drops
    # it. A unit with no answer has no verdict — its
    # failure class is its own row in the census, not a
    # FAIL.
    per_arm: dict[str, Any] = {}
    for arm in arms:
        arm_records = [r for r in records
                       if r.get("arm") == arm]
        delivered = [r for r in arm_records
                     if _delivered(r)]
        strict = [r for r in delivered
                  if _verdict(r, keys) == "PASS"]
        at_3sf = [r for r in delivered
                  if _verdict(r, keys_3sf) == "PASS"]
        per_arm[arm] = {
            "planned": len(arm_records),
            "delivered": len(delivered),
            "delivered_correct_key_strict": len(strict),
            "delivered_correct_3sf": len(at_3sf),
            "delivered_correct_of_planned_key_strict": (
                len(strict) / len(arm_records)
                if arm_records else None),
            "delivered_correct_of_planned_3sf": (
                len(at_3sf) / len(arm_records)
                if arm_records else None),
            "delivered_correct_of_delivered_key_strict": (
                len(strict) / len(delivered)
                if delivered else None),
            "delivered_correct_of_delivered_3sf": (
                len(at_3sf) / len(delivered)
                if delivered else None),
        }

    # Table 2 — Q1-Q5 shown separately: the five
    # questions the calibration pilot exposed, where a
    # single call's own accuracy is the reference the
    # harness is judged against.
    calibration_ids = [f"Q{n}" for n in range(1, 6)]
    calibration: dict[str, Any] = {}
    for arm in arms:
        arm_records = [r for r in records
                       if r.get("arm") == arm
                       and r.get("question_id")
                       in calibration_ids]
        delivered = [r for r in arm_records
                     if _delivered(r)]
        strict = [r for r in delivered
                  if _verdict(r, keys) == "PASS"]
        at_3sf = [r for r in delivered
                  if _verdict(r, keys_3sf) == "PASS"]
        calibration[arm] = {
            "planned": len(arm_records),
            "delivered": len(delivered),
            "delivered_correct_key_strict": len(strict),
            "delivered_correct_3sf": len(at_3sf),
        }

    # Table 3 — each arm paired against A, by question:
    # per question, how many of the arm's three
    # repetitions held the answer (delivered and
    # key-strict correct), beside A's own count. E'
    # ran stage 1's seven only, so its pairing covers
    # those.
    pairing: dict[str, dict[str, Any]] = {}
    for question_id in question_map:
        row: dict[str, Any] = {
            "stage1": question_id in STAGE1_QUESTION_IDS,
        }
        for arm in arms:
            arm_records = [
                r for r in records
                if r.get("question_id") == question_id
                and r.get("arm") == arm]
            row[arm] = sum(
                1 for r in arm_records
                if _delivered(r)
                and _verdict(r, keys) == "PASS")
        pairing[question_id] = row

    # Table 4 — median cost and median latency per arm,
    # over the units that ran (a skipped unit never
    # started, so it has no cost or latency to median).
    medians: dict[str, Any] = {}
    for arm in arms:
        arm_records = [r for r in records
                       if r.get("arm") == arm
                       and r.get("status") != "skipped"]
        costs = [float(r.get("cost") or 0.0)
                 for r in arm_records]
        seconds = [float(r.get("seconds") or 0.0)
                   for r in arm_records]
        medians[arm] = {
            "units": len(arm_records),
            "median_cost": (statistics.median(costs)
                            if costs else None),
            "median_seconds": (statistics.median(seconds)
                               if seconds else None),
        }

    # Table 5 — F's first answer against its final
    # answer, among F units whose check forced a
    # revision (prediction 9): the first iteration's
    # answer beside the answer the run ended on, both
    # scored. The prediction is reported, not tested,
    # when fewer than five units revised.
    f_units = [r for r in records
               if r.get("arm") == "F"]
    transitions = {
        "right_to_right": 0, "right_to_wrong": 0,
        "wrong_to_right": 0, "wrong_to_wrong": 0,
        "no_first_answer": 0,
    }
    revised = 0
    for record in f_units:
        iterations = list(((record.get("pipeline")
                            or {}).get("iterations")
                           or []))
        answers = [i.get("implement_summary")
                   for i in iterations
                   if i.get("implement_summary")]
        if len(answers) < 2:
            # One iteration: the check passed (or the
            # run ended) before any revision, so this
            # unit is not in the prediction's population.
            continue
        revised += 1
        first, final = answers[0], record.get("answer")
        if not first or not final:
            transitions["no_first_answer"] += 1
            continue
        first_verdict = scorer.score(
            record["question_id"], str(first),
            keys=keys).get("verdict")
        final_verdict = _verdict(record, keys)
        if first_verdict == "PASS" and final_verdict == "PASS":
            transitions["right_to_right"] += 1
        elif first_verdict == "PASS":
            transitions["right_to_wrong"] += 1
        elif final_verdict == "PASS":
            transitions["wrong_to_right"] += 1
        else:
            transitions["wrong_to_wrong"] += 1
    first_vs_final = {
        "revised_units": revised,
        "transitions": transitions,
        "testable": revised >= 5,
        "note": ("the prediction is reported, not "
                 "tested, until five units revise"
                 if revised < 5 else
                 "five or more units revised: the "
                 "prediction is tested"),
    }

    # Table 6 — the unresolved candidates read
    # (prediction 7): every unendorsed candidate of E'
    # and F, with its open dissents and their anchors,
    # and the candidates' scorer verdicts against the
    # delivered answers'.
    candidates: dict[str, Any] = {}
    for arm in ("E", "F"):
        unresolved = [
            r for r in records
            if r.get("arm") == arm
            and r.get("delivered_kind") in (
                "unendorsed candidate",
                "approved, not shipped")]
        delivered = [
            r for r in records
            if r.get("arm") == arm
            and r.get("delivered_kind") == "shipped"]
        wrong = lambda rows: sum(      # noqa: E731
            1 for r in rows
            if _verdict(r, keys) == "FAIL")
        scored = lambda rows: sum(     # noqa: E731
            1 for r in rows
            if _verdict(r, keys) is not None)
        candidates[arm] = {
            "unresolved_count": len(unresolved),
            "delivered_count": len(delivered),
            "candidates_wrong": wrong(unresolved),
            "candidates_scored": scored(unresolved),
            "candidates_wrong_rate": (
                wrong(unresolved) / scored(unresolved)
                if scored(unresolved) else None),
            "delivered_wrong": wrong(delivered),
            "delivered_scored": scored(delivered),
            "delivered_wrong_rate": (
                wrong(delivered) / scored(delivered)
                if scored(delivered) else None),
            "candidates": [
                {
                    "question_id": r["question_id"],
                    "repetition": r["repetition"],
                    "delivered_kind": r["delivered_kind"],
                    "scorer_verdict": _verdict(r, keys),
                    "open_dissents": [
                        {
                            "judge": d.get("judge"),
                            "ask": d.get("ask"),
                            "quote": d.get("quote"),
                            "hazard": d.get("hazard"),
                        } for d in _open_dissents(r)],
                } for r in unresolved],
        }

    # Table 7 — repetition agreement against correctness
    # (prediction 8): per question and arm, whether all
    # three repetitions agree on every stated value, and
    # whether the arm held the question (any repetition
    # delivered and correct). A question no repetition
    # states a quantity for carries no agreement signal
    # and is counted apart, not as agreement.
    agreement = {"arms": {}}
    for arm in arms:
        arm_records = [r for r in records
                       if r.get("arm") == arm]
        by_question: dict[str, list[dict[str, Any]]] = {}
        for record in arm_records:
            by_question.setdefault(
                record["question_id"], []).append(record)
        table = {"agree_held": 0, "agree_missed": 0,
                 "disagree_held": 0, "disagree_missed": 0,
                 "no_quantities": 0, "questions": {}}
        for question_id, rows in sorted(
                by_question.items()):
            signatures = [
                _quantity_signature(str(r.get("answer")
                                        or ""))
                for r in rows]
            held = any(
                _delivered(r) and _verdict(r, keys)
                == "PASS" for r in rows)
            if not any(signatures):
                table["no_quantities"] += 1
                verdict = "no_quantities"
            elif all(s == signatures[0]
                     for s in signatures):
                verdict = "agree"
                if held:
                    table["agree_held"] += 1
                else:
                    table["agree_missed"] += 1
            else:
                verdict = "disagree"
                if held:
                    table["disagree_held"] += 1
                else:
                    table["disagree_missed"] += 1
            table["questions"][question_id] = {
                "agreement": verdict, "held": held}
        agreement["arms"][arm] = table

    # Table 8 — the unanchored blocks per E' and F unit
    # (prediction 3): every dissent the record carries
    # with no anchor, per unit. The prediction says
    # there are none; the table is the exhibit that
    # would name one.
    unanchored: dict[str, Any] = {"arms": {}}
    for arm in ("E", "F"):
        arm_records = [r for r in records
                       if r.get("arm") == arm]
        per_unit = []
        for record in arm_records:
            blocks = _unanchored_blocks(record)
            if blocks:
                per_unit.append({
                    "question_id": record["question_id"],
                    "repetition": record["repetition"],
                    "unanchored_blocks": [
                        {"judge": d.get("judge"),
                         "ask": d.get("ask"),
                         "quote": d.get("quote"),
                         "hazard": d.get("hazard")}
                        for d in blocks],
                })
        unanchored["arms"][arm] = {
            "units": len(arm_records),
            "units_with_unanchored_blocks": len(per_unit),
            "units_detail": per_unit,
        }

    return {
        "arms": list(arms),
        "keys": "frozen (the scorer's own, unmodified)",
        "keys_3sf": ("the frozen keys with Q23's two "
                     "force items widened to ±0.05 kN "
                     "(K1, not ruled)"),
        "per_arm": per_arm,
        "calibration_q1_q5": calibration,
        "paired_against_a_by_question": pairing,
        "median_cost_and_latency": medians,
        "f_first_vs_final": first_vs_final,
        "unresolved_candidates": candidates,
        "repetition_agreement_vs_correctness": agreement,
        "unanchored_blocks": unanchored,
    }


# ── The experiment driver ──────────────────────────────

def _manifest_version() -> str:
    """The manifest's own version, as the results header
    names it (the resume guard compares against it)."""
    with open(TIER3 / "manifest.json", encoding="utf-8") as handle:
        return json.load(handle)["versions"]["manifest"]


def _pre_registration_digests() -> dict[str, str]:
    """The pre-registration's two digests, as the
    manifest's tier3-8 registration carries them: the
    sha256 of the D51 record's section 9 (the nine
    predictions) and of its section 7 (the decision
    table), copied verbatim and committed before any
    paid unit. The results header names them, so a
    results file names the pre-registration it was
    measured against."""
    with open(TIER3 / "manifest.json",
              encoding="utf-8") as handle:
        pre = (json.load(handle)
               .get("remeasurement", {})
               .get("pre_registration", {}))
    return {
        "predictions_section_9_sha256":
            pre.get("predictions_section_9_sha256"),
        "decision_table_section_7_sha256":
            pre.get("decision_table_section_7_sha256"),
    }


def _standing_spec():
    """The workflow the harness ships, loaded the way the
    eval CLI loads it. Arm E runs the pipeline as it ships."""
    from autornd.graph.spec import load as load_spec
    return load_spec(
        ROOT / "workflows" / f"{harness_settings.autornd_workflow}.yaml")


def _verify_first_spec():
    """The verify-first workflow (Ruling D51 (8)), loaded
    the same way. Arm F runs the pipeline's own path —
    arm E's executor, the same tiers, the same pins —
    through this workflow instead of the standing one."""
    from autornd.graph.spec import load as load_spec
    return load_spec(ROOT / "workflows" / "verify-first.yaml")


async def run_experiment(
        mode: str,
        results_path: str | Path | None = None,
        stop_after: int | None = None,
        client_factory: Any = None,
        tool_dispatcher: Any = None,
        scenario_runner: Any = None,
        pipeline_client_factory: Any = None,
        catalogue: list[dict[str, Any]] | None = None,
        deadline_overrides: dict[tuple[str, int, str],
                                      float] | None = None,
        ) -> dict[str, Any]:
    """One experiment run: the gates, the free preflight,
    then every unit of the plan in the recorded order, under
    the sweep budget, each recorded as it finishes.

    The gates and the preflight come before any network
    call, and a refusal names each missing gate or each
    refusal case. On a restart with the same manifest
    version and order digest, every unit already recorded
    is skipped and nothing runs twice or out of order; the
    unit in flight at the interruption is charged its full
    ceiling against the sweep as unreconciled liability,
    then re-run.
    """
    pilot = mode == "pilot"
    remeasure = mode == "remeasure"
    tier3 = Tier3Settings()
    servings = resolve_servings(tier3)
    fingerprint = servings_fingerprint(servings)

    # The three ratification gates, before any network call.
    missing = gate_report(tier3, servings, fingerprint,
                            pilot, mode=mode)
    if missing:
        raise ExperimentRefused(
            "the ratification gates are not cleared",
            servings, fingerprint, missing)

    # The free preflight, before the first unit.
    if catalogue is None:
        catalogue = await fetch_catalogue(
            confirm={serving for serving in _all_servings(servings)})
    report = run_preflight(servings, catalogue)
    if report.refusals:
        raise ExperimentRefused(
            "the preflight refused to start",
            servings, fingerprint, report.refusals)

    arms = (REMEASURE_ARMS if remeasure
            else PILOT_ARMS if pilot else ARMS)
    repetitions = (REPITIONS if remeasure or not pilot
                   else PILOT_REPETITIONS)
    seed = (REMEASURE_SEED if remeasure
            else PILOT_SEED if pilot else SEED)
    # The staged plan's stage-1 main run enumerates over
    # the seven selected questions (the selection rule the
    # manifest registers); the pilot and a stage-2 run
    # enumerate over the frozen set's own. The
    # re-measurement's plan is its own: arms A, D and F
    # over the frozen set's twenty-five questions and
    # arm E over stage 1's seven, three repetitions each,
    # interleaved and shuffled once with the registered
    # seed (the guard test reconstructs the order
    # independently and compares the digest).
    if remeasure:
        order = remeasure_order(seed)
    else:
        order_questions = (load_questions() if pilot
                           else stage1_questions())
        order = build_order(seed, repetitions, arms,
                            order_questions)
    digest = order_digest(order)
    authorization = (REMEASURE_CEILING if remeasure
                     else PILOT_CEILING if pilot
                     else MAIN_CEILING)

    path = (Path(results_path) if results_path is not None
            else default_results_path(mode))
    log = Tier3ResultsLog(path, config={
        "record": "header",
        "mode": mode,
        "manifest_version": _manifest_version(),
        "dataset_version": scorer.MANIFEST["dataset_version"],
        "scorer_version": scorer.SCORER_VERSION,
        "seed": seed,
        "selection_seed": (None if pilot
                           else SELECTION_SEED),
        "stage1_question_ids": (list(STAGE1_QUESTION_IDS)
                                if not pilot else None),
        "repetitions": repetitions,
        "arms": list(arms),
        "order_sha256": digest,
        "order_units": len(order),
        "servings": servings,
        "servings_fingerprint": fingerprint,
        "ceilings": dict(ARM_CEILINGS),
        "authorization_ceiling": authorization,
        "max_tokens": REGISTERED_MAX_TOKENS,
        "temperature": REGISTERED_TEMPERATURE,
        "deadline_seconds": DEADLINE_SECONDS,
        "arm_b_call_limit": ARM_B_CALL_LIMIT,
        "arm_b_tool_invocations": ARM_B_TOOL_INVOCATION_LIMIT,
        "arm_c_call_limit": ARM_C_CALL_LIMIT,
        "arm_c_check_attempts": ARM_C_CHECK_ATTEMPTS,
        "arm_e_call_limit": ARM_E_CALL_LIMIT,
        "arm_f_call_limit": (ARM_F_CALL_LIMIT
                             if remeasure else None),
        # The re-measurement's registered plan, as the
        # header names it: the interleaved order's seed,
        # the authorisation, and the pre-registration's
        # two digests (the D51 record's sections 9 and 7,
        # copied verbatim into the manifest and never
        # edited afterwards).
        "remeasurement": ({
            "arms": list(REMEASURE_ARMS),
            "seed": REMEASURE_SEED,
            "authorization_ceiling": REMEASURE_CEILING,
            "arm_f_call_limit": ARM_F_CALL_LIMIT,
            "pre_registration": _pre_registration_digests(),
        } if remeasure else None),
        "pins": {name: getattr(tier3, name) for name in (
            "tier3_arm_a", "tier3_arm_b", "tier3_arm_c_1",
            "tier3_arm_c_2", "tier3_arm_d",
            "tier3_servings_ratified",
            "tier3_spend_authorized" if not pilot
            else "tier3_pilot_authorized")},
    })

    budget = SweepBudget(cap=authorization)
    questions = {question["id"]: question
                 for question in load_questions()}
    keys = scorer.KEYS
    spec = _standing_spec() if "E" in arms else None
    spec_f = _verify_first_spec() if "F" in arms else None
    records: list[dict[str, Any]] = []
    log.header()

    # Resume: skip every unit already recorded, and charge
    # the unit in flight at the interruption its full
    # ceiling as unreconciled liability before re-running it.
    recorded = log.recorded_units()
    in_flight = log.in_flight()
    charged = 0.0
    if in_flight is not None:
        charged = ARM_CEILINGS[in_flight[2]]
        budget.record(charged)

    started = 0
    killed_at: int | None = None
    for index, unit_key in enumerate(order):
        key = tuple(unit_key)
        if key in recorded:
            continue
        if stop_after is not None and started >= stop_after:
            # The kill: the next unit is marked in flight and
            # the run stops there, exactly as a process kill
            # leaves the record.
            log.unit_started(*key)
            killed_at = index
            break
        log.unit_started(*key)
        result = await run_unit(
            key, questions, servings, budget,
            deadline_overrides=deadline_overrides,
            client_factory=client_factory,
            tool_dispatcher=tool_dispatcher,
            scenario_runner=scenario_runner,
            spec=spec, spec_f=spec_f,
            pipeline_client_factory=pipeline_client_factory)
        log.unit(result.record())
        records.append(result.record())
        started += 1
    # The unit this invocation left in flight (the kill's
    # exhibit), read back the way a restart reads it.
    left_in_flight = (log.in_flight() if killed_at is not None
                      else None)
    # The record is the experiment's, not the invocation's:
    # a resumed run's summary, measures and census cover
    # every unit the file holds, including the units the
    # interrupted invocation recorded.
    all_records = log.all_units()
    log.close()

    measures = compute_measures(all_records)
    summary = summarize(
        all_records, measures,
        f"tier-3 {mode} run — {len(order)} planned units, "
        f"seed {seed}, order sha256 {digest[:12]}…",
        charged_liability=charged)
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
        "resumed": in_flight is not None,
        "in_flight": in_flight,
        "left_in_flight": left_in_flight,
        "charged_liability": charged,
        "killed_at": killed_at,
        "budget": {"cap": budget.cap, "spent": budget.spent,
                    "started": budget.started,
                    "skipped": budget.skipped},
        "order_units": len(order),
        "questions": questions,
        "keys": keys,
        "seed": seed,
    }


# ── The mocked dry run ─────────────────────────────────
#
# The dry run runs the real machinery — the gates, the
# preflight, the plan and its order, the arm executors, the
# deadline, the scoring, the record, the resume, the
# measures — with the model-serving layer mocked: a scripted
# client for arms A-D, a fixture catalogue, and a stand-in
# at the pipeline boundary for arm E (the pipeline's own
# execution is proven by the harness's suite; everything
# above the boundary is the experiment's machinery and runs
# for real). No network, no spend.

# The mock lineup: serving names that are placeholders, not
# model ids (non-negotiable 6). Arm B's pin is arm A's pin,
# as the ratification gate requires.
DRY_RUN_SERVINGS = {
    "A": "dryrun/arm-a",
    "B": "dryrun/arm-a",
    "C": ["dryrun/arm-c-1", "dryrun/arm-c-2"],
    "D": "dryrun/arm-d",
    "E": {tier: f"dryrun/{tier}" for tier in PIPELINE_TIERS},
}

# The kill point for the resume exhibit: the main dry run
# stops after this many units, the next unit is left in
# flight, and the run is resumed to the end.
DRY_RUN_KILL_AFTER = 40

# The fixture catalogue's rates, per token: the prompt
# side and the completion side. The dry run's scripted
# token counts are priced at exactly these figures (the
# budget-stop exhibit bills a call its arm's whole
# per-unit ceiling through them), so they are named
# constants rather than literals in two places.
DRY_RUN_PROMPT_RATE = 0.0000001
DRY_RUN_COMPLETION_RATE = 0.0000002
# What the script's default call bills at those rates:
# the _answer_call fixture's own token counts.
DRY_RUN_DEFAULT_CALL_COST = (
    900 * DRY_RUN_PROMPT_RATE
    + 1200 * DRY_RUN_COMPLETION_RATE)


def _all_servings(servings: dict[str, Any]) -> list[str]:
    """Every serving the lineup names, deduplicated."""
    named: list[str] = []
    for serving in ([servings["A"], servings["B"], servings["D"]]
                    + list(servings["C"])
                    + list(servings["E"].values())):
        if serving not in named:
            named.append(serving)
    return named


def _dry_run_catalogue(servings: dict[str, Any]) -> list[dict[str, Any]]:
    """The fixture catalogue: every serving the dry run's
    lineup names, with dry-run rates and the parameters the
    preflight checks. The rates are the fixture's own; the
    guard the dry run's calls pass through is the real one."""
    return [
        {
            "id": serving,
            "pricing": {"prompt": f"{DRY_RUN_PROMPT_RATE}",
                        "completion": (
                            f"{DRY_RUN_COMPLETION_RATE}")},
            "context_length": 200000,
            "max_completion_tokens": 32768,
            "supported_parameters": [
                "tools", "tool_choice",
                "response_format", "max_tokens",
                "temperature"],
        }
        for serving in _all_servings(servings)
    ]


def _install_dry_run_rates(catalogue: list[dict[str, Any]]) -> int:
    """The fixture's rates into the client's own pricing
    table, so the guard the dry run's calls pass through is
    the real one. The table is module state the real
    check_models() writes from the free GET; the dry run
    writes the fixture's rates into it instead of fetching."""
    from autornd.routing import openrouter as _openrouter
    installed = 0
    for entry in catalogue:
        pricing = entry.get("pricing") or {}
        try:
            _openrouter._model_pricing[entry["id"]] = (
                float(pricing["prompt"]),
                float(pricing["completion"]))
            installed += 1
        except (KeyError, TypeError, ValueError):
            continue
        # The per-request charge rides with the rates, so the
        # guard the dry run's calls pass through charges it too.
        per_request = _per_request_charge(entry)
        if per_request:
            _openrouter._model_per_request[entry["id"]] = per_request
    return installed


@contextlib.contextmanager
def _env_overrides(overrides: dict[str, str]):
    """Set environment variables for the duration, restoring
    what was there (including absence). The dry run ratifies
    its mock lineup through the same environment the owner's
    run uses."""
    saved = {name: os.environ.get(name) for name in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@contextlib.contextmanager
def _harness_pin_overrides(pins: dict[str, str] | None):
    """Pin the harness settings' model tiers for the duration.

    The dry run names arm E's lineup the way the owner's run
    does — through the standing pins — so the dry run's
    fingerprint is over a real resolved map. In a process
    whose environment carries no pins (the test suite's),
    the dry run supplies its own; the mutation is the same
    one _isolated_store() makes to settings.chromadb_path,
    and it is restored.
    """
    if not pins:
        yield
        return
    saved = {tier: getattr(harness_settings, f"model_{tier}")
             for tier in pins}
    for tier, pin in pins.items():
        setattr(harness_settings, f"model_{tier}", pin)
    try:
        yield
    finally:
        for tier, pin in saved.items():
            setattr(harness_settings, f"model_{tier}", pin)


def _answer_call(content: str,
                 finish_reason: str = "stop",
                 sleep: float = 0.0) -> dict[str, Any]:
    return {"content": content, "finish_reason": finish_reason,
            "prompt_tokens": 900, "completion_tokens": 1200,
            "sleep": sleep}


def _tool_call(name: str, arguments: dict[str, Any]
               ) -> dict[str, Any]:
    return {"content": "", "finish_reason": "tool_calls",
            "tool_calls": [{
                "id": "dryrun", "type": "function",
                "function": {"name": name,
                             "arguments": json.dumps(arguments)}}]}


def _provider_failure_call(detail: str) -> dict[str, Any]:
    return {"provider_failure": detail}


def _asks_anchored() -> dict[str, Any]:
    """The D51 (1) asks record a completed run carries:
    the anchored quotes, and the proposals the free
    anchoring check could not find in the request,
    counted beside them. The mock's asks are the
    request's own words, as the real extractor's are."""
    return {
        "anchored": ["the answer the question asks for"],
        "quotes": ["the question's own wording"],
        "demoted": ["a proposal the anchoring check "
                    "could not find in the request"],
    }


def _shipped(answer: str,
             profile: str = "standing") -> dict[str, Any]:
    """A completed pipeline run whose terminal conclusion is
    the answer — delivered (D50 (3)). The record carries the
    D51 shape the manifest's criterion (d) requires every
    unit to show: the asks with the quotes that did not
    anchor beside them, the notes the run counted, and
    every iteration's answer. ``profile`` selects the
    workflow's call profile — the standing pipeline's, or
    verify-first's (one answer, one check: four calls)."""
    if profile == "verify-first":
        figures = {"calls": 4, "seconds": 45.0, "cost": 0.04,
                   "cost_by_tier": {"engineering": 0.02,
                                    "judge": 0.02},
                   "calls_by_tier": {"triage": 2,
                                     "engineering": 1,
                                     "judge": 1}}
    else:
        figures = {"calls": 14, "seconds": 95.0, "cost": 0.11,
                   "cost_by_tier": {"engineering": 0.08,
                                    "judge": 0.03},
                   "calls_by_tier": {"triage": 2,
                                     "engineering": 8,
                                     "judge": 4}}
    return {
        "status": "completed",
        "verdicts": {"implement": {"summary": answer},
                     "asks_anchored": _asks_anchored()},
        "iterations": [{"implement_summary": answer}],
        "normalised_by_kind": {"consistency_note": 1},
        "providers_by_tier": {"engineering": ["dryrun"],
                                "judge": ["dryrun"]},
        "retries": {},
        **figures,
    }


def _revised(first: str, final: str) -> dict[str, Any]:
    """A verify-first run whose check forced one revision
    (D51 (8)'s repair path): two iterations, each with its
    answer — prediction 9's population, the first answer
    beside the final one. Two iterations are two engineering
    and two judge calls after triage and asks: four, the
    registered bound (ARM_F_CALL_LIMIT's four)."""
    return {
        "status": "completed",
        "verdicts": {"implement": {"summary": final},
                     "asks_anchored": _asks_anchored()},
        "iterations": [{"implement_summary": first},
                       {"implement_summary": final}],
        "normalised_by_kind": {"consistency_note": 1},
        "calls": 6, "seconds": 60.0, "cost": 0.06,
        "cost_by_tier": {"engineering": 0.04, "judge": 0.02},
        "calls_by_tier": {"triage": 2, "engineering": 2,
                          "judge": 2},
        "providers_by_tier": {"engineering": ["dryrun"],
                                "judge": ["dryrun"]},
        "retries": {},
    }


def _unendorsed_candidate(
        answer: str, dissents: list[dict[str, Any]],
        rulings: list[dict[str, Any]] | None = None,
        profile: str = "standing") -> dict[str, Any]:
    """A run that ended escalated after an implementation
    existed — D51 (7)'s unendorsed candidate, kept with its
    open dissents and their anchors, and D51 (6)'s escalation
    ruling on each dissent before it directed. The dissents
    are the typed anchors the judges that raised them carry:
    an ask, a quote of the request, or a hazard."""
    if profile == "verify-first":
        figures = {"calls": 6, "seconds": 70.0, "cost": 0.06,
                   "cost_by_tier": {"engineering": 0.04,
                                    "judge": 0.02},
                   "calls_by_tier": {"triage": 2,
                                     "engineering": 2,
                                     "judge": 2}}
    else:
        figures = {"calls": 38, "seconds": 590.0, "cost": 0.42,
                   "cost_by_tier": {"engineering": 0.30,
                                    "judge": 0.12},
                   "calls_by_tier": {"triage": 2,
                                     "engineering": 22,
                                     "judge": 14}}
    return {
        "status": "escalated",
        "verdicts": {
            "implement": {"summary": answer},
            "asks_anchored": _asks_anchored(),
            "escalation": {
                "root_cause_analysis": (
                    "the answer states a value the request's "
                    "own words do not support"),
                "architectural_correction": None,
                "resolution_directive": (
                    "address the upheld dissent only"),
                "requires_human": False,
                "rulings": (rulings if rulings is not None
                            else [
                                {"dissent": 1, "upheld": True,
                                 "reason": (
                                     "the dissent names the "
                                     "ask and quotes the "
                                     "request")}]),
            },
        },
        "iterations": [{"implement_summary": answer}],
        "candidate": {"answer": answer, "endorsed": False,
                      "open_dissents": dissents},
        "normalised_by_kind": {"unanchored_dissent": 1},
        "providers_by_tier": {"engineering": ["dryrun"],
                                "judge": ["dryrun"]},
        "retries": {},
        **figures,
    }


def _approved_not_shipped(answer: str) -> dict[str, Any]:
    """A judge-approved draft with no completed terminal —
    scored and reported beside the delivered count as
    'approved, not shipped', never counted as delivered
    (D50 (3), the D38 watchdog's case). The record carries
    the D51 asks and the notes the run counted."""
    return {
        "status": "escalated",
        "watchdog": {"approved": {"index": 1}},
        "verdicts": {"implement": {"summary": answer},
                     "asks_anchored": _asks_anchored()},
        "iterations": [{"implement_summary": None},
                        {"implement_summary": answer}],
        "normalised_by_kind": {"consistency_note": 1},
        "calls": 38, "seconds": 590.0, "cost": 0.42,
        "cost_by_tier": {"engineering": 0.30, "judge": 0.12},
        "calls_by_tier": {"triage": 2, "engineering": 22,
                          "judge": 14},
        "providers_by_tier": {"engineering": ["dryrun"],
                                "judge": ["dryrun"]},
        "retries": {},
    }


def _no_answer() -> dict[str, Any]:
    """A pipeline run that ended without an answer — an
    incomplete unit, counted in the denominator. The asks
    still ran (the run judged nothing against them, but it
    extracted them), so the record carries them."""
    return {"status": "blocked",
            "verdicts": {"asks_anchored": _asks_anchored()},
            "normalised_by_kind": {},
            "calls": 9, "seconds": 61.0, "cost": 0.05,
            "cost_by_tier": {"triage": 0.05},
            "calls_by_tier": {"triage": 9},
            "providers_by_tier": {"triage": ["dryrun"]},
            "retries": {}}


class DryRunScript:
    """The dry run's scripted model behaviour.

    One entry per (question_id, repetition, arm) — the
    runner's unit key — holds what each call returns, in
    call order; every unit the script does not name runs
    the default — a correct answer through the arm's
    registered treatment. The correct answers are the
    recorded real answers where the record holds them
    (the twelve vectors the tier-2 regression probe reads
    from the committed traces), and the frozen key's own
    model answer elsewhere; the wrong answers are the
    key's common wrong answers, so the FAIL cases are
    answers a reader would find wrong.
    """

    def __init__(self) -> None:
        self._calls: dict[tuple[str, int, str],
                           list[dict[str, Any]]] = {}
        self._arm_e: dict[str, dict[str, Any]] = {}
        self._arm_f: dict[str, dict[str, Any]] = {}
        self._deadlines: dict[tuple[str, int, str], float] = {}
        self._tool_failures: set[tuple[str, int, str]] = set()

    def calls_for(self, unit_key: tuple[str, int, str]
                  ) -> list[dict[str, Any]]:
        return list(self._calls.get(unit_key, []))

    def arm_e_outcome(self, scenario_id: str) -> dict[str, Any]:
        return dict(self._arm_e.get(scenario_id, _shipped("")))

    def arm_f_outcome(self, scenario_id: str) -> dict[str, Any]:
        return dict(self._arm_f.get(
            scenario_id, _shipped("", profile="verify-first")))

    def deadline_for(self, unit_key: tuple[str, int, str]
                     ) -> float | None:
        return self._deadlines.get(unit_key)

    def tool_fails(self, unit_key: tuple[str, int, str]) -> bool:
        return unit_key in self._tool_failures


def build_dry_run_script() -> DryRunScript:
    """The dry run's script: the defaults for every unit,
    then the failure-class exhibits and the FAIL cases the
    command orders — each failure class included at least
    once."""
    script = DryRunScript()
    questions = {q["id"]: q for q in load_questions()}
    keys = {k["id"]: k for k in scorer.KEYS}
    recorded: dict[str, str] = {}
    for _run, question_id, answer in regression_12.load_vectors():
        recorded.setdefault(question_id, answer)

    def correct(question_id: str) -> str:
        return (recorded.get(question_id)
                or keys[question_id]["model_answer"])

    def wrong(question_id: str) -> str:
        return keys[question_id]["common_wrong_answers"][0][
            "answer"]

    def citation_of(question_id: str) -> str | None:
        return _citation_in(questions[question_id]["question"])

    # The default for every unit: a correct answer through
    # the arm's registered treatment.
    for question_id in questions:
        for repetition in (1, 2, 3):
            for arm in ARMS:
                key = (question_id, repetition, arm)
                if arm in ("A", "D"):
                    script._calls[key] = [
                        _answer_call(correct(question_id))]
                elif arm == "B":
                    citation = citation_of(question_id)
                    first = (_tool_call(
                        "fetch_primary_source",
                        {"citation": citation}) if citation
                        else _tool_call(
                            "recompute",
                            {"expression":
                             "2.00 * 4.00 / (2.00 + 4.00)"}))
                    script._calls[key] = [
                        first, _answer_call(correct(question_id))]
                elif arm == "C":
                    # Draft, a concurring typed check, the
                    # draft delivered.
                    script._calls[key] = [
                        _answer_call(correct(question_id)),
                        _answer_call('{"concur": true, '
                                     '"objections": []}')]
                else:
                    script._arm_e[
                        f"tier3_e_{question_id}_r{repetition}"
                    ] = _shipped(correct(question_id))

    # ── The failure-class exhibits, one each ──
    # Keyed to the stage-1 selection's questions (the
    # seven the plan runs: Q6, Q10, Q14, Q15, Q16, Q17,
    # Q23) — an exhibit keyed to a question the plan does
    # not run never fires, and the dry run would prove a
    # failure class it does not exercise. Each (question,
    # repetition, arm) triple below is distinct.
    # refusal: a serving that chose to answer nothing.
    script._calls[("Q6", 1, "A")] = [_answer_call("")]
    # deadline: a call that outlasts the unit's shortened
    # deadline, cancelled by the runner's wait_for.
    script._calls[("Q10", 1, "D")] = [
        _answer_call(correct("Q10"), sleep=0.25)]
    script._deadlines[("Q10", 1, "D")] = 0.05
    # incomplete: a serving that consumed its budget and
    # emitted nothing — the provider failure the client
    # raises after its bounded retries.
    script._calls[("Q14", 1, "D")] = [
        _provider_failure_call(
            "scripted: the serving consumed its budget and "
            "emitted nothing")]
    # tool failure: the tool's execution fails (the way a
    # real OSError would); the model continues without the
    # tool and the delivered answer is scored on what it
    # delivered.
    script._tool_failures.add(("Q15", 1, "B"))
    # an invalid arm C verdict: the check answers in prose,
    # twice — no valid verdict after the bounded retries,
    # recorded as unavailable, never as concurrence, and
    # the draft delivered.
    script._calls[("Q16", 1, "C")] = [
        _answer_call(correct("Q16")),
        _answer_call("The draft looks sound to me; I have no "
                     "objections to raise."),
        _answer_call("I concur with the draft as it stands.")]
    # arm B's two-round unit: tools on calls 1 and 2, the
    # answer on call 3 — which keeps them declared with
    # tool_choice "none", so the model must answer.
    script._calls[("Q17", 1, "B")] = [
        _tool_call("fetch_primary_source",
                   {"citation": citation_of("Q17")}),
        _tool_call("recompute", {"expression": "90 / 2"}),
        _answer_call(correct("Q17"))]
    # serving_error: the final call's empty reply with
    # finish "error" — the serving failed the call (the
    # stage-1 run's 13 arm-B final-call errors), so the
    # unit is counted in its own class, never as a
    # refusal.
    script._calls[("Q23", 1, "B")] = [
        _tool_call("recompute", {"expression": "1.00 + 1.00"}),
        _tool_call("recompute", {"expression": "2.00 * 2.00"}),
        _answer_call("", finish_reason="error")]

    # ── The FAIL cases, so the sheet has FAILs to read ──
    script._calls[("Q23", 1, "A")] = [_answer_call(wrong("Q23"))]
    script._calls[("Q10", 1, "B")] = [
        _tool_call("recompute",
                   {"expression": "12.0 / (4.00 + 2.00)"}),
        _answer_call(wrong("Q10"))]
    script._calls[("Q14", 1, "C")] = [
        _answer_call(wrong("Q14")),
        _answer_call('{"concur": false, "objections": '
                     '["The draft does not answer the third '
                     'part the question asks."]}'),
        _answer_call(wrong("Q14"))]
    script._calls[("Q15", 1, "D")] = [_answer_call(wrong("Q15"))]

    # ── Arm E's delivery kinds ──
    # a shipped wrong answer (delivered, FAIL);
    script._arm_e["tier3_e_Q17_r1"] = _shipped(wrong("Q17"))
    # a judge-approved draft that never shipped;
    script._arm_e["tier3_e_Q23_r1"] = _approved_not_shipped(
        correct("Q23"))
    # a run that ended without an answer.
    script._arm_e["tier3_e_Q6_r1"] = _no_answer()
    return script


# ── The re-measurement's dry run (command 121) ──────

def _request_quote(question_id: str,
                   questions: dict[str, dict[str, Any]]
                   ) -> str:
    """A verbatim quote of the request, as a dissent's
    anchor names it (D51 (3)): the question's own first
    clause, taken from the request's bytes, so the mock's
    anchor is a real quote the way a real judge's is."""
    text = questions[question_id]["question"]
    for end in (".", "?", ";", "\n"):
        cut = text.find(end)
        if cut > 0:
            return text[:cut]
    return text[:60]


def _ceiling_call(arm: str, answer: str) -> dict[str, Any]:
    """A call that bills its arm's whole per-unit ceiling
    (the budget-stop exhibit): the token counts the
    fixture's rates turn into the ceiling, so the client's
    own accounting books the full figure the fit rule
    budgeted for the unit. A hair under the ceiling, so
    the client's own post-call check — the booked cost
    against the unit's ceiling — holds exactly, and the
    unit is delivered at its ceiling rather than refused
    by it."""
    prompt_tokens = int(
        ARM_CEILINGS[arm] * 0.999 / DRY_RUN_PROMPT_RATE)
    return {"content": answer, "finish_reason": "stop",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": 0}


def _at_ceiling(arm: str, answer: str) -> dict[str, Any]:
    """A pipeline run that used its whole per-unit ceiling
    (the budget-stop exhibit's E' and F units): the
    workflow's own profile, priced at the arm's ceiling
    with the tiers' shares held."""
    outcome = _shipped(
        answer, profile=("verify-first" if arm == "F"
                         else "standing"))
    ceiling = ARM_CEILINGS[arm]
    scale = ceiling / outcome["cost"]
    outcome["cost"] = ceiling
    outcome["cost_by_tier"] = {
        tier: round(amount * scale, 6)
        for tier, amount in outcome["cost_by_tier"].items()}
    return outcome


def build_remeasure_script(
        ) -> tuple[DryRunScript, list[tuple[str, int, str]]]:
    """The re-measurement dry run's own script: the 246-unit
    plan's defaults, the failure-class exhibits the command
    names (refusal, serving error, deadline, provider
    failure, budget stop), the FAIL cases every arm's
    reading sheet needs, the D51 record exhibits (criterion
    (d): the anchored and demoted asks, every dissent with
    its anchor, the notes count, the escalation's rulings,
    the candidate, every iteration's answer), and the
    budget-stop tail — the deterministic tail of the seeded
    order whose units are charged their whole per-unit
    ceilings, so the $15.00 authorization stops the run
    inside the tail and the units after the stop skip
    through the fit rule.

    Returns the script and the tail, so the dry run's
    report can name the exhibit's population. Every exhibit
    is keyed to a (question, repetition, arm) unit the
    re-measurement's plan actually runs — arms A, D, F over
    the frozen set's twenty-five questions and E' over
    stage 1's seven — so each class is exercised, not
    scripted onto a unit the plan never reaches.
    """
    script = DryRunScript()
    questions = {q["id"]: q for q in load_questions()}
    keys = {k["id"]: k for k in scorer.KEYS}
    recorded: dict[str, str] = {}
    for _run, question_id, answer in regression_12.load_vectors():
        recorded.setdefault(question_id, answer)

    def correct(question_id: str) -> str:
        return (recorded.get(question_id)
                or keys[question_id]["model_answer"])

    def wrong(question_id: str) -> str:
        return keys[question_id]["common_wrong_answers"][0][
            "answer"]

    def quote(question_id: str) -> str:
        return _request_quote(question_id, questions)

    # The cost each unit books, as the budget-stop tail's
    # floor is computed from it: the defaults' own figures,
    # then each exhibit's, as it is scripted.
    booked: dict[tuple[str, int, str], float] = {}
    default_cost = {"A": DRY_RUN_DEFAULT_CALL_COST,
                    "D": DRY_RUN_DEFAULT_CALL_COST,
                    "F": 0.04, "E": 0.11}

    # The defaults: every unit of the plan answers correctly
    # through its arm's registered treatment.
    for question in questions.values():
        for repetition in (1, 2, 3):
            for arm in ("A", "D", "F"):
                key = (question["id"], repetition, arm)
                if arm in ("A", "D"):
                    script._calls[key] = [
                        _answer_call(correct(question["id"]))]
                else:
                    script._arm_f[
                        f"tier3_f_{question['id']}"
                        f"_r{repetition}"] = _shipped(
                            correct(question["id"]),
                            profile="verify-first")
                booked[key] = default_cost[arm]
    for question_id in STAGE1_QUESTION_IDS:
        for repetition in (1, 2, 3):
            key = (question_id, repetition, "E")
            script._arm_e[
                f"tier3_e_{question_id}_r{repetition}"] = (
                    _shipped(correct(question_id)))
            booked[key] = default_cost["E"]

    def exhibit(key: tuple[str, int, str],
                cost: float) -> None:
        """Record what an exhibit unit books, so the
        budget-stop tail's floor is the plan's true
        spend, not an estimate — and which units are
        exhibits, so the tail never charges a ceiling
        over an exhibit's own scripted behaviour."""
        booked[key] = cost
        exhibit_keys.add(key)

    exhibit_keys: set[tuple[str, int, str]] = set()

    # ── The failure-class exhibits, one each ──
    # refusal: a serving that chose to answer nothing
    # (its empty reply still bills the call).
    script._calls[("Q6", 1, "A")] = [_answer_call("")]
    exhibit(("Q6", 1, "A"), DRY_RUN_DEFAULT_CALL_COST)
    # serving error: the serving failed the call (an empty
    # reply with finish "error" — the stage-1 run's
    # arm-B final-call errors, on a unit this plan runs);
    # the call billed before the serving failed it.
    script._calls[("Q16", 1, "A")] = [
        _answer_call("", finish_reason="error")]
    exhibit(("Q16", 1, "A"), DRY_RUN_DEFAULT_CALL_COST)
    # deadline: a call that outlasts the unit's shortened
    # deadline, cancelled by the runner's wait_for before
    # anything booked (its reservation stays unreconciled
    # liability on the unit's client, not the sweep).
    script._calls[("Q10", 1, "D")] = [
        _answer_call(correct("Q10"), sleep=0.25)]
    script._deadlines[("Q10", 1, "D")] = 0.05
    exhibit(("Q10", 1, "D"), 0.0)
    # provider failure: a serving that consumed its budget
    # and emitted nothing, after dispatch, the same way.
    script._calls[("Q14", 1, "D")] = [
        _provider_failure_call(
            "scripted: the serving consumed its budget and "
            "emitted nothing")]
    exhibit(("Q14", 1, "D"), 0.0)

    # ── The FAIL cases, so every arm's sheet has FAILs ──
    script._calls[("Q23", 1, "A")] = [_answer_call(wrong("Q23"))]
    exhibit(("Q23", 1, "A"), DRY_RUN_DEFAULT_CALL_COST)
    script._calls[("Q15", 1, "D")] = [_answer_call(wrong("Q15"))]
    exhibit(("Q15", 1, "D"), DRY_RUN_DEFAULT_CALL_COST)
    # arm F's shipped wrong answer (delivered, FAIL).
    script._arm_f["tier3_f_Q23_r1"] = _shipped(
        wrong("Q23"), profile="verify-first")
    exhibit(("Q23", 1, "F"), 0.04)

    # ── Arm F's revisions (prediction 9's population:
    # the check forced a revision, and the first answer
    # sits beside the final one) ──
    # the check turned a wrong answer right;
    script._arm_f["tier3_f_Q15_r1"] = _revised(
        wrong("Q15"), correct("Q15"))
    # the check turned a right answer wrong;
    script._arm_f["tier3_f_Q14_r1"] = _revised(
        correct("Q14"), wrong("Q14"))
    # the revision left a wrong answer wrong.
    script._arm_f["tier3_f_Q16_r1"] = _revised(
        wrong("Q16"), wrong("Q16"))
    for question_id in ("Q15", "Q14", "Q16"):
        exhibit((question_id, 1, "F"), 0.06)

    # ── The D51 (7) candidates, with their open dissents
    # and their anchors, and D51 (6)'s rulings ──
    # arm F's run ended escalated after its revision: the
    # dissent survived, so the candidate is kept,
    # unendorsed, with the judge's anchor — an ask, a
    # quote of the request — beside it.
    script._arm_f["tier3_f_Q17_r1"] = _unendorsed_candidate(
        wrong("Q17"),
        [{"judge": "validate", "ask": 1,
          "quote": quote("Q17"), "hazard": False}],
        profile="verify-first")
    exhibit(("Q17", 1, "F"), 0.06)
    # arm E's run ended escalated with two dissents and
    # the escalation's ruling on each: one upheld, one
    # not — D51 (6)'s per-dissent record.
    script._arm_e["tier3_e_Q10_r1"] = _unendorsed_candidate(
        wrong("Q10"),
        [{"judge": "review", "ask": 1,
          "quote": quote("Q10"), "hazard": False},
         {"judge": "domain_review", "ask": 3,
          "quote": quote("Q10"), "hazard": False}],
        rulings=[
            {"dissent": 1, "upheld": True,
             "reason": ("the dissent names the ask and "
                        "quotes the request's own words")},
            {"dissent": 2, "upheld": False,
             "reason": ("the concern names no ask and "
                        "quotes no request words: a note, "
                        "not a dissent")}])
    exhibit(("Q10", 1, "E"), 0.42)

    # ── Arm E's delivery kinds ──
    # a shipped wrong answer (delivered, FAIL);
    script._arm_e["tier3_e_Q17_r1"] = _shipped(wrong("Q17"))
    exhibit(("Q17", 1, "E"), 0.11)
    # a judge-approved draft that never shipped;
    script._arm_e["tier3_e_Q23_r1"] = _approved_not_shipped(
        correct("Q23"))
    exhibit(("Q23", 1, "E"), 0.42)
    # a run that ended without an answer.
    script._arm_e["tier3_e_Q6_r1"] = _no_answer()
    exhibit(("Q6", 1, "E"), 0.05)

    # ── The budget-stop tail ──
    # The plan's true spend, unit by unit, is known before
    # anything runs (the dry run is deterministic), so the
    # tail is long enough that its ceilings sum past the
    # authorization minus that spend, with margin: the
    # crossing lands inside the tail, and the units after
    # it skip through the fit rule — the budget-stop class,
    # on the real rule, at zero spend.
    order = remeasure_order(REMEASURE_SEED)
    floor = sum(booked.get(tuple(key), 0.0) for key in order)
    target = REMEASURE_CEILING - floor + 1.00
    tail: list[tuple[str, int, str]] = []
    accumulated = 0.0
    for key in reversed(order):
        if accumulated >= target:
            break
        unit_key = tuple(key)
        if unit_key in exhibit_keys:
            # An exhibit keeps its own scripted
            # behaviour; the tail charges the defaults.
            continue
        tail.append(unit_key)
        accumulated += ARM_CEILINGS[unit_key[2]]
    for unit_key in tail:
        question_id, repetition, arm = unit_key
        if arm in ("A", "D"):
            script._calls[unit_key] = [
                _ceiling_call(arm, correct(question_id))]
        elif arm == "F":
            script._arm_f[
                f"tier3_f_{question_id}_r{repetition}"] = (
                    _at_ceiling("F", correct(question_id)))
        else:
            script._arm_e[
                f"tier3_e_{question_id}_r{repetition}"] = (
                    _at_ceiling("E", correct(question_id)))
    return script, tail


class DryRunClient(OpenRouterClient):
    """The dry run's mocked client for arms A-D.

    It returns the script's outcome for each call, in call
    order, and bills every call through the client's own
    guard and accounting (convention 7: a test double must
    bill) — so the spend ceiling, the reservation and the
    reconciliation the dry run exercises are the real ones.
    """

    def __init__(self, script: DryRunScript,
                 unit_key: tuple[str, int, str],
                 serving: str,
                 rates: dict[str, tuple[float, float]],
                 ceiling: float, call_limit: int) -> None:
        super().__init__()
        self.call_ceiling = call_limit
        self.spend_ceiling = ceiling
        self._script = script
        self._unit_key = unit_key
        self._rates = rates
        self._outcomes = script.calls_for(unit_key)
        self._call_number = 0

    async def chat(
            self, function: str, system_prompt: str,
            user_message: str,
            response_format: dict[str, Any] | None = None,
            temperature: float = 0.3,
            max_tokens: int = 16384,
            model: str | None = None,
            tools: list[dict[str, Any]] | None = None,
            tool_choice: str | None = None,
    ) -> ModelResponse:
        self._call_number += 1
        outcome = (self._outcomes[self._call_number - 1]
                   if self._call_number <= len(self._outcomes)
                   else {"content": "", "finish_reason": "stop"})
        if outcome.get("sleep"):
            # The deadline class: the unit's wait_for cancels
            # the call here, before anything is booked.
            await asyncio.sleep(outcome["sleep"])
        model = model or self.get_model(function)
        # The real guard, at the real formula, with the
        # fixture's rates installed in the real table.
        reservation = self._guard_spend(
            function, model,
            _prompt_bytes(system_prompt, user_message),
            max_tokens)
        self._in_flight += 1
        try:
            if outcome.get("provider_failure"):
                # The provider consumed its budget and
                # emitted nothing: a failed call, booked
                # the way the real client books one.
                raise ProviderFailure(
                    function, None,
                    outcome["provider_failure"])
            prompt_tokens = outcome.get("prompt_tokens", 900)
            completion_tokens = outcome.get(
                "completion_tokens", 1200)
            prompt_rate, completion_rate = self._rates.get(
                model, (0.0, 0.0))
            cost = (prompt_tokens * prompt_rate
                    + completion_tokens * completion_rate)
            # The real reconciliation: this call's own
            # reservation released, then the bill booked
            # (D47: _account releases nothing itself).
            self._release(reservation)
            self._account(function, cost,
                          outcome.get("provider"),
                          prompt_tokens=prompt_tokens,
                          completion_tokens=completion_tokens,
                          reservation=reservation)
            return ModelResponse(
                content=outcome.get("content") or "",
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost=cost,
                finish_reason=outcome.get("finish_reason",
                                            "stop"),
                provider=outcome.get("provider"),
                tool_calls=outcome.get("tool_calls") or [])
        except BaseException as exc:
            # A call that failed after dispatch keeps its
            # worst case, as unreconciled liability with
            # the kind of failure recorded — the real
            # client's exact rule (D45 (5)).
            self._fail_call(function, model,
                            _failure_kind(exc), reservation)
            raise


class DryRunScenarioRunner:
    """The dry run's stand-in at the pipeline boundary for
    arms E and F.

    Everything above this boundary is the real machinery —
    the unit's place in the order, the deadline, the
    delivery reader, the scoring, the record, the resume.
    The pipeline's own execution is replaced by scripted
    ScenarioRun rows, the same way the dry run's client
    replaces the model servings for arms A-D: the dry run
    proves the experiment's machinery, and the pipeline
    itself is proven by the harness's own suite. The
    budget's fit rule is the real one, and the scripted
    cost is booked to it exactly as run_scenario books a
    real run's.
    """

    def __init__(self, script: DryRunScript) -> None:
        self._script = script

    async def __call__(self, scenario: Scenario, spec,
                        client_factory, settings_lookup_dict,
                        timeout: float = DEADLINE_SECONDS,
                        max_spend: float | None = None,
                        budget: SweepBudget | None = None,
                        ) -> Any:
        if budget is not None and not budget.can_start(max_spend):
            return ScenarioRun(
                scenario=scenario, results=[], calls=0,
                seconds=0.0, error=budget.skip(max_spend),
                was_skipped=True)
        # The scenario's id names its arm: tier3_e_* runs
        # the standing workflow, tier3_f_* the verify-first
        # one (arm F's scenario, as _arm_f builds it).
        if scenario.id.startswith("tier3_f_"):
            outcome = self._script.arm_f_outcome(scenario.id)
        else:
            outcome = self._script.arm_e_outcome(scenario.id)
        if budget is not None:
            budget.record(outcome.get("cost", 0.0))
        return ScenarioRun(
            scenario=scenario, results=[],
            calls=outcome.get("calls", 0),
            seconds=outcome.get("seconds", 0.0),
            cost=outcome.get("cost", 0.0),
            error=outcome.get("error"),
            cost_by_tier=outcome.get("cost_by_tier", {}),
            calls_by_tier=outcome.get("calls_by_tier", {}),
            providers_by_tier=outcome.get(
                "providers_by_tier", {}),
            verdicts=outcome.get("verdicts", {}),
            status=outcome.get("status", ""),
            iterations=outcome.get("iterations", []),
            watchdog=outcome.get("watchdog"),
            tokens_by_tier=outcome.get("tokens_by_tier", {}),
            retries=outcome.get("retries", {}),
            candidate=outcome.get("candidate"),
            normalised_by_kind=outcome.get(
                "normalised_by_kind", {}))


class _DryRunContext:
    """The dry run's shared state: which unit is running, so
    the client factory and the tool dispatcher can find the
    script's entry for it. Units run sequentially, so one
    holder serves every seam."""

    def __init__(self) -> None:
        self.unit_key: tuple[str, int, str] | None = None


def _dry_run_client_factory(script: DryRunScript,
                            rates: dict[str, tuple[float, float]],
                            context: _DryRunContext):
    """The dry run's arms A-D client factory: a scripted
    client per unit, which bills through the real guard and
    accounting."""
    def factory(unit_key, arm, serving, ceiling, call_limit):
        context.unit_key = unit_key
        return DryRunClient(script, unit_key, serving, rates,
                            ceiling, call_limit)
    return factory


def _dry_run_tool_dispatcher(script: DryRunScript,
                             context: _DryRunContext):
    """The dry run's tool dispatcher: the real tools, except
    where the script marks a unit's tool execution as failed
    (the tool-failure exhibit — the way a real OSError
    would)."""
    def dispatcher(name: str, arguments: dict[str, Any]):
        if (context.unit_key is not None
                and script.tool_fails(context.unit_key)):
            raise OSError(
                "scripted tool failure (the dry run's "
                "tool-failure exhibit)")
        return _dispatch_tool(name, arguments)
    return dispatcher


def _synthetic_readings(sheet: dict[str, Any]) -> tuple[
        dict[int, str], dict[int, str]]:
    """The dry run's stand-in for two readers: reader 1 reads
    what the scorer read, reader 2 the same except one
    seeded disagreement, so the merge demonstrates both its
    agreement and its disagreement paths. A real run's
    readings come from the two hand readings D50 (1)
    orders; nothing here substitutes for them."""
    reader_1: dict[int, str] = {}
    reader_2: dict[int, str] = {}
    for entry in sheet["entries"]:
        verdict = entry["scorer_verdict"] or "FAIL"
        reader_1[entry["entry"]] = verdict
        reader_2[entry["entry"]] = verdict
    if sheet["entries"]:
        # One seeded disagreement: the second entry, read
        # the other way by reader 2.
        second = sheet["entries"][1]["entry"]
        reader_2[second] = ("PASS" if reader_2[second] == "FAIL"
                            else "FAIL")
    return reader_1, reader_2


async def dry_run() -> dict[str, Any]:
    """The mocked dry runs (the command's pre-registration
    check): the full 375-unit plan and the 50-unit pilot
    through the real runner with mocked clients — no
    network, no spend.

    Every failure class the command names is included at
    least once: refusal, deadline, tool failure, an invalid
    arm C verdict, an incomplete unit, and a resume after a
    kill (the main run is killed after DRY_RUN_KILL_AFTER
    units, the in-flight unit charged its ceiling as
    unreconciled liability, and the run resumed to the end).
    The order's sha256 is the guard's reconstruction
    (the guard test rebuilds the order from the manifest's
    seed and comprehension, and the two digests are
    compared).
    """
    script = build_dry_run_script()
    servings = DRY_RUN_SERVINGS
    fingerprint = servings_fingerprint(servings)
    overrides = {
        "TIER3_ARM_A": servings["A"],
        "TIER3_ARM_B": servings["B"],
        "TIER3_ARM_C_1": servings["C"][0],
        "TIER3_ARM_C_2": servings["C"][1],
        "TIER3_ARM_D": servings["D"],
        "TIER3_SERVINGS_RATIFIED": fingerprint,
        "TIER3_SPEND_AUTHORIZED": f"{MAIN_CEILING:.2f}",
        "TIER3_PILOT_AUTHORIZED": f"{PILOT_CEILING:.2f}",
    }
    catalogue = _dry_run_catalogue(servings)
    rates = {entry["id"]: (float(entry["pricing"]["prompt"]),
                            float(entry["pricing"]["completion"]))
             for entry in catalogue}
    # The deadline exhibit's shortened deadline, keyed by
    # the runner's unit key, as run_unit reads it.
    deadline_overrides = {key: seconds
                          for key, seconds
                          in script._deadlines.items()}
    context = _DryRunContext()
    main_path = RESULTS_DIR / "dryrun-tier3-main.jsonl"
    pilot_path = RESULTS_DIR / "dryrun-tier3-pilot.jsonl"
    with _env_overrides(overrides), \
            _harness_pin_overrides(servings["E"]):
        installed = _install_dry_run_rates(catalogue)
        client_factory = _dry_run_client_factory(
            script, rates, context)
        tool_dispatcher = _dry_run_tool_dispatcher(script, context)
        scenario_runner = DryRunScenarioRunner(script)
        # The main run, killed after DRY_RUN_KILL_AFTER units
        # (the resume exhibit)…
        killed = await run_experiment(
            "main", results_path=main_path,
            stop_after=DRY_RUN_KILL_AFTER,
            client_factory=client_factory,
            tool_dispatcher=tool_dispatcher,
            scenario_runner=scenario_runner,
            catalogue=catalogue,
            deadline_overrides=deadline_overrides)
        # …then resumed to the end, on the same results file.
        resumed = await run_experiment(
            "main", results_path=main_path,
            client_factory=client_factory,
            tool_dispatcher=tool_dispatcher,
            scenario_runner=scenario_runner,
            catalogue=catalogue,
            deadline_overrides=deadline_overrides)
        # The 50-unit pilot.
        pilot = await run_experiment(
            "pilot", results_path=pilot_path,
            client_factory=client_factory,
            tool_dispatcher=tool_dispatcher,
            scenario_runner=scenario_runner,
            catalogue=catalogue)
        # The re-measurement: the 246-unit plan under the
        # re-measurement's own script — its failure-class
        # exhibits, its D51 record exhibits and its
        # budget-stop tail — through the same real
        # machinery, at the re-measurement's own $15.00
        # authorization (the gate's line is the main
        # run's, which the re-measurement's ceiling sits
        # under). No network, no spend.
        remeasure_script, remeasure_tail = (
            build_remeasure_script())
        remeasure_context = _DryRunContext()
        remeasure_overrides = {
            key: seconds for key, seconds
            in remeasure_script._deadlines.items()}
        remeasure_path = (RESULTS_DIR
                          / "dryrun-tier3-remeasure.jsonl")
        remeasurement = await run_experiment(
            "remeasure", results_path=remeasure_path,
            client_factory=_dry_run_client_factory(
                remeasure_script, rates, remeasure_context),
            tool_dispatcher=_dry_run_tool_dispatcher(
                remeasure_script, remeasure_context),
            scenario_runner=DryRunScenarioRunner(
                remeasure_script),
            catalogue=catalogue,
            deadline_overrides=remeasure_overrides)

    # The reading sheets and the five measures, both ways.
    questions = {q["id"]: q for q in load_questions()}
    main_sheet = export_reading_sheet(
        resumed["records"], questions, scorer.KEYS,
        RESULTS_DIR / "dryrun-tier3-reading-sheet.json",
        SEED)
    pilot_sheet = export_reading_sheet(
        pilot["records"], questions, scorer.KEYS,
        RESULTS_DIR / "dryrun-tier3-pilot-reading-sheet.json",
        PILOT_SEED)
    # The re-measurement's reading sheet and its report:
    # the eight tables the manifest's tier3-8 registration
    # lists, computed from the units' own records.
    remeasure_sheet = export_reading_sheet(
        remeasurement["records"], questions, scorer.KEYS,
        RESULTS_DIR / "dryrun-tier3-remeasure-reading-sheet.json",
        REMEASURE_SEED)
    remeasurement_report = remeasure_report(
        remeasurement["records"], questions, scorer.KEYS)
    remeasure_report_path = (RESULTS_DIR
                             / "dryrun-tier3-remeasure-report.json")
    remeasure_report_path.write_text(
        json.dumps(remeasurement_report, indent=2,
                   default=str),
        encoding="utf-8")
    reader_1, reader_2 = _synthetic_readings(main_sheet)
    merged = merge_readings(main_sheet, reader_1, reader_2)
    read_verdicts = {
        (record["question_id"], record["repetition"],
         record["arm"]): None
        for record in resumed["records"]}
    # The readers read sheet entries, which carry no arm
    # label; the merge's verdicts are keyed by entry. Join
    # them to units through the sheet's question ids.
    entry_by_question: dict[str, int] = {}
    for entry in main_sheet["entries"]:
        entry_by_question.setdefault(entry["question_id"],
                                     entry["entry"])
    for record in resumed["records"]:
        entry = entry_by_question.get(record["question_id"])
        if entry is not None and entry in merged["merged"]:
            read_verdicts[(record["question_id"],
                           record["repetition"],
                           record["arm"])] = merged["merged"][entry]
    measures_read = compute_measures(
        resumed["records"], readings={
            key: verdict for key, verdict in read_verdicts.items()
            if verdict is not None})
    return {
        "installed_rates": installed,
        "servings": servings,
        "servings_fingerprint": fingerprint,
        "order_sha256": resumed["order_sha256"],
        "killed": {
            "summary": killed["summary"],
            "units": len(killed["records"]),
            "killed_at": killed["killed_at"],
            "in_flight": killed["left_in_flight"],
        },
        "main": {
            "summary": resumed["summary"],
            "measures": resumed["measures"],
            "measures_read": measures_read,
            "census": resumed["census"],
            "units": len(resumed["records"]),
            "resumed": resumed["resumed"],
            "in_flight": resumed["in_flight"],
            "charged_liability": resumed["charged_liability"],
            "path": resumed["path"],
            "records": resumed["records"],
        },
        "pilot": {
            "summary": pilot["summary"],
            "measures": pilot["measures"],
            "census": pilot["census"],
            "units": len(pilot["records"]),
            "path": pilot["path"],
            "records": pilot["records"],
        },
        "remeasurement": {
            "summary": remeasurement["summary"],
            "measures": remeasurement["measures"],
            "census": remeasurement["census"],
            "units": len(remeasurement["records"]),
            "planned": remeasurement["order_units"],
            "budget": remeasurement["budget"],
            "path": remeasurement["path"],
            "records": remeasurement["records"],
            "reading_sheet": {
                "path": str(RESULTS_DIR
                            / "dryrun-tier3-remeasure-"
                            "reading-sheet.json"),
                "per_arm": remeasure_sheet["per_arm"],
                "entries": len(remeasure_sheet["entries"]),
            },
            "report": {
                "path": str(remeasure_report_path),
                "tables": list(remeasurement_report),
            },
            "budget_stop_tail": [
                list(unit_key) for unit_key in remeasure_tail],
        },
        "reading_sheet": {
            "path": str(RESULTS_DIR
                        / "dryrun-tier3-reading-sheet.json"),
            "per_arm": main_sheet["per_arm"],
            "entries": len(main_sheet["entries"]),
            "merged": len(merged["merged"]),
            "disagreements": merged["disagreements"],
            "unread": merged["unread"],
        },
    }


# ── The command line ───────────────────────────────────

# The exit code of a run the gates or the preflight refused,
# mirroring the eval CLI's own refusal code, so a script
# driving the experiment can tell "nothing ran" from "it ran
# and failed".
REFUSED_EXIT = 3


def _print_preflight_findings(report: PreflightReport) -> None:
    for refusal in report.refusals:
        print(f"[REFUSE] {refusal}")
    for note in report.reports:
        print(f"[report] {note}")


def _print_worst_case(rows: list[dict[str, Any]],
                      arm: str = "E") -> None:
    """The worst-case table, one line per tier — arm
    E's standing tiers, or arm F's verify-first call
    counts on them (with the whole sequence's worst
    case as its last line)."""
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
            # Arm F's bound: the whole call sequence's
            # worst case, the counts the workflow's own
            # declared bound composes, against the
            # per-unit ceiling.
            print(
                f"arm {arm}/sequence: {row['calls']} calls "
                f"({row['serving']}) — worst case "
                f"${row['worst_case']:.4f} against the "
                f"${row['unit_ceiling']:.2f} per-unit "
                f"ceiling ({refusal})")
            continue
        calls = row.get("calls")
        on_tier = (f" — the workflow's {calls} calls on "
                   f"this tier: ${row['tier_worst_case']:.4f}"
                   if calls is not None else "")
        print(
            f"arm {arm}/{row['tier']}: {row['serving']}{priced} — "
            f"standing cap {row['cap']}, worst case per call "
            f"${row['worst_case']:.4f}{on_tier} against the "
            f"${row['unit_ceiling']:.2f} per-unit ceiling "
            f"({refusal}; {charge}the prompt side is the largest "
            f"question, a floor — the guard computes the real "
            f"bytes at call time)")


async def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tier3-runner",
        description="The tier-3 experiment runner "
                    "(ARCH-20261003-119)")
    sub = parser.add_subparsers(dest="command", required=True)
    preflight_p = sub.add_parser(
        "preflight",
        help="the gates and the free preflight, before any "
             "paid call")
    preflight_p.add_argument("--pilot", action="store_true",
                             help="check the pilot's gates "
                                  "(TIER3_PILOT_AUTHORIZED)")
    preflight_p.add_argument(
        "--remeasure", action="store_true",
        help="check the re-measurement's gates "
             "(TIER3_SPEND_AUTHORIZED against the "
             "re-measurement's $15.00 ceiling)")
    sub.add_parser("worst-case",
                   help="the arm-E worst-case table (free)")
    for name, help_text in (
            ("run", "the 375-unit main run (paid)"),
            ("pilot", "the 50-unit calibration pilot (paid)"),
            ("remeasure",
             "the 246-unit D51 re-measurement (paid)")):
        command_p = sub.add_parser(name, help=help_text)
        command_p.add_argument("--results-file", default=None,
                               metavar="PATH")
    sub.add_parser("dry-run",
                   help="the mocked dry runs, main, pilot "
                        "and re-measurement (free)")
    sheet_p = sub.add_parser(
        "reading-sheet",
        help="export the reading sheet from a results file")
    sheet_p.add_argument("results_file", metavar="RESULTS_FILE")
    report_p = sub.add_parser(
        "remeasure-report",
        help="the re-measurement's eight report tables, "
             "from a results file")
    report_p.add_argument("results_file", metavar="RESULTS_FILE")
    args = parser.parse_args(argv)

    if args.command == "preflight":
        tier3 = Tier3Settings()
        servings = resolve_servings(tier3)
        fingerprint = servings_fingerprint(servings)
        print("servings map:")
        print(json.dumps(servings, indent=2, sort_keys=True))
        print(f"servings fingerprint: {fingerprint}\n")
        missing = gate_report(
            tier3, servings, fingerprint, pilot=args.pilot,
            mode=("remeasure" if args.remeasure
                  else "main"))
        if missing:
            print("the ratification gates are not cleared — "
                  "refusing before any network call:")
            for gate in missing:
                print(f"  [GATE] {gate}")
            return REFUSED_EXIT
        print("the ratification gates hold\n")
        catalogue = await fetch_catalogue(
            confirm={serving for serving in _all_servings(servings)})
        report = run_preflight(servings, catalogue)
        _print_preflight_findings(report)
        _print_worst_case(arm_e_worst_case(servings, catalogue))
        if args.remeasure:
            # The re-measurement's arm F: the
            # verify-first workflow's calls on the
            # standing tiers, against its own $0.20
            # per-unit ceiling — each arm's worst
            # case within its ceiling, as the
            # manifest's tier3-8 registration
            # registers the preflight.
            print()
            print("arm F, the verify-first workflow's "
                  "calls on arm E's standing tiers:")
            _print_worst_case(
                arm_f_worst_case(servings, catalogue),
                arm="F")
        if report.refusals:
            print(f"\nrefused: the preflight refused to start "
                  f"(exit {REFUSED_EXIT})")
            return REFUSED_EXIT
        print("\nthe preflight holds; the experiment may start "
              "once the owner authorizes the spend")
        return 0

    if args.command == "worst-case":
        tier3 = Tier3Settings()
        servings = resolve_servings(tier3)
        fingerprint = servings_fingerprint(servings)
        print(f"servings fingerprint: {fingerprint}")
        catalogue = await fetch_catalogue(
            confirm={serving for serving in _all_servings(servings)})
        _print_worst_case(arm_e_worst_case(servings, catalogue))
        return 0

    if args.command in ("run", "pilot", "remeasure"):
        mode = args.command
        try:
            result = await run_experiment(
                mode, results_path=args.results_file)
        except ExperimentRefused as exc:
            print(exc)
            if exc.servings is not None:
                print("\nservings map:")
                print(json.dumps(exc.servings, indent=2,
                                 sort_keys=True))
                print(f"servings fingerprint: {exc.fingerprint}")
            print("\nthe experiment refused to start before "
                  "any paid call")
            return REFUSED_EXIT
        print(result["summary"])
        print()
        print(json.dumps(result["measures"], indent=2,
                         default=str))
        if mode == "remeasure":
            print()
            print("the re-measurement's report:")
            print(json.dumps(remeasure_report(
                result["records"], result["questions"],
                result["keys"]), indent=2, default=str))
        return 0

    if args.command == "dry-run":
        result = await dry_run()
        print("the dry run's mock lineup (servings by "
              "fingerprint):")
        print(f"  fingerprint: {result['servings_fingerprint']}")
        print(f"  order sha256: {result['order_sha256']}")
        print(f"  catalogue fixture: "
              f"{result['installed_rates']} servings priced\n")
        print("the main run, killed for the resume exhibit:")
        print(result["killed"]["summary"])
        print(f"  killed after {result['killed']['units']} "
              f"units; the next unit "
              f"({result['killed']['in_flight']}) was left "
              f"in flight\n")
        print("the main run, resumed to the end:")
        print(result["main"]["summary"])
        print(f"  resumed: {result['main']['resumed']}; the "
              f"in-flight unit "
              f"{result['main']['in_flight']} was charged "
              f"${result['main']['charged_liability']:.2f} as "
              f"unreconciled liability and re-run")
        print(f"  failure census: {json.dumps(result['main']['census'], sort_keys=True)}")
        print()
        print("the pilot, resumed to the end:")
        print(result["pilot"]["summary"])
        print(f"  failure census: {json.dumps(result['pilot']['census'], sort_keys=True)}")
        print()
        print("the re-measurement, the 246-unit plan:")
        print(result["remeasurement"]["summary"])
        print(f"  planned: {result['remeasurement']['planned']}"
              f" units; ran "
              f"{result['remeasurement']['units']}; the "
              f"budget stopped it at "
              f"${result['remeasurement']['budget']['spent']:.4f}"
              f" of "
              f"${result['remeasurement']['budget']['cap']:.2f}"
              f" ({result['remeasurement']['budget']['skipped']}"
              f" units skipped by the fit rule)")
        print(f"  failure census: "
              f"{json.dumps(result['remeasurement']['census'], sort_keys=True)}")
        print(f"  report: the eight tables, written to "
              f"{result['remeasurement']['report']['path']}")
        print()
        print("the reading sheet:")
        print(f"  {result['reading_sheet']['entries']} entries "
              f"({json.dumps(result['reading_sheet']['per_arm'], sort_keys=True)})")
        print(f"  merge: {result['reading_sheet']['merged']} "
              f"agreements, "
              f"{len(result['reading_sheet']['disagreements'])} "
              f"disagreements, "
              f"{len(result['reading_sheet']['unread'])} unread")
        print(f"  the re-measurement's sheet: "
              f"{result['remeasurement']['reading_sheet']['entries']}"
              f" entries "
              f"({json.dumps(result['remeasurement']['reading_sheet']['per_arm'], sort_keys=True)})")
        print(f"\nresults: {result['main']['path']}")
        print(f"         {result['pilot']['path']}")
        print(f"         {result['remeasurement']['path']}")
        print(f"         {result['reading_sheet']['path']}")
        print(f"         {result['remeasurement']['reading_sheet']['path']}")
        print(f"         {result['remeasurement']['report']['path']}")
        return 0

    # reading-sheet
    if args.command == "reading-sheet":
        path = Path(args.results_file)
        records = [json.loads(line) for line in
                   path.read_text(encoding="utf-8").splitlines()
                   if line.strip() and json.loads(line).get(
                       "record") == "unit"]
        questions = {q["id"]: q for q in load_questions()}
        sheet = export_reading_sheet(
            records, questions, scorer.KEYS,
            path.with_suffix(".reading-sheet.json"), SEED)
        print(f"reading sheet: {len(sheet['entries'])} entries — "
              f"{json.dumps(sheet['per_arm'], sort_keys=True)}")
        print(f"written: {path.with_suffix('.reading-sheet.json')}")
        return 0

    # remeasure-report: the eight tables, from a results
    # file's own units.
    path = Path(args.results_file)
    records = [json.loads(line) for line in
               path.read_text(encoding="utf-8").splitlines()
               if line.strip() and json.loads(line).get(
                   "record") == "unit"]
    questions = {q["id"]: q for q in load_questions()}
    report = remeasure_report(records, questions,
                              scorer.KEYS)
    print(f"the re-measurement's report: the eight "
          f"tables, from {len(records)} units")
    print(json.dumps(report, indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_cli(argv))


if __name__ == "__main__":
    sys.exit(main())
