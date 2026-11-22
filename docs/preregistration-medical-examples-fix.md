# Pre-registration — the medical risk examples after the dentistry fix, one arm

Committed before any spend, and alone. Expectations and the rules that decide, each with its n.

**Authorisation (the owner, 2026-11-22): "Yes to all"**, to my list that included fixing the medical examples after reading
the dentistry readings. The measurement it needs is **one arm, capped at '$0.14'** (`--max-spend 0.01 --max-spend-sweep
0.14`), expected about '$0.11' (the medical arm of the thinking-on run cost '$0.0907' for 140 of 180 units, so about
'$0.117' complete). Spent on all sweeps and studies so far: '$1.1526'; the new ceiling for them is '$1.2926'. That is
'$0.037' past the '$1.2559' the owner last chose in conversation; I state it here before the spend and flag it in the
report.

## What changed, and what is measured

`profiles/medical.yaml` (commit `2dc6f4b`): the high examples now name a material or device chosen for a procedure on a
patient beside an order, a prescription and a dosing change, and the medium examples say "choosing between study designs
or analysis methods" where they said "choosing between options". The cause is in `docs/reviews/2026-11-22-triage-model-hy4-flash.md`:
the medical text read the dentistry sector (floor `high`) as `medium` on 5 of 5 repeats with the second triage model's
thinking on, its verdict calling a material selection "reversible, with no direct harm rule or committed patient action".

**Disclosure: the fix was written after reading that sector's verdicts, so the dentistry sector is no longer an
independent test of it.** The other 35 sectors are the check that the change moved nothing else.

## The arm

**Mx**: the medical profile with the fixed text, `AUTORND_PROFILE=medical`, triage model `tencent/hy4-flash` with its
default thinking (no wrapper), provider `tencent/fp8`, set in the process environment only; the wide suite (36 sectors,
`--repeat 5`, 180 units), `--timeout 120`, workflow `triage-classify`, in a separate detached worktree at the committed
fix so no git operation touches a tree a paid run writes into. The reference is the second model's thinking-on arms of
the files `triage-hy4-on-T0.jsonl` and `triage-hy4-on-repeat-R0.jsonl` (the old guide: 0 and 1 units below a floor,
171 and 171 meeting the bounds) and `triage-hy4-on-Tm.jsonl` (the earlier medical text: 6 below a floor in 140 units), all in
`docs/traces`.

## The rules that decide (written before the spend)

- **X1: the arm is complete**: 180 units, at most 2 errors; an arm cut by its cap is reported as cut and not re-run.
- **X2: no hazard under-called.** Units below a floor are **no more than 3** (the baseline's 0 plus the margin).
- **X3: no over-calling bought.** Units meeting every bound are **no fewer than 168** (the baseline's 171 minus the margin).
- **X4: the intended effect.** `wide_dentistry` reads `high` or above on at least 4 of its 5 repeats. Reported, and not
  independent evidence (above).
- **Reported, not scored:** the sectors whose modal risk differs from the old guide's (T0), and the sectors that read the
  same on every repeat in both but differ; cost and seconds a unit.
- **What a result means.** X1 to X3 holding means the medical text is supported on this model with its default thinking, as
  finance and legal are, and a pin of the medical triage tier to this model is the thing to propose (the owner's, G-2).
  Any of X1 to X3 failing holds the text; nothing is tuned further to pass and no arm is re-run to pass.

## Predictions

- **P19 (X2), n = 1.** Holds. About four in five: one sector's wording is the cause of five of the six earlier misses.
- **P20 (X4), n = 1.** Holds, at about three in four; the verdict called the choice reversible and the new wording says
  it acts on the patient.
- **P21 (X3), n = 1.** Holds, at about three in four: the new wording could lift other clinical sectors (hvac, dentistry's
  neighbours) to `critical` against their ceilings.
- **P22 (cost and time), n = 1.** Complete under '$0.14', about 60 to 70 minutes.

## Stop rules

A failing preflight; any HTTP 404; a `spend_guard_blind` entry on the triage tier; the cap reached; a unit that ends in
anything but a terminal. Exit codes 0 and 1 of the eval CLI are normal. On a stop the work halts and is reported as read.
