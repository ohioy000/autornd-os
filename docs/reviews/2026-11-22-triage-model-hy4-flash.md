# The triage seat on a second model, with its thinking off and on (2026-11-22)

**Status.** Owner-directed in conversation, 2026-11-22. Nothing here is a ruling and nothing ships on it: a serving pin is
the owner's (G-2), and the tuned texts held by `docs/reviews/2026-11-21-per-profile-pins-and-tuned-prompts.md` stay held
until the owner rules. Pre-registered in `docs/preregistration-triage-model-hy4-flash.md` (with three amendments, each
committed alone before the spend it opens). Spent: '$0.6687' in all ('$0.4233' of the '$0.50' first read from the owner's permission, then '$0.2454' on the repeat of
Amendment 3), inside the '$1.00' given for sweeps ('$0.2251' on the first sweep; '$0.1062' of it left). Traces below, by sha256.

## The question

The first sweep read the tuned risk guides of `legal`, `finance` and `medical` under one triage model and found them
under-calling physical hazards (10, 24 and 18 of 180 units below a floor; control 0). One model cannot tell whether the
examples or the model cause that. The owner picked a second model, `tencent/hy4-flash`, from five candidates (newer, cheaper per token, typed
output, reasoning), and this run holds the examples and changes the model.

## What the model asks of the seat, as checked free first

Listed and priced ('$0.035' in, '$0.1405' out per million tokens); one provider, Tencent (fp8); typed output and
`max_tokens` accepted; 1,048,576 context; 65,536 output ceiling; reasoning supported. Not in `docs/MODELS.md` before this.

## What it costs and how long it takes, by setting (measured)

The model is a reasoning model. Triage sends no `reasoning` option, so its default applies (thinking on); a probe
wrapper (`docs/probes/triage_thinking_off_wrapper.py`, outside the harness, process only) sent `reasoning: {"enabled":
false}` for the thinking-off arms.

| | earlier model (the owner's triage model, sweep) | `hy4-flash`, thinking off | `hy4-flash`, thinking on (default) |
|---|---|---|---|
| completion tokens a call | about 530 | about 60 | 2,800 to 4,500 |
| seconds a unit | 2.6 | 2.2 to 2.4 | 17.6 to 25.1 |
| cost of a 180-unit arm | '$0.0304' to '$0.0344' | '$0.0031' to '$0.0036' | '$0.0718' to '$0.0907' (two arms cut at the cap) |

Thinking off is about a tenth of the earlier model's cost at the same speed. Thinking on is about 2 to 3 times its cost
and about 7 times slower, a wait of about 19 seconds on every run.

## Results, by the pre-registered rules

Reference, the earlier model: old text 0 units below a floor, 174 meeting the bounds. "Floor" is units below their
sector's `risk_at_least`; "bounds" is units meeting every bound. Margin 3, as in the first sweep.

| Text | earlier model | `hy4-flash`, thinking off | `hy4-flash`, thinking on |
|---|---|---|---|
| old guide (baseline of each column on this model) | 0 / 174 | **6 / 174: M2 fails** (limit 3) | **0 / 171: M2 holds**, at its limit |
| `general` | 0 / 169 | 0 / 175: M3 and M4 hold | 0 / 175: M3 and M4 hold |
| `finance` | 24 / 150 | **41 / 136: M3 fails** (limit 9) | 1 / 173: **M3 holds** (limit 3) |
| `medical` | 18 / 156 | **51 / 129: M3 fails** (limit 9) | **6 floor misses in 140 units run: M3 fails** (limit 3) |
| `legal` | 10 / 154 | **15 / 160: M3 fails** (limit 9) | 1 floor miss in 174 units run: M3 holds on what ran (limit 3) |

(The thinking-off limit is 9 because that column's baseline had 6; the thinking-on limit is 3 because its baseline had 0.)

**Two arms are partial, and why.** The thinking-on arms of `medical` and `legal` reached their per-arm cap of '$0.10', a
stop rule written in Amendment 2; I set the cap from a '$0.08' expectation and the two arms that think hardest cost
more. `medical` ran 140 of its 180 units ('$0.0907'; 8 recorded as skipped by the cap and 32 never started), `legal`
174 ('$0.0901'). Their other readings are real and stand as read; no arm was re-run. The medical failure cannot be reversed
by the missing units, which could only add misses. The legal pass is on the units that ran: the six missing units are
the last in suite order (two were recorded as skipped, on `wide_water_treatment` and `wide_wind_energy`), and could add
up to six misses in the worst case.

**M1 (the model holds the shape):** holds in all ten arms: no errors beyond the cap's skipped units, **zero rejected
replies and zero provider failures in the 1,760 units that ran**, every call served by the one provider.
**M2:** fails with thinking off, holds with thinking on. **M3:** fails for all three field texts with thinking off;
holds for `finance` and `legal` and fails for `medical` with thinking on. **M4:** holds in both settings.

**What the one medical failure is.** Five of its six floor misses are `wide_dentistry`, which the medical text reads
`medium` on all five repeats (the old text reads it `critical` on all five); the sixth is one `wide_marine` repeat. The
first sweep's C4 note allowed that a clinical profile may read a dentistry request lower and be right. **That is the
owner's reading to make:** the sector's expectation is a floor of `high` (`wide_marine`'s too), and the text reads below it.

**Movement (M5), thinking on, against T0:** `general` 5 of 36 sectors move in modal risk (2 of 29 stable ones differ),
`finance` 4 of 36 (0 of 29), `legal` 5 of 36 (0 of 26). Thinking off moved 7, 15 and 9 sectors, with `finance` reading
brewing, broadcast, dentistry and automotive as `low`. The full lists are reproducible from the traces with
`docs/probes/score_triage_hy4.py`. (Its `medical` list contains sectors with no reading because of the cap; those are
not movements.)

## The repeat (Amendment 3): 3 arms, thinking on, each complete

The owner asked for just 3 arms: the baseline, finance and legal, repeated with default thinking, each a full 180 units
(per-arm cap '$0.115', so none was cut). Spent '$0.2454' ('$0.0804', '$0.0687', '$0.0963'); about 56 to 66 minutes an arm;
**no rejected reply and no provider failure in the 540 units, every call on Tencent**.

| Arm | Units below a floor | Meets every bound | Rule |
|---|---|---|---|
| R0 (old guide, `general`) | 1 (`wide_dentistry`, `medium`) | 171 | **M2 holds** (at most 3 and at least 171: again exactly at the limit) |
| Rf (`finance`) | 1 (`wide_wind_energy`, `medium`) | 173 | **M3 holds** (limit R0's 1 plus 3 is 4) |
| Rl (`legal`) | 0 | 173 | **M3 holds** |

**The pre-registered test for "supported on this model".** A text is supported only if it holds M3 in the first run
and in this one, and the baseline holds M2 in both. Baseline: held in both (171 and 171 meeting the bounds; 0 and 1 below a
floor). `finance`: held in both (1 and 1 below a floor). `legal`: held in both (1 on the 174 units that ran, and 0 on a
complete arm). **So the finance and legal texts are supported on `hy4-flash` with its default thinking, and the baseline is
supported as a baseline.** Predictions: **P12** holds (even odds, and it sat on the limit again), **P13** holds twice,
**P14** holds (all complete, '$0.2454' under '$0.30').

**Movements (M5), against R0:** `finance` 3 of 36 sectors move in modal risk, with one unanimous change (semiconductor,
`high` to `medium` on all five repeats); `legal` 3 of 36 and none unanimous. Semiconductor reads `medium` under the
finance text in this run and in the thinking-off run, and under legal in neither; the owner may want to read it.

**What this does not say.** The baseline itself meets the bounds on 171 of 180 units on this model, against 174 on the
first model, so this model is no better than the first on the old text and is 3 units worse on the over-calling side
(`risk_at_most` misses 8 and 9). It is not shown to be a better triage model than the first, only a model on which two
texts that failed on the first read within the margin. Two runs per text, each of 180 units, a margin of 3. The medical
text was not repeated; it stays held.

## Predictions, scored

- **P1 (the probe), n = 4: holds.** Typed, no rejection, the pinned model, Tencent only, rated.
- **P2 (at most 2 errors an arm): holds** for all ten arms, apart from the units skipped by the cap.
- **P3 (M2 holds), n = 1: falsified with thinking off**, holds at the limit with thinking on.
- **P4 (M3 fails for the three field texts), n = 3: holds with thinking off; with thinking on it holds for `medical`
  and is falsified for `finance` and `legal`.**
- **P5 (M4), n = 1: holds** in both settings.
- **P6 (cost), n = 5: falsified for default thinking** ('$0.07' to '$0.09' an arm, '$0.405' for the five, against the
  '$0.012' an arm it predicted); replaced in Amendments 1 and 2. Thinking off then cost less than the replacement
  predicted ('$0.0031' to '$0.0036' an arm against under '$0.015').
- **P7 (thinking off does not make the model under-call by itself): falsified**, by M2.
- **P8 (thinking on is no worse than off in each arm), n = 5: holds** (0 against 6; 0 against 0; 1 against 41; 6 on
  140 units against 51; 1 on 174 units against 15). Written after seeing the thinking-off counts.
- **P9 (M2 on thinking on): holds**, at the limit (171).
- **P10 (the field texts stay above the margin on thinking on): falsified for two of three.** Written after seeing the
  thinking-off counts.
- **P11 (each arm under '$0.10', the five under '$0.45', under 80 minutes, M1 holds): holds for the five together
  ('$0.405'), the time (53 to 65 minutes an arm) and M1; falsified for two arms cut at the cap.**

## What this says, and what it does not

1. **The under-calling is not only the examples.** The same `finance` text under-calls badly with thinking off (41 units)
   and on the earlier model (24), and reads within the margin of its baseline when the model thinks (1). The same holds
   for `legal`. The examples are enough for a model that reasons through the guide's rules and not for one that answers
   straight away; both are model behaviour, and the seat's model and its thinking setting are part of what the text is
   measured on.
2. **`medical` is the exception that stays.** It under-calls dentistry with thinking on too. That one is the text, or the
   field's own reading of the sector (above), whichever the owner decides.
3. **`general` is not model-sensitive on these two models:** it holds M3 and M4 in both settings and the first sweep's
   miss (2 units, over-calls) was not repeated (0 floor misses, 175 meeting the bounds).
4. **Not shown:** that thinking on makes the triage better in any sense but these readings; anything about the answer
   tier; a repeat of any arm (each is one run of 180 units, and the first sweep's spread between identical arms was 2 to 3
   units); whether `hy4-flash` with its thinking on is acceptable for a seat that runs on every request at about 19 seconds
   a call (a latency decision for the owner).

## Options, and a recommendation (the owner's to take)

1. **Keep the owner's triage model; fix the three texts' examples** (the first record's option 2). No new model, no latency.
2. **Pin the triage tier of `finance` and `legal` to this model with its default thinking** (**now supported by two runs each**, above)
   (`PROFILE_MODELS=<profile>:triage=tencent/hy4-flash@tencent/fp8`, no harness change needed because thinking on is the
   model's default). This lets the two texts that passed ship on a model they were measured on, at about '$0.0004' a call
   and about 19 seconds a run, and leaves every other profile alone. `medical` stays held. A G-2 pin, proposed with this
   evidence, not made.
3. **Do both**, and read the medical dentistry readings by hand first.

My recommendation, after the repeat, is option 2 for `finance` and `legal`: the two texts passed twice on this model, and the
cost is about '$0.0004' a call and about 19 seconds a run under those two profiles only. The pin line would be
`PROFILE_MODELS=finance:triage=tencent/hy4-flash@tencent/fp8,legal:triage=tencent/hy4-flash@tencent/fp8`; it is a G-2 pin
and waits on the owner, as does the choice to accept 19 seconds on every run. In parallel, read the dentistry readings and
fix medical's examples (option 1 for that profile).

## Traces (sha256)

| File | sha256 |
|---|---|
| `triage-hy4-probe-on-1.jsonl` | `9b3691278a8e6eae467e79aa40fca41898f91c2ca039c0778e6bc3845db0e2f1` |
| `triage-hy4-probe-on-2.jsonl` | `f49e48dcba881a1d7d455c436a714e36c28261ebdc8b45bdd40d7186aac14a75` |
| `triage-hy4-probe-off.jsonl` | `57cadb4876692ce199808092bf2cf6bf6362531450440fcfc1e4a016c4a16f88` |
| `triage-hy4-off-H0.jsonl` | `b54737d1d095a20c709fd420ffc50f0a958d2bf88ea6bab26688ba261c296a8d` |
| `triage-hy4-off-Hg.jsonl` | `31f44ff76fa4f310b6b0b0bd233923489ed4bedb50cd5b38b5a99720823f46be` |
| `triage-hy4-off-Hf.jsonl` | `4b408223ddf2b66a7fad2ef8659bca1447f512f3deae4f00a8e23e24d7b5dac6` |
| `triage-hy4-off-Hm.jsonl` | `25c108a064c06b6e0b619e5b06e25c316ebb80e9f529d0aead875c478dc4c7ff` |
| `triage-hy4-off-Hl.jsonl` | `d2a01cac7610196e6b0fa889e73092cdeaf6159bf05010156ca00832d18f5856` |
| `triage-hy4-on-T0.jsonl` | `ede5bbb9b7d64c8f3581ffd26ef897a12261aadcacd52aa148dc320b736f5108` |
| `triage-hy4-on-Tg.jsonl` | `f03a47aa91cda692f37518ffb1e5d0d0bafcd953b00cce95b0bf48cbdca35d14` |
| `triage-hy4-on-Tf.jsonl` | `eb74b5b2fbdac0bb715b95f3a500bb95dbeae6986d8987c42c0fb6011c622dc2` |
| `triage-hy4-on-Tm.jsonl` | `319d5dded7a9c070764e336ca0e2316b20743828788dc8b2d0887cec689ef386` |
| `triage-hy4-on-Tl.jsonl` | `3bd0a088691e89550c4a390ac1669343dd62faf342715f2b4ecdb7a4d0fef281` |
| `triage-hy4-on-repeat-R0.jsonl` | `2d73b7bb2babc47514ca6c2e3d1c783e8b9767600db6560cb6d5cd65c64dc10e` |
| `triage-hy4-on-repeat-Rf.jsonl` | `f7fdf45b24a82f5645fe8d422300da028b2a4fd43442ecd3678ed62f5f37ebb7` |
| `triage-hy4-on-repeat-Rl.jsonl` | `339a508e4d3ff496512086055cf409bd4accb287a915e554a855131c3957f0fc` |

The wrapper, `docs/probes/triage_thinking_off_wrapper.py`: `10904e36a001e3dcb76301aad093516da644e266197f1f49a840d3d8225508fe`.
The first probe call's caps were set wrong by me (a unit reserves its cap against the sweep cap), so it ran one of three
units; the other two ran as `probe-on-2` ('$0.0003' of the study's spend is the first, '$0.0010' the second).

## Found, not touched

- **The thinking-on arms' per-arm cap was mine and too low for the slowest two.** Noted above; the cost of a complete
  `medical` arm is about '$0.11'.
- **The control worktree runs the older code**, so its unit records carry no `models_by_function`; the header and the
  provider record carry the model instead (H0 and T0).
- **No harness setting sends `reasoning: {"enabled": false}` for triage.** Adopting thinking off for the seat would need
  one and a ruling of its own; it would also need a measurement of the readings it costs (here, 6 floor misses on the old
  text where thinking on has 0).
- **The ledger of servings counts a unit by its header's tiers**, as the first record notes.
