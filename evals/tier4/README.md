# Tier-4 capacity test: the frozen batches

**Status: runnable (ARCH-20261017-122, Ruling D52, with the runner fixes of
the advisor's 2026-10-17 review — rulings R7, R8 and R9 — landed before any
further paid tier-4 unit). The runner is built and proved by a mocked dry run
of both modes of both frozen batches at zero spend; every acceptance criterion
of the command is demonstrated by `tests/test_tier4_runner.py`. Execution
stops at the owner's gate: no paid unit may start until `TIER3_SPEND_AUTHORIZED`
in `.env.tier3` equals the mode's registered ceiling ($2.00 calibration on the
pilot batch, $1.00 calibration on batch 2, $5.00 pilot on either batch). The
calibration and the pilot each wait for the owner's gate after this branch
merges.**

This directory holds the tier-4 runner (`evals/tier4/runner.py`) and
the interface to the frozen batches (`evals/tier4/pilot/` and
`evals/tier4/batch2/`, both frozen under D44 and never edited) and
their corpora. Tier 4 is the capacity test (D52,
`docs/reviews/2026-10-16-tier4-the-capacity-test.md`): can the harness answer
hard engineering questions under the two ways the world can be arranged —
**everything given but hard** (family F1), or **the data lives in a fictional
corpus profile** (family F2)? The measure is two blind hand readings per
answered unit against the question's requirement statements (D50); the
requirement checker is deliberately **not** built here — it starts at the first
growth step (D52 §3), and a harness defect found in a dry run is a STOP-and-report,
not a fix.

## The frozen batches

Every frozen batch registers itself in its own `manifest.json` (R9): the
candidates file's path and sha256, each question's corpus pages with the
sha256 over the listed pages concatenated in the listed order, the families,
the calibration and pilot ceilings, the per-unit ceilings, the deadline and
the single-call max_tokens. The runner reads every one of those figures from
the manifest — no batch's plan, ceilings, deadline or caps is a constant in
the runner — and every subcommand takes `--batch DIR` to select the batch
(the default is the pilot batch).

**The pilot batch** — five questions, frozen under D44 in
`evals/tier4/pilot/candidates.json`
(sha256 `9c9109826431778bd203eddfe0ba12887b53434f33e3d656f4bb589cd216b634`,
registered in `evals/tier4/pilot/manifest.json`, written in the same format
every batch uses). T4-01 was dropped at evidence time (its own reference
design gives v_act = 4.20 m/s against the stated 0.42 m/s — infeasible,
0 of 6100 designs; `evals/tier4/pilot/verify.py` is the frozen check and
its output is the registration). The runner runs T4-02..T4-06:

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

**Batch 2** — two questions, both F2, frozen under D44 by the owner's
instruction to merge PR #188: T4-15 and T4-16, each with one corpus page
(registered in `evals/tier4/batch2/manifest.json`, candidates sha256
`d49afe00c5980691204a5327c88fec1c77243ae1e615fc2a095822a8599eab67`).
Its calibration is exactly its two D-pages units, registered ceiling $1.00.

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
F2 unit of arms F and E runs with the profile set programmatically for the
unit (and nothing else), so its pipeline's grounding node loads the corpus
pages. **Every F2 unit grounds with its own question's pages and no other
question's** (R9): a question whose frozen pages are the tier-4 profile's
own corpus pages — the pilot batch's T4-06 — runs under the shipped `tier4`
profile, so its grounding is byte-identical to the pre-manifest runner's;
any other F2 question (batch 2's T4-15 and T4-16) runs under a per-question
profile whose scratch manifest lists that question's frozen pages and nothing
else. An F1 unit of every arm runs under the default profile, so no corpus
text can reach an F1 question — and arm A does not run on F2 at all.

**Arm D on F2 (D-pages)** is the pages-in-the-prompt treatment: its user
message is the request, the registered separator `\n\nReference documents:\n\n`,
and **its own question's** corpus pages verbatim and in the manifest's listed
order, each preceded by its file name (the pilot batch's T4-06: 7172 bytes,
sha256
`c2186c6045877759761dec3318e8c230469f56039a9e6bc54efb61ecacab1f09`; R9:
D-pages carries its own question's pages, and no other question's — batch 2's
D-pages units carry T4-15's and T4-16's own single pages). The
system prompt is arm D's own (`evals/tier3/prompts/arm_d.md`), unchanged. D-pages
exists so the pilot can separate *finding* the data (arm D on F1 has nothing
to find; arm F/E must retrieve it) from *using* it (D-pages is handed it).

## The modes

| mode | units | registered ceiling | seed |
|---|---|---|---|
| calibration | the batch's own plan: every F1 question × A and D, every F2 question × D-pages, one repetition each — the pilot batch plans 9 (A on T4-02..T4-05, D on T4-02..T4-05, D-pages on T4-06), batch 2 plans 2 (D-pages on T4-15 and T4-16) | $2.00 pilot batch, $1.00 batch 2 | 20261017 |
| pilot | the named question ids (at most 4, from the frozen batch only) × their family's arms × 1 repetition; the pilot batch's four ids are T4-02, T4-03, T4-04, T4-06 → 15 units, batch 2's two ids are T4-15 and T4-16 → 6 units | $5.00 | 20261018 |

The order is the seeded interleaved order — `random.Random(seed).shuffle` over
the enumerated units, no arm runs as a block — and the order's sha256 digest is
recorded in the results header (calibration
`b808c0ed711ae0f27c459a4f51c0787bd1f1969de46d585821f86bbf75f4837d`, pilot
`d1176aa0d44eb2b47e880738017d0c01d8d3d6c2a163e3fa05d66e60486a77a5`).
The resume guard reconstructs it: a results file whose recorded plan differs
from the mode's current plan refuses to continue.

Per-unit ceilings, the deadline and the single-call max_tokens are the
batch's own registrations (R9), read from its manifest — not constants in
the runner: **A $0.15, D (and D-pages) $0.40, F $0.40, E $1.50; 3600
seconds per unit; single-call max_tokens 32768 for the single-call arms
(R8)** — the cap the pipeline's implement call already has, so a long
answer is not cut off at 8000 tokens and counted a result. A unit whose
answer ends on `length` is recorded `truncated`, flagged on the reading
sheet and not read as a result. If a measured worst case exceeds an arm's
ceiling, the preflight refuses the mode and reports the figure — the
ceiling is not raised.

## The provider pins (R7)

The single-call arms (A, D, D-pages) run on the owner's ratified
provider pins: the `tier3_arm_a` and `tier3_arm_d` entries of
`OPENROUTER_PROVIDER_ORDER`, re-keyed to the `tier4_arm_a` and
`tier4_arm_d` functions the arms' calls bill to. The void calibration's
defect was precisely that the tier-4 functions matched no key of the
owner's line and fell to its general list — arm A was served by Google
and every arm-D call by Wafer (mxfp4, $24/M), neither a ratified pin
(both void runs, $1.08, are committed to `docs/traces/`). The mapping
copies the ratification onto the tier-4 functions rather than asking for
a second one — the single-call arms are the same workloads on the same
servings — and a line that already carries the tier-4 entries is
re-mapped, so the mapping is idempotent. A tier3 entry with no provider
maps to an explicitly empty tier-4 entry: unpinned, and refused by the
preflight — an absent key would fall to the general list again.

Every unit records the provider that served each call
(`providers_by_tier`). A unit of a single-call arm served outside its
pin is recorded `serving_mismatch`: kept in the record, flagged on the
reading sheet, and not read as a result. The preflight prints each
single-call arm's pin ("arm A: pinned to …") and each pipeline arm's
per-tier provider order, and refuses to start an arm with no pin.

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

Both modes refuse to start unless the batch and the corpus on disk hash to
the values the batch's manifest registers (R9): the candidates file's
sha256, and each question's corpus — the sha256 over its listed pages
concatenated in the listed order. A one-byte change to the candidates
file or to any corpus page refuses, naming the question and the pages.
For a question the tier-4 profile mirrors, every page the `tier4`
profile's manifest lists in `docs/tier4/` must also stay byte-identical
to the frozen page it copies.

## The ratification gates (R4) and the preflight

The gate is the tier-3 one, reused: `TIER3_SERVINGS_RATIFIED` must equal the
servings map's fingerprint, and `TIER3_SPEND_AUTHORIZED` in `.env.tier3` must
equal **the mode's registered ceiling exactly** — the ceiling the batch's
manifest registers: $2.00 for the calibration on the pilot batch, $1.00 for
the calibration on batch 2, $5.00 for the pilot on either. An authorization
above the ceiling would spend past a plan the owner never ratified; one
below it stops the sweep mid-plan. The pins are unchanged (servings
fingerprint `e0dc92a3aecb` under the owner's standing lines); a different
map is refused.

The preflight is free (the catalogue fixture or the free GET, the credit GET,
arithmetic). It prints each arm's per-call and per-unit worst case at the
catalogue's shape — the single-call arms (A, D, D-pages) at the largest
message the mode carries and the batch's registered max_tokens, arms F and E
per standing tier with the workflow's own call counts (arm F: 2 triage +
3 research + 1 search + 2 engineering + 2 judge; arm E: the pipeline's own) —
prints each single-call arm's provider pin and each pipeline arm's per-tier
provider order (R7), and refuses the mode when any serving is unpriced or
absent, any call refuses even at zero spend, a single-call arm has no pin,
or the provider's remaining credit is below the mode's ceiling. A balance
that could not be read is no evidence: a paid run that cannot establish its
balance does not start.

## The records and the reading sheet

The results log is the tier-3 one (`Tier3ResultsLog`, append-only JSONL,
resume-safe): a header carrying the batch sha256, the corpus sha256, the mode,
the order digest and the servings fingerprint, then one record per unit
carrying the question id, family, arm, the profile the unit ran under, the
exact user message's sha256, and the tier-3 unit fields (status, answer,
candidate, iterations, reason, stop_reason, calls, cost, seconds) plus the
provider that served each call (`providers_by_tier`). Failure
treatment is registered, not improvised: a refusal, a deadline, a provider
failure and a budget stop each keep their own status class, and the census
counts them. Two defect classes carry their own flags (R7, R8): a unit
whose answer ended on `length` is recorded `truncated`, and a unit of a
single-call arm served outside its pin is recorded `serving_mismatch` —
both kept in the record and counted, and both excluded from the units a
reading may draw on.

The reading sheet is exported per mode, **arm-blind**: one entry per answered
unit, listing the question's requirement statements for the reader — the
request, the requirements, the answer, and the two reading slots — with no arm
label anywhere, and a `truncated` or `serving_mismatch` flag on any unit
that carries one, so a flagged answer is never silently read as a result.
The pilot is read by the advisor alone (D52 §5); the sheet is
still arm-blind, so the reading cannot follow the arm.

## The mocked dry run (the proof, at zero spend)

`python3 evals/tier4/runner.py dry-run` runs both modes of both batches
through the real runner with mocked clients — no network, no spend — and
includes every failure class the command names, at least once per mode: a
refusal, a deadline, a provider failure and a budget stop, plus the void
calibration's two defect classes scripted as exhibits: a single-call unit
served outside its pin (recorded `serving_mismatch`, R7) and a single-call
unit whose answer ends on `length` (recorded `truncated`, R8). Measured on
the fixture catalogue's rates: the pilot batch's calibration books $1.9990 of
$2.00 (its budget stop is one call that books $1.998 against the sweep,
admitted by the pre-call guard and refused by the unit's own ceiling — the
remaining units fail the fit rule); its pilot books $4.7456 of $5.00 (its
ceiling-tail defaults exhaust the authorization inside the plan); batch 2's
calibration books $0.0007 of $1.00 and its pilot $4.5954 of $5.00. The dry
run's records carry every field, and the reading sheet is generated from
them, arm-blind. A harness defect found in the dry run is a STOP-and-report,
not a fix.

## The CLI

```bash
python3 evals/tier4/runner.py plan calibration            # the pilot batch's 9 units and the digest
python3 evals/tier4/runner.py plan calibration --batch evals/tier4/batch2   # batch 2's 2 units and the digest
python3 evals/tier4/runner.py plan pilot --ids T4-02,T4-03,T4-04,T4-06
python3 evals/tier4/runner.py worst-case                  # the per-arm worst-case tables
python3 evals/tier4/runner.py preflight calibration       # freeze, gates, preflight (free)
python3 evals/tier4/runner.py dry-run                     # the mocked runs of both modes, both batches
python3 evals/tier4/runner.py reading-sheet RESULTS_FILE  # the arm-blind sheet
python3 evals/tier4/runner.py run pilot --ids T4-02,T4-03,T4-04,T4-06   # paid: waits on the gates
```

Every subcommand takes `--batch DIR` (the default is the pilot batch).

`run` is the only paid path, and it passes the same gates and the same
preflight first. A refusal exits 3.

## What tier 4 does not do

It does not score. The tier-2 scorer has no keys for tier-4 questions, and
tier 4's primary measure is the hand readings (D50: a scorer verdict is never
the result). The runner's summary reports the census — statuses, spend,
liability, seconds — and nothing about correctness. The requirement checker
that would machine-grade the requirement statements is the first growth step
(D52 §3), deliberately out of this command's scope.
