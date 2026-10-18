"""The tier-4 runner (Ruling D52, command ARCH-20261017-122;
the runner's fixes ruled 2026-10-17, recorded as
advisor_review_2026_10_17 in the command's response).

Tier 4 is the capacity test: does the pipeline's structure recover
answers a single call misses, on work hard enough for a single call
to miss it? Every frozen batch registers itself in its own
manifest.json (R9) — the sha256 of its candidates and of each F2
question's corpus pages, its families, its calibration and pilot
ceilings, its per-unit ceilings, its deadline and its single-call
max_tokens — and this runner reads them all from the manifest, so a
new frozen batch is a directory and a manifest, never a code change:

* the pilot batch (evals/tier4/pilot/, D44) — five questions, four
  F1 (everything given but hard) and one F2 (the data lives in a
  fictional corpus), run in two modes under the $2.00 and $5.00
  ceilings its manifest registers;
* batch 2 (evals/tier4/batch2/, D44's second freeze) — two F2
  questions, its calibration the two D-pages units under the $1.00
  ceiling its manifest registers.

The model-visible text is the candidate's ``request`` only — plus,
for arm D on F2 (D-pages), that question's own corpus pages,
verbatim and in the manifest's listed order, each preceded by its
file name, under the registered separator. Never the requirements,
the reference design, the worked solution, the wrong designs or the
difficulty rationale: the leakage guard below asserts it, with its
break-proof, for every unit of every mode of every batch. Every F2
unit of arms F and E grounds with its own question's pages and no
other's (R9): a question whose pages are the tier-4 corpus profile's
corpus runs under that profile, and any other question runs under a
per-question grounding profile whose manifest lists its own pages —
two F2 questions in one batch never share a page. Arm A does not run
on F2.

The single-call arms (A, D, D-pages) run on the owner's ratified
provider pins (R7): the ``tier3_arm_a`` and ``tier3_arm_d`` entries
of OPENROUTER_PROVIDER_ORDER, mapped onto the tier-4 arms' own
function names, so the providers the owner ratified for arms A and D
serve the tier-4 arms that bill under their own labels. The ratified
line is read from the paid runners' own config file (``.env.tier3``),
where the owner ratified those entries — the ambient line the routing
layer reads from ``.env`` registers no ``tier3_arm_*`` entries. Every
unit records the provider that served each call; a unit served by any
other provider is recorded ``serving_mismatch``, kept in the record
and not read as a result. The comparison is on the provider's name,
not the string form each side writes it in — the response names the
provider bare (``InferenceNet``) while the order line writes the
call-time specifier (``inference-net/fp4``), normalized the way
``autornd/preflight.py`` has measured since 2026-09-30. The
single-call arms run with the
manifest's single-call max_tokens (R8: 32768, the cap the pipeline's
implement call already has); a unit whose answer ends on finish
``length`` is recorded truncated, flagged on the reading sheet and
not read as a result.

Every figure the record carries comes from the batch's manifest: the
per-unit ceilings, the deadline, the modes' ceilings, the
single-call max_tokens. The seeds, the registered separator and the
manifest version are this runner's own constants, named here and in
the results header. The gates are the owner's: TIER3_SPEND_AUTHORIZED
in .env.tier3 must equal the mode's registered ceiling exactly (R4),
and the servings map is the owner's standing pins, fingerprint
e0dc92a3aecb, refused otherwise. Every mode of every batch refuses to
start unless the freeze guard holds — the candidates hash to the
manifest's registered sha256, each question's corpus pages hash to
the manifest's registered sha256 over the pages concatenated in the
listed order, and every corpus page the tier-4 profile's manifest
mirrors in docs/tier4/ is byte-identical to the frozen page itself.

    python3 evals/tier4/runner.py preflight [calibration|pilot --ids IDS] [--batch DIR]
    python3 evals/tier4/runner.py plan [calibration|pilot --ids IDS] [--batch DIR]
    python3 evals/tier4/runner.py worst-case [--batch DIR]
    python3 evals/tier4/runner.py dry-run [--batch DIR]   # mocked, free
    python3 evals/tier4/runner.py reading-sheet RESULTS_FILE
    python3 evals/tier4/runner.py run calibration|pilot --ids IDS [--batch DIR]  # paid

The dry run is free by construction: the real machinery — the freeze
guard, the gates, the plan and its seeded order, the preflight, the
arm executors, the deadline, the fit-rule budget, the records, the
reading sheet — with the model-serving layer mocked the way the tier-3
dry run mocks it (a scripted client that bills through the real guard
and accounting, a fixture catalogue, a stand-in at the pipeline
boundary for arms E and F). No network, no spend. The dry run covers
both modes of the pilot batch and of batch 2. The paid modes wait for
the owner's gate line naming the mode's registered ceiling exactly.

The tier-3 runner (evals/tier3/runner.py) is imported by path, the
way the tests import it: evals/ is not an installed package. The arm
executors, the unit client, the worst-case tables, the preflight's
catalogue classes, the results log, the failure census and the dry
run's doubles are its; tier 4 registers its own seeds, scenario ids,
function labels, prompt floors and — since the fixes — its provider
mapping on top of them. The tier-3 changes the import needs are two
additive ``max_tokens`` parameters (``_registered_call``,
``_arm_single``), defaulting to the registered cap: tier 3's
behaviour is unchanged, and its tests pass unmodified.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import functools
import hashlib
import importlib.util
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values

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

from autornd.config import settings as harness_settings  # noqa: E402
from autornd.profiles import (          # noqa: E402
    DEFAULT_PROFILE, ProjectProfile, get_profile, load_profile,
    set_profile)
from autornd.knowledge.context import (  # noqa: E402
    DOCS_DIR, load_docs_context)
from autornd.routing.openrouter import (   # noqa: E402
    provider_order_for)
from autornd import preflight              # noqa: E402

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
    "CALIBRATION_SEED", "PILOT_ID_LIMIT", "PILOT_SEED",
    "PAGES_SEPARATOR", "TIER4_MANIFEST_VERSION",
    "TIER4_PROFILE", "DEFAULT_BATCH_DIR", "REFUSED_EXIT",
    "ExperimentRefused", "Tier3ResultsLog", "Tier4Batch",
    "UnitResult", "calibration_plan", "check_freeze",
    "corpus_context", "corpus_pages", "d_pages_message",
    "export_tier4_reading_sheet", "leakage_findings",
    "load_batch", "model_visible_message", "pilot_plan",
    "question_profile", "run_tier4_experiment",
    "run_tier4_unit", "tier4_dry_run", "tier4_gate_report",
    "tier4_pins", "tier4_preflight", "tier4_summarize",
    "unit_profile",
]

# ── The registered plan (the command's constraints) ─────
#
# Every constant here is a registered parameter: a value a unit's
# outcome depends on, so it is named in this file and the results
# header rather than buried in a call site. Everything a frozen
# batch registers — its families, its calibration and pilot
# ceilings, its per-unit ceilings, its deadline and its
# single-call max_tokens — lives in the batch's own
# manifest.json (R9) and is read from it by ``load_batch``
# below, never hardcoded here.

# The calibration mode's arms, by family: A and D on the F1
# questions, D-pages on the F2 one (R9's calibration rule —
# the one rule every batch's calibration plans by). Arm A does
# not run on F2.
CALIBRATION_ARMS_F1 = ("A", "D")
CALIBRATION_ARMS_F2 = ("D-pages",)

# The seeds the two modes' interleaved orders are shuffled with —
# registered, so the order's digest in the results header is the
# figure both the runner and the guard test compute.
CALIBRATION_SEED = 20261017
PILOT_SEED = 20261018

# The pilot's registered limit on named question ids.
PILOT_ID_LIMIT = 4

# The corpus profile the pilot batch's F2 question grounds under
# (``AUTORND_PROFILE=tier4`` — ``profiles/tier4.yaml``, whose
# docs dir mirrors the pilot batch's corpus pages, the freeze
# guard's byte-identity check). An F2 question whose pages are
# not this profile's corpus runs under a per-question grounding
# profile (R9) — see ``question_profile``.
TIER4_PROFILE = "tier4"

# The results record's identity: the manifest version the log's
# resume keys on. The dataset version is the batch's own —
# ``tier4-<batch>`` — carried from the batch, not a constant.
TIER4_MANIFEST_VERSION = "tier4-1"

# The registered separator between the request and the corpus pages
# in arm D's F2 user message (the command's ARM D ON F2 constraint).
PAGES_SEPARATOR = "\n\nReference documents:\n\n"

# The default batch (the pilot batch, D44) and the tier-4
# profile's docs dir, whose manifest.json lists the pilot
# corpus pages as global documents.
DEFAULT_BATCH_DIR = TIER4 / "pilot"
DOCS_TIER4 = ROOT / "docs" / "tier4"

# The exit code a refusal returns (the tier-3 CLI's convention).
REFUSED_EXIT = 3


# ── The frozen batch and the corpus ─────────────────────

@dataclass(frozen=True)
class Tier4Batch:
    """A frozen batch's own registration, read from its
    manifest.json (R9): the sha256 of its candidates and of
    each F2 question's corpus pages, its families, its
    calibration and pilot ceilings, its per-unit ceilings,
    its deadline and its single-call max_tokens.

    A frozen batch is a directory and a manifest; the runner
    reads every registered figure from it, so a new frozen
    batch is data, never a code change. A question's pages
    are the manifest's listed paths, in the listed order —
    the order the D-pages message and the corpus sha256 read
    them in."""
    name: str
    path: Path
    manifest_path: Path
    candidates_path: Path
    candidates_sha256: str
    corpus: dict[str, tuple[Path, ...]]
    corpus_sha256: dict[str, str]
    families: dict[str, str]
    calibration_ceiling: float
    pilot_ceiling: float
    pilot_arms: dict[str, tuple[str, ...]]
    per_unit_ceilings: dict[str, float]
    deadline_seconds: float
    single_call_max_tokens: int
    batch_dir: str

    @property
    def f1_ids(self) -> tuple[str, ...]:
        """The batch's F1 question ids, in the manifest's own
        order."""
        return tuple(question_id for question_id, family
                     in self.families.items()
                     if family == "F1")

    @property
    def f2_ids(self) -> tuple[str, ...]:
        """The batch's F2 question ids, in the manifest's own
        order."""
        return tuple(question_id for question_id, family
                     in self.families.items()
                     if family == "F2")

    @property
    def dataset_version(self) -> str:
        """The batch's dataset version — its own name, so one
        batch's records never carry another batch's version."""
        return f"tier4-{self.name}"

    def corpus_pages(self, question_id: str
                     ) -> list[tuple[str, str]]:
        """The question's corpus pages: (file name, content),
        in the manifest's listed order."""
        return [(path.name, path.read_text(encoding="utf-8"))
                for path in self.corpus.get(question_id, ())]

    def load_candidates(self) -> list[dict[str, Any]]:
        """The batch's candidates, as they stand on disk."""
        return json.loads(
            self.candidates_path.read_text(encoding="utf-8"))

    def questions(self) -> dict[str, dict[str, Any]]:
        """The batch's candidates keyed by question id."""
        return {candidate["id"]: candidate
                for candidate in self.load_candidates()}


def _read_batch(path: Path) -> Tier4Batch:
    """Read one batch's manifest into its registration.

    A manifest that does not register a field the runner
    needs is not a frozen batch — it refuses to load, naming
    the field, rather than running on a figure the batch
    never registered."""
    manifest_path = path / "manifest.json"
    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8"))

    def registered(field: str) -> Any:
        value = manifest.get(field)
        if value is None:
            raise ValueError(
                f"{manifest_path}: the batch's manifest does "
                f"not register {field!r} (R9: every frozen "
                "batch registers itself)")
        return value

    def resolve(registered_path: str) -> Path:
        """A manifest-registered path: absolute as it stands;
        repo-relative when the repository carries it (the
        frozen batches' own convention — the manifest names
        the candidates and corpus pages the way the repo
        lays them out); else relative to the batch's own
        directory (a synthetic batch's manifest)."""
        candidate = Path(registered_path)
        if candidate.is_absolute():
            return candidate
        rooted = ROOT / candidate
        return rooted if rooted.exists() else path / candidate

    corpus: dict[str, tuple[Path, ...]] = {}
    corpus_sha256: dict[str, str] = {}
    for question_id, entry in registered("corpus").items():
        pages = entry.get("pages")
        if not pages:
            raise ValueError(
                f"{manifest_path}: the corpus entry for "
                f"{question_id!r} registers no pages")
        corpus[question_id] = tuple(
            resolve(page) for page in pages)
        digest = entry.get("sha256")
        if not digest:
            raise ValueError(
                f"{manifest_path}: the corpus entry for "
                f"{question_id!r} registers no sha256")
        corpus_sha256[question_id] = digest
    calibration = registered("calibration")
    pilot = registered("pilot")
    return Tier4Batch(
        name=str(registered("batch")),
        path=path,
        manifest_path=manifest_path,
        candidates_path=resolve(registered("candidates")),
        candidates_sha256=str(registered("candidates_sha256")),
        corpus=corpus,
        corpus_sha256=corpus_sha256,
        families={str(question_id): str(family)
                  for question_id, family
                  in registered("families").items()},
        calibration_ceiling=float(calibration["ceiling_usd"]),
        pilot_ceiling=float(pilot["ceiling_usd"]),
        pilot_arms={str(family): tuple(arms)
                    for family, arms
                    in (pilot.get("arms") or {}).items()},
        per_unit_ceilings={
            str(arm): float(ceiling) for arm, ceiling
            in registered("per_unit_ceilings_usd").items()},
        deadline_seconds=float(registered("deadline_seconds")),
        single_call_max_tokens=int(
            registered("single_call_max_tokens")),
        batch_dir=(str(path.relative_to(ROOT))
                   if path.is_relative_to(ROOT) else str(path)),
    )


@functools.lru_cache(maxsize=None)
def _load_batch_cached(path: str) -> Tier4Batch:
    return _read_batch(Path(path))


def load_batch(path: str | Path | None = None) -> Tier4Batch:
    """A frozen batch's registration: the batch at ``path``,
    or the pilot batch (the default every mode runs when no
    ``--batch`` names another)."""
    return _load_batch_cached(
        str(Path(path).resolve() if path is not None
            else DEFAULT_BATCH_DIR.resolve()))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def batch_sha256(batch: Tier4Batch | None = None) -> str:
    """The sha256 of the batch's candidates.json bytes, as
    they stand on disk."""
    return sha256_bytes(
        (batch or load_batch()).candidates_path.read_bytes())


def corpus_sha256(question_id: str,
                  batch: Tier4Batch | None = None) -> str:
    """The sha256 of the question's corpus pages concatenated
    in the manifest's listed order — the manifest's own
    convention (the pages' bytes, no separator, listed
    order): ``cat <the listed pages> | sha256sum``."""
    digest = hashlib.sha256()
    for page in (batch or load_batch()).corpus.get(
            question_id, ()):
        digest.update(page.read_bytes())
    return digest.hexdigest()


@functools.lru_cache(maxsize=None)
def _mirrored_pages() -> frozenset[str]:
    """The corpus page names the tier-4 profile's docs
    manifest mirrors in docs/tier4/ — the pages the freeze
    guard's byte-identity check covers (the pilot batch's
    registration, command 122's acceptance criterion (c)).
    A question whose pages are not mirrored grounds through
    its own per-question manifest (R9), and its pages are
    the frozen pages themselves — nothing to mirror."""
    manifest = DOCS_TIER4 / "manifest.json"
    if not manifest.exists():
        return frozenset()
    try:
        listed = json.loads(
            manifest.read_text(encoding="utf-8")).get(
                "global", [])
    except (OSError, ValueError):
        return frozenset()
    return frozenset(Path(entry).name for entry in listed)


def check_freeze(batch: Tier4Batch | None = None) -> list[str]:
    """The freeze guard's refusals, each naming the file that drifted.

    Empty means the guard holds: the candidates hash to the
    manifest's registered sha256, each question's corpus pages
    hash to the manifest's registered sha256 over the pages
    concatenated in the listed order, and every corpus page the
    tier-4 profile's manifest mirrors in docs/tier4/ is
    byte-identical to the frozen page itself. A mode refuses to
    start on any refusal here — the run's evidence is the frozen
    batch, and a batch that moved under the run is a different
    experiment from the one the ceilings and the reading were
    registered for."""
    batch = batch or load_batch()
    refusals: list[str] = []
    if not batch.candidates_path.exists():
        refusals.append(
            f"{batch.candidates_path}: the batch's candidates "
            "are not on disk — the freeze guard cannot hash "
            "what is not there")
    else:
        measured = batch_sha256(batch)
        if measured != batch.candidates_sha256:
            refusals.append(
                f"{batch.candidates_path}: sha256 {measured} is "
                f"not the frozen batch's registered sha256 "
                f"{batch.candidates_sha256} — the batch moved "
                "under the run (the freeze guard, R9)")
    for question_id, pages in batch.corpus.items():
        missing = [str(page) for page in pages
                   if not page.exists()]
        if missing:
            refusals.append(
                f"{question_id}: the registered corpus pages "
                "are not on disk — the freeze guard cannot hash "
                "what is not there: " + ", ".join(missing))
            continue
        measured = corpus_sha256(question_id, batch)
        if measured != batch.corpus_sha256[question_id]:
            refusals.append(
                f"{question_id}: the corpus pages "
                + ", ".join(str(page) for page in pages)
                + " concatenated in the manifest's listed order "
                f"hash to {measured}, not the registered "
                f"sha256 {batch.corpus_sha256[question_id]} — "
                "the corpus moved under the run (the freeze "
                "guard, R9)")
        # The docs/tier4 mirror: a page the tier-4 profile's
        # manifest lists must be byte-identical to the frozen
        # page it copies — the profile's grounding copy is the
        # frozen page itself, never a retelling of it.
        for page in pages:
            if page.name not in _mirrored_pages():
                continue
            docs_copy = DOCS_TIER4 / page.name
            if (not docs_copy.exists()
                    or docs_copy.read_bytes() != page.read_bytes()):
                refusals.append(
                    f"{docs_copy}: not byte-identical to its "
                    f"corpus page {page} — the profile's "
                    "grounding copy must be the frozen page "
                    "itself (the freeze guard)")
    return refusals


# ── The model-visible text ──────────────────────────────

def d_pages_message(candidate: dict[str, Any],
                    batch: Tier4Batch | None = None) -> str:
    """Arm D's F2 user message: the request, the registered
    separator, and the question's own corpus pages verbatim and
    in the manifest's listed order, each preceded by its file
    name (R9: D-pages carries its own question's pages, and no
    other question's)."""
    pages = "\n\n".join(
        f"{name}\n\n{content}"
        for name, content in (batch or load_batch()).corpus_pages(
            candidate["id"]))
    return candidate["request"] + PAGES_SEPARATOR + pages


def model_visible_message(arm: str,
                          candidate: dict[str, Any],
                          batch: Tier4Batch | None = None) -> str:
    """The model-visible text the arm's treatment carries: the
    candidate's request only, plus, for arm D on F2, the
    question's own corpus pages under the registered separator.
    Never the requirements, the reference design, the worked
    solution, the wrong designs or the difficulty rationale —
    the leakage guard below asserts it."""
    if arm == "D-pages":
        return d_pages_message(candidate, batch)
    return candidate["request"]


def message_sha256(arm: str, candidate: dict[str, Any],
                   batch: Tier4Batch | None = None) -> str:
    """The sha256 of the exact user message the unit's treatment
    carries — the figure the unit record reports."""
    return sha256_bytes(
        model_visible_message(arm, candidate,
                              batch).encode("utf-8"))


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

class QuestionProfile(ProjectProfile):
    """An F2 question's own grounding profile (R9): the
    tier-4 profile's vocabulary, with the docs dir this
    question's grounding manifest lives at.

    ``get_docs_dir`` is the one hook ``load_docs_context``
    resolves a profile's manifest through, so a profile
    that names a scratch dir grounds on that dir's
    manifest — and nothing else. The scratch manifest
    lists the question's frozen corpus pages and no other
    question's, so an F2 unit of arm F or E grounds with
    its own question's pages and no other's."""

    def __init__(self, name: str, docs_dir: Path,
                 description: str = "") -> None:
        super().__init__(name=name, description=description)
        self.docs_dir = docs_dir

    def get_docs_dir(self) -> str:
        return str(self.docs_dir)


@functools.lru_cache(maxsize=None)
def _mirrored_manifest() -> tuple[str, ...]:
    """The ordered global entries of the tier-4 profile's
    docs manifest (docs/tier4/manifest.json) — the pages
    the tier-4 profile grounds on, in its own order."""
    manifest = DOCS_TIER4 / "manifest.json"
    if not manifest.exists():
        return ()
    try:
        listed = json.loads(
            manifest.read_text(encoding="utf-8")).get(
                "global", [])
    except (OSError, ValueError):
        return ()
    return tuple(str(entry) for entry in listed)


@functools.lru_cache(maxsize=None)
def _tier4_corpus_pages() -> tuple[tuple[str, str], ...]:
    """The corpus pages the tier-4 profile grounds on:
    (file name, content), in the mirror's own order. A
    frozen question whose pages equal these runs under
    the shipped tier-4 profile itself — byte-identical
    grounding — and any other question grounds on its
    own pages (R9)."""
    return tuple(
        (Path(entry).name,
         (DOCS_DIR / entry).read_text(encoding="utf-8"))
        for entry in _mirrored_manifest())


_GROUNDING_PROFILES: dict[str, QuestionProfile] = {}


def _grounding_profile(question_id: str,
                       batch: Tier4Batch | None = None
                       ) -> QuestionProfile:
    """The per-question grounding profile for a question
    whose pages the tier-4 profile does not mirror (R9):
    a scratch manifest under the results dir lists the
    question's frozen pages — and only those — and the
    profile reads it.

    The scratch dir is gitignored run output, regenerated
    from the frozen pages on every run, so a page edit
    cannot ground a unit: the freeze guard refuses the
    run before the profile is ever built."""
    batch = batch or load_batch()
    key = f"{batch.name}/{question_id}"
    profile = _GROUNDING_PROFILES.get(key)
    if profile is not None:
        return profile
    docs_dir = (RESULTS_DIR / "tier4-grounding"
                / batch.name / question_id)
    manifest = {
        "global": [
            os.path.relpath(page, DOCS_DIR)
            for page in batch.corpus[question_id]
        ],
    }
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8")
    profile = QuestionProfile(
        name=f"Tier4 {batch.name} {question_id}",
        docs_dir=docs_dir)
    _GROUNDING_PROFILES[key] = profile
    return profile


def question_profile(question_id: str,
                     batch: Tier4Batch | None = None
                     ) -> ProjectProfile | None:
    """The profile a question grounds under, or ``None``
    when the question grounds on nothing (every F1
    question). A question whose frozen pages are the
    tier-4 profile's own corpus pages — the pilot batch's
    T4-06 — runs under the shipped tier-4 profile, so its
    grounding is byte-identical to the pre-manifest
    runner's; every other F2 question grounds on its own
    pages through its per-question profile (R9)."""
    batch = batch or load_batch()
    if batch.families.get(question_id) != "F2":
        return None
    pages = tuple(batch.corpus_pages(question_id))
    if pages == _tier4_corpus_pages():
        return load_profile(TIER4_PROFILE)
    return _grounding_profile(question_id, batch)


def unit_profile(question_id: str, arm: str,
                 batch: Tier4Batch | None = None
                 ) -> ProjectProfile | None:
    """The profile the unit runs under (the command's
    PROFILES constraint): the question's own grounding
    profile for an F2 unit of arm F or E — the pipeline's
    own grounding node loads the question's pages into
    the requests that read it — and the process default
    for every other unit, so no corpus text reaches an F1
    question. Arm D on F2 (D-pages) carries the pages in
    its user message and runs the single-call treatment,
    so it runs under the default too."""
    batch = batch or load_batch()
    if batch.families.get(question_id) != "F2":
        return None
    if arm not in ("E", "F"):
        return None
    return question_profile(question_id, batch)


@contextlib.contextmanager
def _profile_selected(profile: ProjectProfile | None):
    """Run under the named profile, restoring the previous
    one.

    ``set_profile`` is the profile mechanism's own
    resolution path — the one ``AUTORND_PROFILE`` drives
    through ``get_profile()`` — so a unit's grounding
    reads the profile the unit registered, whatever the
    process's environment says."""
    previous = get_profile()
    set_profile(profile if profile is not None
                else DEFAULT_PROFILE)
    try:
        yield
    finally:
        set_profile(previous)


def corpus_context() -> str:
    """The grounding context the tier-4 profile carries:
    the corpus pages, exactly as ``load_docs_context``
    loads them under ``AUTORND_PROFILE=tier4``."""
    with _profile_selected(load_profile(TIER4_PROFILE)):
        return load_docs_context([], [])


def question_grounding_context(question_id: str,
                               batch: Tier4Batch | None = None
                               ) -> str:
    """The grounding context a question's pipeline calls
    read: the question's own pages for an F2 question,
    nothing for an F1 question (the default manifest's
    globals are empty)."""
    profile = question_profile(question_id, batch)
    if profile is None:
        return ""
    with _profile_selected(profile):
        return load_docs_context([], [])


def prompt_floor(arms: tuple[str, ...],
                 questions: dict[str, dict[str, Any]],
                 batch: Tier4Batch | None = None) -> str:
    """The largest prompt the mode's pipeline calls can carry.

    For arms E and F the entry point is the scenario request, and
    the pipeline's own node prompts sit above it — the grounding
    node loads the question's own pages into every request an F2
    question reads, and an F1 question grounds on nothing (the
    default manifest's globals are empty). The floor is the largest
    request with its grounding context, the way the tier-3 tables
    read the largest question: a floor, with the guard's call-time
    computation the binding check."""
    floors: list[str] = []
    for candidate in questions.values():
        request = candidate["request"]
        if candidate["family"] == "F2":
            floors.append(
                request + "\n\n"
                + question_grounding_context(
                    candidate["id"], batch))
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


def candidate_index(batch: Tier4Batch | None = None
                    ) -> dict[str, dict[str, Any]]:
    """The batch's candidates keyed by question id."""
    return (batch or load_batch()).questions()


def calibration_plan(batch: Tier4Batch | None = None
                     ) -> list[list[Any]]:
    """The calibration mode's units, in the seeded interleaved
    order: arm A on every F1 question, arm D on every F1
    question, arm D-pages on every F2 question, one repetition
    each (R9: the plan's questions are the batch's own — the
    batch's families decide which questions are F1 and which
    are F2, so a new frozen batch calibrates itself)."""
    batch = batch or load_batch()
    units: list[list[Any]] = [
        [question_id, 1, arm]
        for question_id in batch.f1_ids
        for arm in CALIBRATION_ARMS_F1
    ]
    units.extend([question_id, 1, arm]
                 for question_id in batch.f2_ids
                 for arm in CALIBRATION_ARMS_F2)
    return tier4_order(CALIBRATION_SEED, units)


def family_arms(family: str, mode: str,
                batch: Tier4Batch | None = None
                ) -> tuple[str, ...]:
    """The arms the mode runs on a question of this family.
    The calibration arms are the runner's own registration
    (A and D on F1, D-pages on F2); the pilot's arms per
    family are the batch's own registration (R9), so a batch
    that runs an arm in a mode the pilot does not is data,
    not a code change."""
    if mode == "calibration":
        return (CALIBRATION_ARMS_F2 if family == "F2"
                else CALIBRATION_ARMS_F1)
    return (batch or load_batch()).pilot_arms.get(
        family, ())


def pilot_plan(question_ids: list[str],
               batch: Tier4Batch | None = None,
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
    batch = batch or load_batch()
    refusals: list[str] = []
    if len(question_ids) > PILOT_ID_LIMIT:
        refusals.append(
            f"the pilot names {len(question_ids)} question ids; "
            f"its registered limit is {PILOT_ID_LIMIT} "
            "(PILOT_ID_LIMIT)")
    candidates = candidate_index(batch)
    for question_id in question_ids:
        if question_id not in candidates:
            refusals.append(
                f"question id {question_id!r} is not in the frozen "
                f"batch ({batch.candidates_path}) — the pilot runs "
                "the frozen batch's questions only")
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
                    else family_arms(family, "pilot", batch)):
            if arm not in family_arms(family, "pilot", batch):
                refusals.append(
                    f"arm {arm} does not run on a question of family "
                    f"{family} ({question_id}'s family runs "
                    + ", ".join(family_arms(family, "pilot", batch))
                    + " — the batch's registered family arms)")
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
    mode's registered ceiling exactly — the calibration mode's
    registered ceiling, the pilot's — an authorization above the
    ceiling would spend
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


# ── The provider pins (R7) ─────────────────────────────

def _map_tier4_pins(raw: str) -> str:
    """The owner's provider-order line, extended with the tier-4
    single-call arms' pins (R7): the ``tier3_arm_a`` and
    ``tier3_arm_d`` entries re-keyed to the tier-4 functions the
    single-call arms bill to.

    The owner's line is a ratification (G-2), and the single-call
    arms are the same workloads on the same servings, so the
    mapping copies the ratification onto the tier-4 functions
    rather than asking for a second one — the void calibration's
    defect was precisely that the tier-4 functions matched no key
    and fell to the line's general list. A tier3 entry with no
    provider maps to an explicitly empty tier-4 entry — unpinned,
    and refused by the preflight — because an absent key would
    fall to the general list, which is what served the void
    calibration. A line that already carries the tier-4 entries is
    re-mapped, so the mapping is idempotent over its own output."""
    per_tier: dict[str, str] = {}
    kept: list[str] = []
    for entry in raw.split(","):
        name, separator, provider = entry.partition(":")
        if not entry.strip():
            continue
        if separator and name.strip().lower() in (
                "tier4_arm_a", "tier4_arm_d"):
            # A previous mapping's entries: re-keyed below, so the
            # mapping is idempotent over a line it already mapped.
            continue
        kept.append(entry.strip())
        if separator:
            per_tier[name.strip().lower()] = provider.strip()
    return ",".join(
        kept + [
            f"tier4_arm_a:{per_tier.get('tier3_arm_a', '')}",
            f"tier4_arm_d:{per_tier.get('tier3_arm_d', '')}",
        ])


@contextlib.contextmanager
def tier4_pins(line: str | None = None):
    """Run with the tier-4 single-call arms pinned to the owner's
    ratified tier-3 pins (R7).

    The provider-order line the harness settings carry — the
    owner's standing line, or ``line`` — is extended by the
    mapping and installed on the harness settings singleton for
    the run's duration (the same mechanism the tier-3 dry run's
    pin overrides use), and restored afterwards. The routing
    layer reads the singleton per call, so every single-call
    arm's chat carries its pin's provider order, and the unit
    record's serving figures name the providers that actually
    served."""
    raw = (line if line is not None
           else (harness_settings.openrouter_provider_order
                 or ""))
    mapped = _map_tier4_pins(raw)
    previous = harness_settings.openrouter_provider_order
    harness_settings.openrouter_provider_order = mapped
    try:
        yield
    finally:
        harness_settings.openrouter_provider_order = previous


# The paid runners' own config file (G-3: the owner's), read for the
# ratified pin line (R7) and keyed by the authorisation claim (R11).
TIER3_ENV_FILE = Path(".env.tier3")

# R11 (the advisor's review of 2026-10-18): one authorisation pays for
# one run. Measured 2026-10-17: the pilot batch's calibration ran twice
# under one unchanged TIER3_SPEND_AUTHORIZED=2.00 (01:14Z and 02:10Z,
# $1.0832 + $1.0839), two launchers each passing the exact gate (R4),
# which checks the amount, not whether it was already spent.
CLAIM_DIR = RESULTS_DIR / ".authorizations"


def claim_authorization(claim_dir: Path, mode: str, batch_name: str,
                        amount: str, env_file: Path,
                        results_path: Path) -> str | None:
    """Claim the run's authorisation before its first paid call (R11).

    The claim is keyed by the mode, the batch, the authorised amount
    and the config file's modification time, so the owner
    re-authorises by re-setting the line. It is an exclusive create,
    so two concurrent launchers cannot both claim. A claim already
    held by the same results file is the same run resuming, and is
    allowed. Returns None when the run holds the claim, else the
    refusal naming the run that spent it."""
    try:
        mtime = env_file.stat().st_mtime_ns
    except OSError:
        mtime = 0
    key = hashlib.sha256(
        f"{mode}|{batch_name}|{amount}|{mtime}".encode()).hexdigest()
    claim_dir.mkdir(parents=True, exist_ok=True)
    marker = claim_dir / f"{mode}-{batch_name}-{key[:16]}.claim"
    record = {"mode": mode, "batch": batch_name, "amount": amount,
              "results_path": str(results_path),
              "claimed_at": datetime.now(timezone.utc).isoformat()}
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            held = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            held = {}
        if held.get("results_path") == str(results_path):
            return None
        return (f"TIER3_SPEND_AUTHORIZED={amount} for the {mode} of "
                f"batch {batch_name} was already spent by the run "
                f"recording to {held.get('results_path', '?')} "
                f"(claimed {held.get('claimed_at', '?')}); one "
                "authorisation pays for one run (R11) - re-set the "
                "line in .env.tier3 to authorise another")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(record, handle)
    return None


def _ratified_provider_order(env_file: Path | None = None) -> str:
    """The owner's ratified provider-order line, read from the
    paid runners' own config file (R7).

    The routing layer reads OPENROUTER_PROVIDER_ORDER from the
    ambient environment and .env — the workflow tiers' pins,
    which register no tier3_arm_a/tier3_arm_d entries. The
    owner ratified the single-call arms' pins on the paid
    runners' line, in .env.tier3 (G-3: the owner's file), and
    an ambient export of the same variable would shadow a
    pydantic-settings read of the file — so the tier-4 paid
    path reads the file directly, and the R7 mapping re-keys
    the entries the owner actually ratified, wherever the run
    is launched from. An absent file or line reads as empty,
    and the preflight refuses the arm: an unpinned arm never
    falls to the line's general list, which is what served
    the void calibration."""
    values = dotenv_values(
        str(env_file) if env_file is not None else str(TIER3_ENV_FILE))
    return (values.get("OPENROUTER_PROVIDER_ORDER") or "").strip()


def _arm_pin_key(arm: str) -> str:
    """The tier-4 function an arm's single call bills to."""
    return f"tier4_arm_{ceiling_key(arm).lower()}"


def _arm_pin(arm: str) -> list[str]:
    """The providers an arm's single call is pinned to (R7),
    resolved through the provider-order line the run installed.

    Empty is an arm with no pin: the mapping installs an
    explicitly empty entry when the owner's line registers no
    tier3 counterpart, so an empty resolution is a refusal —
    never a fall to the line's general list, which is what
    served the void calibration."""
    return provider_order_for(_arm_pin_key(arm))


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
        index: dict[str, dict[str, Any]],
        max_tokens: int = tier3.REGISTERED_MAX_TOKENS
        ) -> float:
    """The worst case of a single-call arm's one call, at the guard's
    own formula: the call's max_tokens against the arm's serving's
    rates, the prompt side the largest message the arm carries. Arm
    D-pages' message is the largest text any tier-4 arm carries —
    the request with the corpus pages inlined. The tier-4
    single-call arms run at the batch's registered max_tokens (R8),
    so a tier-4 worst case is computed at that cap, not tier 3's."""
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
        max_tokens, per_request)


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
        questions: dict[str, dict[str, Any]],
        mode: str = "pilot",
        batch: Tier4Batch | None = None,
        ) -> PreflightReport:
    """The tier-4 preflight, before the first unit. Free: it reads
    the catalogue fixture or the free GET's result, and computes.

    It refuses to start, and prints each arm's per-call and per-unit
    worst case at the catalogue's shape, in the command's cases:

    1. any serving the mode's arms name has no catalogue price
       (D49: an unknown price is not free), or is not in the
       catalogue at all;
    2. a single-call arm (A, D, D-pages) whose call's worst case —
       the batch's registered max_tokens at the largest message the
       arm carries, the guard's own formula — exceeds its per-unit
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

    The per-unit ceilings, the deadline and the single-call
    max_tokens are the batch's own registrations (R9), so every
    figure the preflight prints is the figure the batch registered,
    for whichever batch the mode runs.
    """
    batch = batch or load_batch()
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

    # Case 1b (R7): each single-call arm's provider pin, and the
    # pipeline arms' per-tier orders, informationally. A single-call
    # arm's chat carries its pin's provider order; an arm with no pin
    # would run on the line's general list — exactly what served the
    # void calibration — and the mode refuses to start.
    for arm in ("A", "D", "D-pages"):
        if arm not in arms:
            continue
        pin = _arm_pin(arm)
        if pin:
            report.reports.append(
                f"arm {arm}: pinned to " + ", ".join(pin)
                + f" (R7: the owner's ratified "
                f"{'tier3_arm_a' if arm == 'A' else 'tier3_arm_d'} "
                "pin, re-keyed to the tier-4 function the arm "
                "bills to)")
        else:
            report.refusals.append(
                f"arm {arm}: no provider pin — the provider-order "
                f"line registers no {_arm_pin_key(arm)} entry (R7: "
                "the single-call arms run on the owner's ratified "
                "tier3_arm_a/tier3_arm_d pins, and an arm with no "
                "pin would run on the line's general list — what "
                "served the void calibration)")
    if report.refusals:
        return report
    for arm in ("E", "F"):
        if arm not in arms:
            continue
        # Arm F runs arm E's path on arm E's tiers, so its
        # lineup is the E entry of the servings map.
        lineup = servings["E" if arm == "F" else arm]
        for tier, serving in lineup.items():
            report.reports.append(
                f"arm {arm}/{tier}: the serving {serving}'s provider "
                "order is "
                + (", ".join(provider_order_for(tier))
                   or "unpinned — the line's general list"))

    # Case 2: each single-call arm's one call, at the largest
    # message the arm carries among the mode's questions.
    for arm in ("A", "D", "D-pages"):
        if arm not in arms:
            continue
        floor = max(
            (model_visible_message(arm, candidate)
             for candidate in questions.values()),
            key=lambda text: len(text.encode("utf-8")))
        worst = _single_call_worst_case(
            arm, floor, servings, index,
            batch.single_call_max_tokens)
        arm_ceiling = batch.per_unit_ceilings[ceiling_key(arm)]
        report.reports.append(
            f"arm {arm}: one call, the largest message the mode "
            f"carries — worst case ${worst:.4f} against the "
            f"${arm_ceiling:.2f} per-unit ceiling "
            f"({'refused even at zero spend' if worst > arm_ceiling else 'within the ceiling'}; "
            "the prompt side is the largest message, a floor — the "
            "guard computes the real bytes at call time; the "
            "call runs at the batch's registered max_tokens "
            f"{batch.single_call_max_tokens} (R8))")
        if worst > arm_ceiling:
            report.refusals.append(
                f"arm {arm}: the worst case of its one call is "
                f"${worst:.4f}, above its per-unit ceiling "
                f"${arm_ceiling:.2f} (the registered max_tokens "
                f"{batch.single_call_max_tokens} at the largest "
                f"message the arm carries) — STOP and report the "
                "figure; the ceiling is not raised")

    # Cases 3 and 4: the tier-3 worst-case tables, at the tier-4
    # prompt floor and the tier-4 per-unit ceilings. Every row is
    # reported — the preflight prints each arm's per-call and
    # per-unit worst case at the catalogue's shape — and a row
    # that refuses even at zero spend refuses the mode.
    floor = prompt_floor(arms, questions, batch)
    if "F" in arms:
        for row in tier3.arm_f_worst_case(
                servings, catalogue, prompt_floor=floor,
                unit_ceiling=batch.per_unit_ceilings["F"]):
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
                f"${batch.per_unit_ceilings['F']:.2f} per-unit ceiling "
                f"({'refused even at zero spend' if row['refuses_even_at_zero_spend'] else 'within the ceiling'}; "
                "the prompt side is the largest prompt, a floor — "
                "the guard computes the real bytes at call time)")
            if row.get("refuses_even_at_zero_spend"):
                report.refusals.append(
                    f"arm F/{row['tier']}: the worst case "
                    f"${row['worst_case']:.4f} refuses even at zero "
                    f"spend, above the "
                    f"${batch.per_unit_ceilings['F']:.2f} per-unit ceiling "
                    "(the ceiling is not raised)")
    if "E" in arms:
        for row in tier3.arm_e_worst_case(
                servings, catalogue, prompt_floor=floor,
                unit_ceiling=batch.per_unit_ceilings["E"]):
            if row.get("unknown"):
                report.refusals.append(
                    f"arm E/{row['tier']}: {row['serving']} — no "
                    f"worst case the guard can bound: "
                    f"{row.get('reason')}")
                continue
            report.reports.append(
                f"arm E/{row['tier']}: {row['serving']} — "
                f"worst case per call ${row['worst_case']:.4f} "
                f"against the ${batch.per_unit_ceilings['E']:.2f} per-unit "
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
                    f"${batch.per_unit_ceilings['E']:.2f} per-unit ceiling "
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
            f"the {mode}'s registered ceiling "
            f"${ceiling:.2f} (shortfall "
            f"${ceiling - credit:.2f})")
    return report


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
        batch: Tier4Batch | None = None,
        ) -> dict[str, Any]:
    """Dispatch to the arm's executor and shape its payload — the
    tier-3 executor's own dispatch, at the tier-4 registrations:
    the batch's per-unit ceilings, the tier-4 scenario ids and
    function labels, and D-pages as arm D's single call carrying
    the corpus pages in its user message. The single-call arms'
    one call runs at the batch's registered max_tokens (R8).

    ``client_holder`` receives the unit's client as soon as it
    exists, so the unit's record carries the figures the client
    booked (spend, unreconciled liability) even when a call fails
    mid-flight — the manifest's outstanding-liability rule."""
    batch = batch or load_batch()
    unit_key = (question_id, repetition, arm)
    if arm in ("A", "D", "D-pages"):
        serving = servings[ceiling_key(arm)]
        client = _unit_client(
            unit_key, arm, serving,
            batch.per_unit_ceilings[ceiling_key(arm)], 1,
            factory=client_factory)
        if client_holder is not None:
            client_holder["client"] = client
        # D-pages is arm D's treatment — arm D's own system prompt
        # (evals/tier3/prompts/arm_d.md, unchanged) — with the
        # corpus pages in the user message; the call bills to the
        # experiment's own function label.
        answer, finish_reasons = await _arm_single(
            ceiling_key(arm), message, serving, client,
            function_prefix="tier4",
            max_tokens=batch.single_call_max_tokens)
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
        unit_ceiling=batch.per_unit_ceilings[arm])
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
        deadline: float | None = None,
        deadline_overrides: dict[tuple[str, int, str],
                                 float] | None = None,
        client_factory: Any = None,
        tool_dispatcher: Any = None,
        scenario_runner: Any = None,
        spec: Any = None,
        spec_f: Any = None,
        pipeline_client_factory: Any = None,
        batch: Tier4Batch | None = None,
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
    denominator, never dropped. The single-call arms' one call runs
    at the batch's registered max_tokens (R8) on the pin in force
    (R7): a call served by any provider outside the pin — or served
    at all with no pin in force — is flagged serving_mismatch on
    the record, and a 'length' finish is flagged truncated; both
    show on the reading sheet, and a flagged unit is not read as a
    result.
    """
    batch = batch or load_batch()
    if deadline is None:
        deadline = batch.deadline_seconds
    question_id, repetition, arm = unit_key
    candidate = questions[question_id]
    family = candidate["family"]
    message = model_visible_message(arm, candidate, batch)
    result = UnitResult(
        question_id=question_id, repetition=repetition, arm=arm,
        status="incomplete",
        serving=_serving_record(ceiling_key(arm), servings))
    effective_deadline = (deadline_overrides or {}).get(
        unit_key, deadline)
    profile = unit_profile(question_id, arm, batch)
    profile_name = (profile.name if profile is not None
                    else "default")

    # The fit rule, decided before any client exists. Arms E and F's
    # run_scenario makes the same decision inside itself, with the
    # same budget object, so the two ceilings compose the way the
    # harness's sweeps compose them.
    if (arm not in ("E", "F") and budget is not None
            and not budget.can_start(
                batch.per_unit_ceilings[ceiling_key(arm)])):
        result.status = "skipped"
        result.stop_reason = budget.skip(
            batch.per_unit_ceilings[ceiling_key(arm)])
        return result

    started = time.perf_counter()
    client: OpenRouterClient | None = None
    run: Any = None
    made: dict[str, Any] = {}
    try:
        with isolate():
            with _profile_selected(
                    profile if profile is not None else None):
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
                        client_holder=made,
                        batch=batch),
                    effective_deadline)
        client = payload.get("client")
        run = payload.get("run")
        answer = payload.get("answer")
        result.calls = payload.get("calls", 0)
        result.finish_reasons = payload.get("finish_reasons", [])
        result.tool_invocations = payload.get("tool_invocations", [])
        result.truncated = any(
            reason == "length" for reason in result.finish_reasons)
        # R7: the serving the arm's single call actually ran
        # on, against the pin in force. A unit served by any
        # provider outside its pin — or served at all with no
        # pin in force, the void calibration's defect — is a
        # serving mismatch: recorded, and not read as a
        # result. A unit nothing served (a failure before any
        # reply) carries no mismatch: it failed, it was not
        # mis-served. Arms E and F's pipeline tiers carry
        # their own ratified pins (the tier-3 gates ratify
        # the servings map), and their per-tier providers are
        # recorded above.
        if (arm in ("A", "D", "D-pages")
                and client is not None):
            pin = _arm_pin(arm)
            served = sorted(client.providers_by_function.get(
                _arm_pin_key(arm), ()))
            result.serving_pins = list(pin)
            # The comparison is on the provider's name, not
            # on the string form each side writes it in: the
            # response names the provider bare ("InferenceNet")
            # while the owner's order line writes the call-time
            # specifier ("inference-net/fp4"), a form the repo
            # measured 2026-09-30 never matching the bare name
            # raw (autornd/preflight.py, _base_provider). The
            # quant is a routing request the response does not
            # echo, so the provider identity is what R7's
            # comparison verifies. Measured live 2026-10-17:
            # the batch-2 calibration's two D-pages units, both
            # served by the pinned InferenceNet, were flagged
            # serving_mismatch on exactly that gap.
            result.serving_mismatch = (
                bool(served)
                and (not pin
                     or not {preflight._base_provider(p)
                             for p in served}
                         <= {preflight._base_provider(p)
                             for p in pin}))
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
                budget.record(
                    batch.per_unit_ceilings[ceiling_key(arm)])
                result.unreconciled_liability += (
                    batch.per_unit_ceilings[ceiling_key(arm)])
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
    claim from a measured zero). The R7/R8 flags ride here too: the
    serving pins in force and whether the unit was served outside
    them, and the truncated flag the tier-3 record already carries —
    a flagged unit is not read as a result."""
    record = result.record()
    record["family"] = candidate["family"]
    record["profile"] = profile_name
    record["message_sha256"] = sha256_bytes(
        message.encode("utf-8"))
    record["serving_pins"] = getattr(
        result, "serving_pins", None)
    record["serving_mismatch"] = bool(
        getattr(result, "serving_mismatch", False))
    pipeline = record.get("pipeline")
    record["candidate"] = (pipeline or {}).get("candidate")
    record["iterations"] = (pipeline or {}).get("iterations")
    record["reason"] = (pipeline or {}).get("reason")
    return record


# ── The experiment driver ───────────────────────────────

def default_results_path(mode: str,
                         batch: Tier4Batch | None = None
                         ) -> Path:
    """evals/results/<utc-timestamp>-tier4-<mode>.jsonl —
    the default batch's own path; another batch's name joins
    the stem, so two batches' runs never write the same
    file."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch = batch or load_batch()
    suffix = (f"-{batch.name}" if batch.name != "pilot"
              else "")
    return RESULTS_DIR / f"{stamp}-tier4-{mode}{suffix}.jsonl"


def mode_arms(mode: str,
              batch: Tier4Batch | None = None
              ) -> tuple[str, ...]:
    """Every arm the mode can run, in the plan's own order:
    the calibration's registered arms, or the batch's own
    pilot registration, deduplicated."""
    if mode == "calibration":
        return CALIBRATION_ARMS_F1 + CALIBRATION_ARMS_F2
    return tuple(dict.fromkeys(
        arm for arms
        in (batch or load_batch()).pilot_arms.values()
        for arm in arms))


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
        batch: Tier4Batch | None = None,
        claim_dir: Path | None = None,
        ) -> dict[str, Any]:
    """One tier-4 experiment run: the freeze guard, the gates, the
    plan, the free preflight, then every unit of the plan in the
    seeded interleaved order, under the sweep budget, each recorded
    as it finishes.

    The whole run executes under the provider pins in force (R7):
    the owner's provider-order line, extended by the mapping with
    the ``tier4_arm_a``/``tier4_arm_d`` entries the single-call
    arms bill to, installed on the harness settings for the run's
    duration — so the preflight's pin case and every single-call
    arm's chat read the same line, and the run restores the line it
    found. The batch's own registrations supply every figure: the
    mode's ceiling, the per-unit ceilings, the deadline and the
    single-call max_tokens (R8, R9).
    """
    batch = batch or load_batch()
    with tier4_pins():
        return await _run_tier4_experiment(
            mode, question_ids=question_ids,
            results_path=results_path,
            client_factory=client_factory,
            tool_dispatcher=tool_dispatcher,
            scenario_runner=scenario_runner,
            pipeline_client_factory=pipeline_client_factory,
            catalogue=catalogue, credit=credit,
            deadline_overrides=deadline_overrides,
            batch=batch, claim_dir=claim_dir)


async def _run_tier4_experiment(
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
        batch: Tier4Batch | None = None,
        claim_dir: Path | None = None,
        ) -> dict[str, Any]:
    tier3_settings = Tier3Settings()
    servings = _resolve_servings(tier3_settings)
    fingerprint = _servings_fingerprint(servings)
    authorization = (batch.calibration_ceiling
                     if mode == "calibration"
                     else batch.pilot_ceiling)

    # The freeze guard: the batch and the corpus as they stand are
    # the ones the evidence registered.
    freeze = check_freeze(batch)
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

    # The plan: the calibration's units — every F1 question x A
    # and D, every F2 question x D-pages — or the pilot's named
    # ids x their family's arms, from the batch's own families
    # and pilot registration.
    if mode == "calibration":
        order = calibration_plan(batch)
        questions = {question_id: candidate
                     for question_id, candidate
                     in candidate_index(batch).items()
                     if question_id in batch.f1_ids
                     or question_id in batch.f2_ids}
        named_ids = list(batch.f1_ids + batch.f2_ids)
    else:
        order, refusals = pilot_plan(question_ids or [], batch)
        if refusals:
            raise ExperimentRefused(
                "the pilot plan refused to start",
                servings, fingerprint, refusals)
        questions = {question_id: candidate
                     for question_id, candidate
                     in candidate_index(batch).items()
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
        arms=arms, questions=questions, mode=mode, batch=batch)
    if report.refusals:
        raise ExperimentRefused(
            "the preflight refused to start",
            servings, fingerprint, report.refusals)

    path = (Path(results_path) if results_path is not None
            else default_results_path(mode, batch))

    # R11: one authorisation pays for one run. A run on the live
    # serving layer (no mocked client, runner or pipeline factory)
    # claims its authorisation here, after every free check and
    # before its first paid call; a caller may name a claim
    # directory to exercise the claim with mocks.
    if (claim_dir is None and client_factory is None
            and scenario_runner is None
            and pipeline_client_factory is None):
        claim_dir = CLAIM_DIR
    if claim_dir is not None:
        spent = claim_authorization(
            Path(claim_dir), mode, batch.name,
            str(tier3_settings.tier3_spend_authorized),
            TIER3_ENV_FILE, path)
        if spent:
            raise ExperimentRefused(
                "the authorisation was already spent",
                servings, fingerprint, [spent])

    log = Tier3ResultsLog(path, config={
        "record": "header",
        "mode": mode,
        "manifest_version": TIER4_MANIFEST_VERSION,
        "dataset_version": batch.dataset_version,
        "batch": batch.name,
        "batch_dir": batch.batch_dir,
        "batch_sha256": batch_sha256(batch),
        "corpus_sha256": {
            question_id: corpus_sha256(question_id, batch)
            for question_id in batch.corpus},
        "seed": (CALIBRATION_SEED if mode == "calibration"
                 else PILOT_SEED),
        "question_ids": named_ids,
        "repetitions": 1,
        "arms": list(arms),
        "order_sha256": digest,
        "order_units": len(order),
        "servings": servings,
        "servings_fingerprint": fingerprint,
        "ceilings": dict(batch.per_unit_ceilings),
        "authorization_ceiling": authorization,
        "max_tokens": batch.single_call_max_tokens,
        "temperature": tier3.REGISTERED_TEMPERATURE,
        "deadline_seconds": batch.deadline_seconds,
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
        charged = batch.per_unit_ceilings[ceiling_key(in_flight[2])]
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
            pipeline_client_factory=pipeline_client_factory,
            batch=batch)
        # The tier-4 record: the unit's own fields, plus the family,
        # the profile and the message sha256 the command's RECORDS
        # constraint names.
        candidate = questions[key[0]]
        profile = unit_profile(key[0], key[2], batch)
        record = tier4_unit_record(
            result, candidate, key[2],
            profile.name if profile is not None else "default",
            model_visible_message(key[2], candidate, batch))
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
                        rest_key[0], rest_key[2], batch)
                    or "default")
                not_run_record["message_sha256"] = message_sha256(
                    rest_key[2], questions[rest_key[0]], batch)
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
    count, the readable count, the spend and the latency; then the
    totals. Every failure class is in its arm's denominator. Tier 4's
    primary measure is the two blind hand readings against the
    requirement statements (D52 §5) — the scorer is not a measure
    here, so no correctness fraction is claimed.

    A unit is readable when it delivered an answer that is neither
    truncated (a 'length' finish, R8) nor served outside its pin
    (R7): a flagged unit is recorded, and not read as a result."""
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
        delivered = sum(
            1 for r in arm_records
            if r.get("status") == "delivered")
        readable = sum(
            1 for r in arm_records
            if r.get("status") == "delivered"
            and not r.get("truncated")
            and not r.get("serving_mismatch"))
        lines.append(
            f"arm {arm}: {len(arm_records)} units — {status_line}; "
            f"delivered {delivered}"
            f"/{len(arm_records)}; "
            f"readable {readable}/{len(arm_records)}; "
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
    grades the answer against), and the delivered answer — beside
    the two flags that stop a unit being read as a result (R7, R8):
    a truncated answer (a 'length' finish) and a serving mismatch
    (a provider outside the pin in force). The flags carry no arm
    information, so the sheet stays arm-blind. The tier-3
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
            "truncated": bool(record.get("truncated")),
            "serving_mismatch": bool(
                record.get("serving_mismatch")),
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

# The dry run's provider-order line: the pin lineup the
# mocked run installs on the harness settings (the owner's
# standing line's shape, with the dry run's own servings),
# so the single-call arms' calls carry a provider order the
# way the owner's run does and the preflight's pin case
# holds. The tier3_arm_a/tier3_arm_d entries are the ones
# the R7 mapping re-keys to the tier-4 functions; the
# pipeline tiers are the tiers arms E and F run on, each
# pinned to its dryrun serving.
DRY_RUN_PROVIDER_ORDER = ",".join(
    [f"tier3_arm_a:{DRY_RUN_SERVINGS['A']}",
     f"tier3_arm_d:{DRY_RUN_SERVINGS['D']}"]
    + [f"{tier}:{DRY_RUN_SERVINGS['E'][tier]}"
       for tier in tier3.PIPELINE_TIERS])

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


def _at_tier4_ceiling(arm: str, answer: str,
                      batch: Tier4Batch | None = None
                      ) -> dict[str, Any]:
    """A pipeline run that used a hair under its per-unit ceiling (the
    pilot dry run's E and F default): the workflow's own profile,
    priced at the batch's registered per-unit ceiling with the
    tiers' shares held."""
    outcome = _shipped(
        answer, profile=("verify-first" if arm == "F" else "standing"))
    ceiling = ((batch or load_batch()).per_unit_ceilings[arm]
               * 0.999)
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


def _unpinned_call(answer: str, provider: str) -> dict[str, Any]:
    """A single call served by a provider outside every
    pin (the void calibration's defect, scripted): the
    call delivers, but the unit's record carries the
    serving_mismatch flag (R7) — recorded, and not read
    as a result."""
    call = _answer_call(answer)
    call["provider"] = provider
    return call


def _truncated_call(answer: str) -> dict[str, Any]:
    """A single call that ended on ``length`` (the void
    calibration's defect, scripted): the call delivers,
    but the unit's record carries the truncated flag
    (R8) — recorded, and not read as a result."""
    return _answer_call(answer, finish_reason="length")


def _default_call(question_id: str) -> dict[str, Any]:
    """The dry run's default single call: the stand-in answer at the
    fixture's default token counts."""
    return _answer_call(_dry_run_answer(question_id))


def _pilot_dry_run_ids(batch: Tier4Batch) -> list[str]:
    """The question ids the pilot dry run names: the ids its
    failure-class exhibits key — when the batch's plan runs
    those units — plus the batch's F2 questions, so every
    family's treatments run, capped at the pilot's registered
    id limit. The pilot batch's own selection (its three
    exhibit-keyed F1 questions and its F2 question) is this
    rule's output, not a special case."""
    planned = {unit_key[0] for unit_key
               in calibration_plan(batch)}
    selected = [question_id for question_id
                in ("T4-02", "T4-03", "T4-04")
                if question_id in planned]
    for question_id in batch.f2_ids:
        if question_id not in selected:
            selected.append(question_id)
    return selected[:PILOT_ID_LIMIT]


def build_calibration_dry_run_script(
        batch: Tier4Batch | None = None
        ) -> tier3.DryRunScript:
    """The calibration dry run's script: the plan's units'
    defaults — every unit answers its stand-in answer through
    its arm's registered treatment — then the failure-class
    exhibits the command orders, one of each, each keyed to a
    unit the calibration's plan actually runs (a batch whose
    plan does not run the keyed unit — batch 2's, whose F2
    questions carry no exhibit — gets the defaults only):

    * a refusal (T4-03, 1, A): a serving that chose to answer
      nothing — its empty reply still bills the call;
    * a deadline (T4-04, 1, D): a call that outlasts the unit's
      shortened deadline, cancelled by the runner's wait_for before
      anything is booked;
    * a provider failure (T4-05, 1, D): a serving that consumed its
      budget and emitted nothing, after dispatch, booked the way the
      real client books a failed call;
    * a budget stop (T4-02, 1, D): one call booking just under the
      mode's authorization, which the unit's own per-unit ceiling
      refuses after the call — the sweep books the booked figure and
      the fit rule stops every unit after it;
    * a serving mismatch (T4-05, 1, A): a call the line served from
      outside the arm's pin — the void calibration's defect class,
      delivered and flagged serving_mismatch (R7), not read as a
      result;
    * a truncation (T4-06, 1, D-pages): a call that ended on
      ``length`` — the void calibration's other defect class,
      delivered and flagged truncated (R8), not read as a result.
    """
    batch = batch or load_batch()
    script = tier3.DryRunScript()
    planned = {tuple(unit_key)
               for unit_key in calibration_plan(batch)}
    for unit_key in planned:
        question_id = unit_key[0]
        script._calls[unit_key] = [
            _default_call(question_id)]
    # The failure-class exhibits, one each — only when the
    # batch's plan runs the unit they key.
    if ("T4-03", 1, "A") in planned:
        script._calls[("T4-03", 1, "A")] = [_answer_call("")]
    if ("T4-04", 1, "D") in planned:
        script._calls[("T4-04", 1, "D")] = [
            _answer_call(_dry_run_answer("T4-04"), sleep=0.25)]
        script._deadlines[("T4-04", 1, "D")] = 0.05
    if ("T4-05", 1, "D") in planned:
        script._calls[("T4-05", 1, "D")] = [
            _provider_failure_call(
                "scripted: the serving consumed its budget and "
                "emitted nothing")]
    if ("T4-02", 1, "D") in planned:
        script._calls[("T4-02", 1, "D")] = [
            _budget_stop_call(_dry_run_answer("T4-02"),
                              batch.calibration_ceiling)]
    if ("T4-05", 1, "A") in planned:
        # The mis-served provider is a bare name (the
        # form a response names a provider in), not a
        # dryrun/ serving id: the comparison normalizes
        # the pin's call-time qualifier away
        # (_base_provider), so a "dryrun/<anything>"
        # provider normalizes to the pinned provider
        # itself and would not exhibit the class.
        script._calls[("T4-05", 1, "A")] = [
            _unpinned_call(_dry_run_answer("T4-05"),
                           "Wafer")]
    if ("T4-06", 1, "D-pages") in planned:
        script._calls[("T4-06", 1, "D-pages")] = [
            _truncated_call(_dry_run_answer("T4-06"))]
    return script


def build_pilot_dry_run_script(
        batch: Tier4Batch | None = None
        ) -> tier3.DryRunScript:
    """The pilot dry run's script: every unit of the pilot's plan
    books a hair under its per-unit ceiling — the dry run exercises
    the sweep's fit rule at the batch's registered ceilings — then
    the failure-class exhibits, one of each, keyed to units the
    plan runs (a batch whose plan does not run the keyed unit gets
    the defaults only):

    * a deadline (T4-03, 1, A), a refusal (T4-02, 1, A) and a
      provider failure (T4-04, 1, D), each as the calibration's are;
    * a budget stop, composed: the ceiling-tail defaults exhaust the
      mode's authorization inside the plan, so the units after the
      crossing skip through the fit rule — the budget-stop class on
      the real rule, at the registered ceilings.
    """
    batch = batch or load_batch()
    script = tier3.DryRunScript()
    order, _refusals = pilot_plan(
        _pilot_dry_run_ids(batch), batch)
    planned = {tuple(unit_key) for unit_key in order}
    for unit_key in order:
        question_id, _repetition, arm = tuple(unit_key)
        if arm in ("A", "D", "D-pages"):
            script._calls[tuple(unit_key)] = [
                _ceiling_call(
                    batch.per_unit_ceilings[ceiling_key(arm)],
                    _dry_run_answer(question_id))]
        else:
            scenario_id = f"tier4_{arm.lower()}_{question_id}_r1"
            if arm == "F":
                script._arm_f[scenario_id] = _at_tier4_ceiling(
                    "F", _dry_run_answer(question_id), batch)
            else:
                script._arm_e[scenario_id] = _at_tier4_ceiling(
                    "E", _dry_run_answer(question_id), batch)
    # The failure-class exhibits, one each — only when the
    # batch's plan runs the unit they key.
    if ("T4-03", 1, "A") in planned:
        script._calls[("T4-03", 1, "A")] = [
            _answer_call(_dry_run_answer("T4-03"), sleep=0.25)]
        script._deadlines[("T4-03", 1, "A")] = 0.05
    if ("T4-02", 1, "A") in planned:
        script._calls[("T4-02", 1, "A")] = [_answer_call("")]
    if ("T4-04", 1, "D") in planned:
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
        batch: Tier4Batch | None = None,
        claim_dir: Path | None = None,
        results_path: Path | None = None,
        ) -> dict[str, Any]:
    """One mode's mocked dry run: the real runner, the mocked
    serving layer, the mode's own authorization pin (R4 — the pin
    names the mode's own registered ceiling), at zero spend.

    The dry run installs its own provider-order line (R7) — the
    pin lineup the mocked servings stand for — so the single-call
    arms' calls carry a provider order the way the owner's run
    does, and the preflight's pin case holds. The run's own pin
    context re-maps the line (idempotently) and restores it."""
    batch = batch or load_batch()
    servings = DRY_RUN_SERVINGS
    fingerprint = _servings_fingerprint(servings)
    authorization = (batch.calibration_ceiling
                     if mode == "calibration"
                     else batch.pilot_ceiling)
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
    suffix = (f"-{batch.name}" if batch.name != "pilot"
              else "")
    path = (Path(results_path) if results_path is not None
            else RESULTS_DIR / f"dryrun-tier4{suffix}-{mode}.jsonl")
    with _env_overrides(overrides), \
            _harness_pin_overrides(servings["E"]), \
            tier4_pins(DRY_RUN_PROVIDER_ORDER):
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
            deadline_overrides=deadline_overrides,
            batch=batch, claim_dir=claim_dir)


def _install_rates(catalogue: list[dict[str, Any]]) -> int:
    """The fixture's rates into the client's own pricing table (the
    tier-3 dry run's own installer, so the guard the dry run's calls
    pass through is the real one)."""
    return tier3._install_dry_run_rates(catalogue)


async def tier4_dry_run(
        batches: tuple[str | Path | None, ...] = (
                None, TIER4 / "batch2"),
        ) -> dict[str, Any]:
    """The mocked dry runs of both modes of every named batch
    (the command's acceptance criterion (f)) — the default pair
    is the pilot batch and batch 2 — through the real runner
    with mocked clients: no network, no spend.

    Every failure class the command names is included at least once
    per mode of a batch whose plan runs the unit it keys: a refusal,
    a deadline, a provider failure, and a budget stop (the
    calibration's booked by one call that takes the sweep to the
    authorization's edge; the pilot's composed by the ceiling-tail
    defaults exhausting the authorization inside the plan). A batch
    whose plan does not run the keyed units — batch 2's calibration
    plan is its two F2 questions — runs its units' defaults only.
    The reading sheet is generated for each mode of each batch from
    its own records, arm-blind, one entry per answered unit.
    """
    outcomes: dict[str, dict[str, Any]] = {}
    sheets: dict[str, dict[str, dict[str, Any]]] = {}
    for batch_path in batches:
        batch = load_batch(batch_path)
        calibration = await _tier4_dry_run_mode(
            "calibration",
            build_calibration_dry_run_script(batch),
            batch=batch)
        pilot = await _tier4_dry_run_mode(
            "pilot",
            build_pilot_dry_run_script(batch),
            question_ids=_pilot_dry_run_ids(batch),
            batch=batch)
        outcomes[batch.name] = {"calibration": calibration,
                                "pilot": pilot}
        for mode, result in (("calibration", calibration),
                             ("pilot", pilot)):
            suffix = (f"-{batch.name}"
                      if batch.name != "pilot" else "")
            sheet_path = RESULTS_DIR / (
                f"dryrun-tier4{suffix}-{mode}.sheet.json")
            sheets.setdefault(batch.name, {})[mode] = (
                export_tier4_reading_sheet(
                    result["records"], result["questions"],
                    sheet_path, result["seed"], mode))
    return {"batches": outcomes, "reading_sheets": sheets}


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
            help="the mode: calibration (every F1 question x "
                 "A and D, every F2 question x D-pages) or "
                 "pilot (the named question ids x their "
                 "family's arms)")
        command_p.add_argument(
            "--ids", default=None, metavar="IDS",
            help="pilot only: the comma-separated question ids from "
                 "the frozen batch (at most four)")
        command_p.add_argument(
            "--batch", default=None, metavar="DIR",
            help="the frozen batch's directory "
                 f"(default {DEFAULT_BATCH_DIR})")
        command_p.add_argument("--results-file", default=None,
                               metavar="PATH")
    worst_p = sub.add_parser(
        "worst-case",
        help="the per-arm worst-case tables at the fixture "
             "catalogue's shape (free)")
    worst_p.add_argument(
        "--batch", default=None, metavar="DIR",
        help="the frozen batch's directory "
             f"(default {DEFAULT_BATCH_DIR})")
    dry_p = sub.add_parser(
        "dry-run",
        help="the mocked dry runs of both modes of every "
             "named batch (free)")
    dry_p.add_argument(
        "--batch", default=None, metavar="DIR",
        help="one frozen batch's directory; unset, the pilot "
             "batch and batch 2")
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
        # The batch the records ran: the header's own
        # registration, so a reading sheet reads the batch's
        # questions, not the default batch's.
        batch_dir = header.get("batch_dir")
        batch = (load_batch(ROOT / batch_dir)
                 if batch_dir else load_batch())
        questions = candidate_index(batch)
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
        # catalogue's own rates. The figures are the batch's own
        # registrations.
        batch = load_batch(args.batch)
        catalogue = _dry_run_catalogue(DRY_RUN_SERVINGS)
        floor = prompt_floor(mode_arms("pilot", batch),
                             candidate_index(batch))
        print("arm A: one call — worst case per call and per unit "
              "are the same figure (a single-call arm)")
        index = _catalogue_index(catalogue)
        for arm in ("A", "D", "D-pages"):
            floor_message = max(
                (model_visible_message(arm, candidate, batch)
                 for candidate in candidate_index(batch).values()),
                key=lambda text: len(text.encode("utf-8")))
            worst = _single_call_worst_case(
                arm, floor_message, DRY_RUN_SERVINGS, index,
                batch.single_call_max_tokens)
            print(f"arm {arm}: one call, the largest message the "
                  f"batch carries — worst case ${worst:.4f} against "
                  f"the ${batch.per_unit_ceilings[ceiling_key(arm)]:.2f} "
                  f"per-unit ceiling (at the batch's registered "
                  f"max_tokens {batch.single_call_max_tokens})")
        print(f"arm F, at the tier-4 prompt floor and the "
              f"${batch.per_unit_ceilings['F']:.2f} "
              "per-unit ceiling:")
        _print_worst_case("F", tier3.arm_f_worst_case(
            DRY_RUN_SERVINGS, catalogue, prompt_floor=floor,
            unit_ceiling=batch.per_unit_ceilings["F"]),
            batch.per_unit_ceilings["F"])
        print(f"arm E, at the tier-4 prompt floor and the "
              f"${batch.per_unit_ceilings['E']:.2f} "
              "per-unit ceiling:")
        _print_worst_case("E", tier3.arm_e_worst_case(
            DRY_RUN_SERVINGS, catalogue, prompt_floor=floor,
            unit_ceiling=batch.per_unit_ceilings["E"]),
            batch.per_unit_ceilings["E"])
        return 0

    if args.command == "plan":
        mode, question_ids = _mode_and_ids(args)
        batch = load_batch(args.batch)
        order = (calibration_plan(batch) if mode == "calibration"
                 else pilot_plan(question_ids or [], batch)[0])
        print(f"the {mode}'s plan: {len(order)} units, seed "
              f"{(CALIBRATION_SEED if mode == 'calibration' else PILOT_SEED)}, "
              f"order sha256 {_order_digest(order)}")
        for unit_key in order:
            print(f"  {unit_key[0]} r{unit_key[1]} arm {unit_key[2]}")
        return 0

    if args.command == "dry-run":
        batches = ((args.batch,) if args.batch
                   else (None, TIER4 / "batch2"))
        result = await tier4_dry_run(batches=batches)
        for name, outcome in result["batches"].items():
            for mode in ("calibration", "pilot"):
                print(outcome[mode]["summary"])
                print(f"records: {outcome[mode]['path']}")
        return 0

    # preflight and run share the gate-and-preflight path, under
    # the provider pins in force (R7: the pin case and every
    # single-call arm's chat read the same line).
    mode, question_ids = _mode_and_ids(args)
    batch = load_batch(args.batch)
    tier3_settings = Tier3Settings()
    # The ratified arm pins live on the paid runners' own
    # OPENROUTER_PROVIDER_ORDER line, in .env.tier3 — not on
    # the ambient line the routing layer reads from .env, which
    # registers no tier3_arm_a/tier3_arm_d entries (measured
    # 2026-10-17: the live preflight refused arm D-pages on
    # exactly that gap, at zero spend). The mapping re-keys the
    # ratified line, so the pin case below and every single-call
    # arm's chat read the pins the owner ratified (R7); the
    # ambient export would shadow a settings read of the same
    # name, so the line is read from the file itself.
    with tier4_pins(_ratified_provider_order()):
        servings = _resolve_servings(tier3_settings)
        fingerprint = _servings_fingerprint(servings)
        authorization = (batch.calibration_ceiling
                         if mode == "calibration"
                         else batch.pilot_ceiling)
        print("servings map:")
        print(json.dumps(servings, indent=2, sort_keys=True))
        print(f"servings fingerprint: {fingerprint}\n")
        freeze = check_freeze(batch)
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
                    calibration_plan(batch) if mode == "calibration"
                    else pilot_plan(question_ids, batch)[0])}))),
            questions=(candidate_index(batch)
                       if mode == "calibration"
                       else {question_id: candidate
                             for question_id, candidate
                             in candidate_index(batch).items()
                             if question_id in set(question_ids)}),
            mode=mode, batch=batch)
        _print_preflight_findings(report)
        if report.refusals:
            return REFUSED_EXIT
        if args.command == "preflight":
            return 0
        result = await run_tier4_experiment(
            mode, question_ids=question_ids,
            results_path=args.results_file, batch=batch)
    print(result["summary"])
    print(f"records: {result['path']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_cli(argv))


if __name__ == "__main__":
    raise SystemExit(main())
