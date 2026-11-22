# Pre-registration — the tuned risk guide under seven arms (the prompt sweep)

Committed before any spend, and alone. Expectations and the rules that decide, each with its n.

**Authorisation (the owner, 2026-11-21): up to $1.00 in total, for this sweep and nothing else** (separate from the
'$3.00' of the pin smoke). Seven arms, each capped at '$0.12', so the hard ceiling is '$0.84'. The expected cost is about
'$0.30' (below).

## What is tested, and what is not

The triage risk guide's worked examples and the hazard sentence are now profile words, so a profile teaches with its
field's examples and `general` with examples from several fields, where every profile used one field's, physical
engineering. The rules around the examples are the same text for every profile. The project's standing claim is that **the
risk axis is profile-invariant** (`docs/handover-review.md` B2: of the 23 wide-suite sectors that read the same on every
repeat in both arms, none changed risk under another profile). This sweep asks whether that holds, and whether the new
text under-calls a hazard, on the same instrument.

Covered: the risk guide and the triage the wide suite scores. **Not covered**, by design: the decision switches' questions,
the citation phrases and the escalation prompt (free tests pin them; no model reading of them is bought here).

## The instrument

The wide suite: 36 sectors (`evals/scenarios/wide`), workflow `triage-classify` (one triage call per unit, nothing else),
`--repeat 5`, `--timeout 45`: 180 units an arm. The earlier two arms (`docs/traces/b14-wide-control.jsonl`,
`b14-wide-studio.jsonl`, `--repeat 3`) read `risk_at_least` failures on 3 and 1 of 108 units with the same text, so the
**spread between two arms of identical text is about 2 units in 108**; five repeats are taken here to narrow it, and the
margin below is that spread scaled to 180 units. The triage model is the owner's global one (not the one of those arms), so
the counts are compared only inside this sweep.

## The arms

| # | Arm | Text | `AUTORND_PROFILE` | Tree |
|---|---|---|---|---|
| 0 | `control` | main at 828d033: the guide as it was (engineering examples) | `general` | `/home/jb/autornd-os-wt-control` |
| 1 | `general` | this branch | `general` | `/home/jb/autornd-os-wt-pins` |
| 2 | `studio` | this branch | `studio` | same |
| 3 | `legal` | this branch | `legal` | same |
| 4 | `finance` | this branch | `finance` | same |
| 5 | `medical` | this branch | `medical` | same |
| 6 | `science` | this branch | `science` | same |

Each arm, from its tree, with `PYTHONPATH` its tree, no `PROFILE_MODELS`, the owner's `.env` (shared, via symlink, never
printed), and `OPENROUTER_PROVIDER_ORDER` passed in the process environment with the stale architecture entry left out (the
same run-scoped step as the pin smoke, and for the same reason: preflight fails on the owner's order, `triage-classify`
never calls that tier, `.env` is not edited, `--skip-preflight` is not used):

```
OPENROUTER_PROVIDER_ORDER="triage:crusoe/bf16,engineering:deepinfra/fp8,escalation:google-vertex/global,search:Perplexity,research:wafer/us,ranker:Fireworks,judge:deepinfra/fp8,premium:,recompute:Anthropic" \
AUTORND_PROFILE=<arm's profile> \
/home/jb/autornd-os/.venv/bin/python3 -m autornd.evals.cli --scenarios evals/scenarios/wide \
  --workflow triage-classify --repeat 5 --timeout 45 \
  --max-spend 0.05 --max-spend-sweep 0.12 \
  --results-file evals/results/sweep-<arm>.jsonl
```

Order: control, then the branch arms 1 to 6. **Stop rules:** a failing preflight, a cap reached, a non-zero exit, or
fewer than 180 unit records in an arm: stop, report as read, spend no more. Results are copied byte-identical into
`docs/traces/` and cited by sha256; no git operation touches a tree while an arm writes.

**Cost.** The two recorded arms cost '$0.0300' and '$0.0297' for 108 units (a mean of '$0.00028' a unit); the pin smoke
read '$0.00023' a triage call on today's model. At '$0.00028' a unit 180 units are '$0.05' an arm, seven arms '$0.35'.

## What is scored

From each unit record: the `risk_at_least` and `risk_at_most` assertions, `status`, `unrecallable`, and the triage verdict's
`risk`. **Not scored, reported only:** `specialists_include` (13 sectors name `test_engineer`, an engineering role a
profile that is not engineering does not have), and domains and rosters. A scorer verdict is a screen, not the result.

## The rules that decide (written before the spend)

**C1 — under-calling a hazard, the failure that matters.** For each branch arm, the units below their sector's
`risk_at_least` floor are **no more than the control's count plus 3** (the 2-in-108 spread above, scaled to 180 and
rounded up). An arm above that **holds that profile's tuned text**.

**C2 — `general` is not worse than before.** The units meeting every risk bound (`risk_at_least` and `risk_at_most`) in the
branch `general` arm are **no fewer than the control's minus 3**. Below that **holds the tuned text of `general`**.

**C3 — every movement is listed.** For each branch arm, every sector whose **modal risk** (over its 5 repeats) differs from
the control's is listed with both readings. Reported, not scored.

**C4 — the invariance claim, sharpened.** Of the sectors that read the same on all 5 repeats in both the control and an arm,
the number whose risk differs. Predicted **0**, as it was 0 of 23. A non-zero count is **reported as a finding**
(B2: a profile that moves a risk reading is a finding, not a feature) and is not by itself a hold: a clinical profile
reading a dentistry sector higher than the engineering examples did may be right, and the owner reads it.

**What "hold" means.** The tuned text of that profile is not shipped as measured: this branch is not merged on the strength
of it, and the owner is told which arm failed and by how many units. Nothing is tuned further to pass, and no arm is re-run
to pass; a re-run is a new pre-registration.

## Predictions

- **P1 (C1), n = 6 arms.** Every branch arm is within the margin of the control. The advisor's expectation is that it holds
  with room, because the rules around the examples are unchanged and each passage carries the rule it is spliced into.
- **P2 (C2), n = 1.** `general` holds.
- **P3 (C4), n = 6 arms.** 0 for each.
- **P4 (instrument).** Each arm has 180 unit records, none refused, none timed out beyond 2 of 180 (the recorded arms had
  none).

## Not predicted, and not claimed

Anything about the switches, the lookup or the escalation; the quality of any triage beyond the risk and the unrecallable
reading; a comparison with another triage model; or the profiles' rosters. Every arm is one draw of 5 repeats per sector.

## After

The seven results are scored in `docs/reviews/2026-11-21-per-profile-pins-and-tuned-prompts.md` with each rule applied as
written above. If a rule holds a profile's text, the README says only what survived, and the owner is told first.
