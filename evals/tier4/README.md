# Tier-4 capacity test: the frozen pilot batch

**Status: runnable (ARCH-20261017-122, Ruling D52). The runner is built and
proved by a mocked dry run of both modes at zero spend; every acceptance
criterion of the command is demonstrated by `tests/test_tier4_runner.py`.
Execution stops at the owner's gate: no paid unit may start until
`TIER3_SPEND_AUTHORIZED` in `.env.tier3` equals the mode's registered ceiling
($2.00 calibration, $5.00 pilot). The calibration and the pilot each wait for
the owner's gate after this branch merges.**

This directory holds the tier-4 runner (`evals/tier4/runner.py`), the
interface to the frozen pilot batch (`evals/tier4/pilot/`, frozen under D44
and never edited) and its corpus. Tier 4 is the capacity test (D52,
`docs/reviews/2026-10-16-tier4-the-capacity-test.md`): can the harness answer
hard engineering questions under the two ways the world can be arranged —
**everything given but hard** (family F1), or **the data lives in a fictional
corpus profile** (family F2)? The measure is two blind hand readings per
answered unit against the question's requirement statements (D50); the
requirement checker is deliberately **not** built here — it starts at the first
growth step (D52 §3), and a harness defect found in a dry run is a STOP-and-report,
not a fix.

## The frozen batch

Five questions, frozen under D44 in `evals/tier4/pilot/candidates.json`
(sha256 `9c9109826431778bd203eddfe0ba12887b53434f33e3d656f4bb589cd216b634`).
T4-01 was dropped at evidence time (its own reference design gives
v_act = 4.20 m/s against the stated 0.42 m/s — infeasible, 0 of 6100
designs; `evals/tier4/pilot/verify.py` is the frozen check and its output is
the registration). The runner runs T4-02..T4-06:

| id | family | domain | requirements |
|---|---|---|---|
| T4-02 | F1 | electrical | 6 |
| T4-03 | F1 | fluid | 5 |
| T4-04 | F1 | thermal | 5 |
| T4-05 | F1 | structural | 5 |
| T4-06 | F2 | fluid | 6 |

Each candidate carries `request`, `requirements` (id, statement, check,
tolerance), `reference_design`, `worked_solution`, `wrong_designs` and
`difficulty_rationale`. **Only the `request` is ever model-visible.** The
rest is the reading sheet's and the grader's material.

## The two families

**F1 — everything given but hard.** The unit's user message is the request
alone. No corpus, no profile: an F1 unit runs under the default profile, so
its grounding grounds on nothing (the default `docs/manifest.json` carries an
empty global list). The difficulty is in the question, not in finding data.

**F2 — the data lives in a fictional corpus profile.** T4-06's request names
a fictional vendor's products (Vortexia Fluidics) whose specifications exist
only in the corpus: three pages in `evals/tier4/pilot/corpus/`
(sha256 `1d27d491195edec184141ba3f8882c27ab509fa3bb7551f7404055fe9f78f1d9`,
concatenated in name order), byte-identical copies of which live in
`docs/tier4/` under the `tier4` profile (`profiles/tier4.yaml` →
`get_docs_dir() == "tier4"` → `docs/tier4/manifest.json`'s global list). An
F2 unit of arms F and E runs with `AUTORND_PROFILE=tier4` set programmatically
for the unit (and nothing else), so its pipeline's grounding node loads the
corpus pages. An F1 unit of every arm runs without it, so no corpus text can
reach an F1 question — and arm A does not run on F2 at all.

**Arm D on F2 (D-pages)** is the pages-in-the-prompt treatment: its user
message is the request, the registered separator `\n\nReference documents:\n\n`,
and the three corpus pages verbatim and in name order, each preceded by its
file name (7172 bytes, sha256
`c2186c6045877759761dec3318e8c230469f56039a9e6bc54efb61ecacab1f09`). The
system prompt is arm D's own (`evals/tier3/prompts/arm_d.md`), unchanged. D-pages
exists so the pilot can separate *finding* the data (arm D on F1 has nothing
to find; arm F/E must retrieve it) from *using* it (D-pages is handed it).

## The modes

| mode | units | registered ceiling | seed |
|---|---|---|---|
| calibration | 9: A on T4-02..T4-05, D on T4-02..T4-05, D-pages on T4-06, one repetition each | $2.00 | 20261017 |
| pilot | the named question ids (at most 4, from the frozen batch only) × their family's arms × 1 repetition; the pilot's four ids are T4-02, T4-03, T4-04, T4-06 → 15 units | $5.00 | 20261018 |

The order is the seeded interleaved order — `random.Random(seed).shuffle` over
the enumerated units, no arm runs as a block — and the order's sha256 digest is
recorded in the results header (calibration
`b808c0ed711ae0f27c459a4f51c0787bd1f1969de46d585821f86bbf75f4837d`, pilot
`d1176aa0d44eb2b47e880738017d0c01d8d3d6c2a163e3fa05d66e60486a77a5`).
The resume guard reconstructs it: a results file whose recorded plan differs
from the mode's current plan refuses to continue.

Per-unit ceilings and the deadline, registered: **A $0.10, D (and D-pages)
$0.30, F $0.40, E $1.50; 3600 seconds per unit.** If a measured worst case
exceeds an arm's ceiling, the preflight refuses the mode and reports the
figure — the ceiling is not raised.

## The leakage guard

Before any unit runs, the runner checks the model-visible text of **every
unit of both modes**: no requirement statement, no reference-design value, no
worked-solution or difficulty-rationale sentence, and no wrong-design value or
reason may occur in a unit's user message — unless the string also occurs in
the unit's *given* texts (the request always; the corpus pages for a D-pages
unit, whose fictional product vocabulary is the F2 given world). A string that
occurs in the message and in none of the given texts is a leak, and the mode
refuses to start naming it. The break-proof test appends the requirements to a
message and watches the guard flag them.

## The freeze guard

Both modes refuse to start unless the batch and the corpus on disk hash to the
registered sha256 values above, and `docs/tier4/` is byte-identical to
`evals/tier4/pilot/corpus/`. A one-byte change to `candidates.json`, to a
corpus page, or to a `docs/tier4/` copy refuses, naming the file.

## The ratification gates (R4) and the preflight

The gate is the tier-3 one, reused: `TIER3_SERVINGS_RATIFIED` must equal the
servings map's fingerprint, and `TIER3_SPEND_AUTHORIZED` in `.env.tier3` must
equal **the mode's registered ceiling exactly** — $2.00 for the calibration,
$5.00 for the pilot. An authorization above the ceiling would spend past a
plan the owner never ratified; one below it stops the sweep mid-plan. The
pins are unchanged (servings fingerprint `e0dc92a3aecb` under the owner's
standing lines); a different map is refused.

The preflight is free (the catalogue fixture or the free GET, the credit GET,
arithmetic). It prints each arm's per-call and per-unit worst case at the
catalogue's shape — the single-call arms (A, D, D-pages) at the largest
message the mode carries, arms F and E per standing tier with the workflow's
own call counts (arm F: 2 triage + 3 research + 1 search + 2 engineering +
2 judge; arm E: the pipeline's own) — and refuses the mode when any serving
is unpriced or absent, any call refuses even at zero spend, or the provider's
remaining credit is below the mode's ceiling. A balance that could not be read
is no evidence: a paid run that cannot establish its balance does not start.

## The records and the reading sheet

The results log is the tier-3 one (`Tier3ResultsLog`, append-only JSONL,
resume-safe): a header carrying the batch sha256, the corpus sha256, the mode,
the order digest and the servings fingerprint, then one record per unit
carrying the question id, family, arm, the profile the unit ran under, the
exact user message's sha256, and the tier-3 unit fields (status, answer,
candidate, iterations, reason, stop_reason, calls, cost, seconds). Failure
treatment is registered, not improvised: a refusal, a deadline, a provider
failure and a budget stop each keep their own status class, and the census
counts them.

The reading sheet is exported per mode, **arm-blind**: one entry per answered
unit, listing the question's requirement statements for the reader — the
request, the requirements, the answer, and the two reading slots — with no arm
label anywhere. The pilot is read by the advisor alone (D52 §5); the sheet is
still arm-blind, so the reading cannot follow the arm.

## The mocked dry run (the proof, at zero spend)

`python3 evals/tier4/runner.py dry-run` runs both modes through the real
runner with mocked clients — no network, no spend — and includes every
failure class the command names, at least once per mode: a refusal, a
deadline, a provider failure and a budget stop. Measured on the fixture
catalogue's rates: the calibration books $1.9990 of $2.00 (its budget stop is
one call that books $1.998 against the sweep, admitted by the pre-call guard
and refused by the unit's own ceiling — the remaining units fail the fit rule);
the pilot books $4.8954 of $5.00 (its ceiling-tail defaults exhaust the
authorization inside the plan). The dry run's records carry every field, and
the reading sheet is generated from them, arm-blind. A harness defect found in
the dry run is a STOP-and-report, not a fix.

## The CLI

```bash
python3 evals/tier4/runner.py plan calibration            # the 9 units and the digest
python3 evals/tier4/runner.py plan pilot --ids T4-02,T4-03,T4-04,T4-06
python3 evals/tier4/runner.py worst-case                  # the per-arm worst-case tables
python3 evals/tier4/runner.py preflight calibration       # freeze, gates, preflight (free)
python3 evals/tier4/runner.py dry-run                     # the mocked runs of both modes
python3 evals/tier4/runner.py reading-sheet RESULTS_FILE  # the arm-blind sheet
python3 evals/tier4/runner.py run pilot --ids T4-02,T4-03,T4-04,T4-06   # paid: waits on the gates
```

`run` is the only paid path, and it passes the same gates and the same
preflight first. A refusal exits 3.

## What tier 4 does not do

It does not score. The tier-2 scorer has no keys for tier-4 questions, and
tier 4's primary measure is the hand readings (D50: a scorer verdict is never
the result). The runner's summary reports the census — statuses, spend,
liability, seconds — and nothing about correctness. The requirement checker
that would machine-grade the requirement statements is the first growth step
(D52 §3), deliberately out of this command's scope.
