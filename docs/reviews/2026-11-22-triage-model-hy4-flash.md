# The triage seat on a second model, with its thinking off and on (2026-11-22)

**Status.** Owner-directed in conversation, 2026-11-22. Nothing here is a ruling and nothing ships on it: a serving pin is
the owner's (G-2), and the tuned texts held by `docs/reviews/2026-11-21-per-profile-pins-and-tuned-prompts.md` stay held
until the owner rules. Pre-registered in `docs/preregistration-triage-model-hy4-flash.md` (with four amendments, each
committed alone before the spend it opens). Spent on this study: '$0.9275' ('$0.4233' of the '$0.50' first read from the owner's permission, '$0.2454' on the repeat of
Amendment 3, '$0.2567' and '$0.0021' on the high-effort test of Amendment 4); with the first sweep's '$0.2251', '$1.1526' on all
sweeps, which is past the '$1.00' they were given by the amount the owner chose in conversation (about '$0.20' more). Traces below, by sha256.

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

**Better, and at what.** (Corrected after the owner's question; the first wording said "not shown to be better", which
understated it.) On the three field texts this model, thinking on, has far fewer units below a floor than the first
model: finance 24 against 1 and 1, legal 10 against 1 and 0, medical 18 against 6 (in 140 units run). A difference of 20 or more
units is far outside the 2 to 3 unit spread two arms of identical text showed, so it is not luck, and it came twice. It is
not the code: no prompt, profile, workflow or graph file differs between the tree the first sweep ran on and the tree
these arms ran on (only the knowledge and PDF files that came in with the merge of main), and the baseline arms ran in the
same unchanged control worktree both times. **The only things that changed are the model and how much it thinks**, and
the thinking-off arms (41, 51 and 15 units below a floor) show that thinking is what carries it. For this harness that is the
property that matters: the risk axis must not move with the profile's text, and this model on this seat moves less than
the first when the text is weaker.

**Where it is not better.** On the old guide, the same text both models were given, the first model has 0 units below a
floor and 174 meeting the bounds, this one 0 and 1 below a floor and 171 (twice, exactly at the limit); it over-calls
a little more (`risk_at_most` misses 8 and 9 against 6). So it is not a better reader of the guide the project was
calibrated on, and it costs 2 to 3 times as much and takes about 7 times as long. Two runs per text, each of 180 units, a
margin of 3. The medical text was not repeated; it stays held. The question this left open, whether the first model would
hold the texts if it thought as much, was then tested (next section), and the answer changes the reading above: **the
amount of thinking is not the whole of it.**

## The first model at high reasoning effort (Amendment 4)

The owner chose to test it: the first model (the owner's global triage model, through Crusoe), the old guide, finance and legal,
**high** reasoning effort sent by a wrapper outside the harness (`docs/probes/triage_effort_wrapper.py`), 180 units an arm,
three lanes at once. A three-unit probe first ('$0.0021'): medium effort, which is its default, matched the sweep (493 to 587
tokens), high spent 1,621 to 2,289 tokens and 5.7 to 8.3 seconds a call. Spent on the three arms '$0.2567' ('$0.0789',
'$0.0879', '$0.0899'), about 30 to 32 minutes an arm, 10 seconds a unit, about 1,630 to 1,830 completion tokens a unit.

| Arm, high effort | Units that ran | Units below a floor | Meets every bound | Rule |
|---|---|---|---|---|
| E0 (old guide, `general`) | 175 | 0 | 171 | E1 fails: 5 errors |
| Ef (`finance`) | 174 | **9** (aquaculture 5, veterinary 2, geotechnical 1, textiles 1) | 148 | E1 fails: 6 errors; E3 would fail |
| El (`legal`) | 180 | **8** (aquaculture 4, printing 3, pulp and paper 1) | 139 | E1 holds; **E3 fails** (limit 3) |

**The errors are the provider's, not the model's.** All 11 are HTTP 429, "temporarily rate-limited upstream", after the
client's retries (about 31 seconds a unit): E0 lost brewing, cold chain, hvac, legal ops and space; Ef lost broadcast, cold
chain, rail signalling, semiconductor, space and textiles. No rejected reply and no provider failure otherwise. Cause: I
ran three lanes at once against the one provider; the five lanes of the second model on its provider had none. The
pre-registration says an arm with more than 2 errors is not scored by its other rules, and it is not re-run. **Read as
the rule allows, and no further:** E0's 0 below a floor is on 175 units, so its limit for E3 is 3, or at most 8 if all 5
lost units had been misses, which at default effort 0 of 180 were; `finance`'s 9 can only grow with its 6 lost units, so it
fails whatever they read; `legal` is complete and has 8, which fails a limit of 3 and, with an implausible worst-case
baseline of 5, would sit exactly at the limit of 8.

**What it says.** At high effort the first model spends about as many tokens as the second model does thinking, and it
still does not read the field texts within the margin: finance 9 (24 at default effort, 1 and 1 on the second model),
legal 8 (10 at default, 1 and 0 on the second). The aquaculture and printing sectors, which both texts under-call, stay
under-called. Effort moved finance from 24 to 9 and legal hardly at all. **So the amount of thinking is not what separates
the two models: the second model reads these texts better at the same thinking.** It also over-calls far more at high effort
under the field texts (`legal` misses its ceiling on 33 units against 9 for the baseline at the same effort and 6 at default), so `legal` meets the bounds on
139 units where the second model meets them on 173. Cost: at high effort the first model costs '$0.079' to '$0.090' an arm,
the same as the second model with thinking on ('$0.069' to '$0.096'), and 10 seconds a unit against 17 to 22, so what the first
model keeps over the second is speed, not cost.

**Predictions (written after the probe's tokens, before any arm's counts):** P15 (E0 holds E2) **holds on the 175 units that
ran** (0 below a floor, 171 meeting the bounds); P16 (Ef holds E3) **falsified**; P17 (El holds E3) **falsified**; P18 (each
arm under '$0.12', the three under '$0.33', under 40 minutes) **holds**.

**Not shown:** that a still higher effort, a different provider or another reasoning setting would not close the gap; the
first model was read at the one effort the owner's setting offers above its default. Whether the second model's advantage is
its size, its training or the way its thinking is used is not separable from these arms.

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
   for `legal`. The examples are enough for the second model when it thinks and not when it answers straight away, and
   **not for the first model even at high effort** (finance 9, legal 8): both thinking and which model are part of what the
   text is measured on, and more thinking alone did not close the gap.
2. **`medical` was the exception, and the fixed text holds.** The earlier text under-called dentistry with thinking on; after
   the examples were fixed (the section above) the arm holds X1 to X3 at one run, with dentistry read `high` 5 of 5 (not
   independent evidence of the fix).
3. **`general` is not model-sensitive on these two models:** it holds M3 and M4 in both settings and the first sweep's
   miss (2 units, over-calls) was not repeated (0 floor misses, 175 meeting the bounds).
4. **Not shown:** that thinking on makes the triage better in any sense but these readings; anything about the answer
   tier; a repeat of any arm (each is one run of 180 units, and the first sweep's spread between identical arms was 2 to 3
   units); whether `hy4-flash` with its thinking on is acceptable for a seat that runs on every request at about 19 seconds
   a call (a latency decision for the owner).

## The medical text after the dentistry fix (the medical-fix pre-registration, one arm)

The owner's "Yes to all" (2026-11-22) covered fixing the medical examples after the dentistry readings were read. The fix
(commit `2dc6f4b`) names a material or device chosen for a procedure on a patient beside an order, a prescription and a
dosing change in the high examples, and says "choosing between study designs or analysis methods" in the medium ones.
One arm, `medical` text, the second model with its default thinking, 180 units, set in the process environment only
(`docs/preregistration-medical-examples-fix.md`, committed before the spend). Disclosure, as written there: the fix was
written after reading that sector's verdicts, so dentistry is **not** independent evidence of it; the other 35 sectors are
the check that nothing else moved.

| Rule | Read | |
|---|---|---|
| X1, complete, at most 2 errors | 180 units, 0 errors | holds |
| X2, units below a floor, at most 3 | **2** (both `wide_semiconductor`, read `low`) | holds |
| X3, units meeting every bound, at least 168 | **173** | holds |
| X4, `wide_dentistry` high or above on at least 4 of 5 | **5 of 5** `high` | holds (reported, not independent) |

Reference: the old guide on this model, thinking on, had 0 and 1 units below a floor and 171 and 171 meeting the bounds
(T0 and R0); the earlier medical text had 6 floor misses in the 140 units it ran (Tm). One provider (Tencent), no blind
entries, '$0.1176', 26.6 seconds a unit (4,779 s for the arm; the line-up smoke's run A shared the machine for 98 s of it).

**Where the readings moved against the old guide's modal reading** (reported, not scored): `wide_broadcast` medium to low,
`wide_data_engineering` medium to high, `wide_dentistry` critical to high, `wide_marine` critical to high,
`wide_veterinary` high to critical, `wide_wind_energy` critical to high, and `wide_semiconductor` high to a split (medium 2,
low 2, high 1), which is where the 2 floor misses are. Three sectors moved down from `critical` to `high` and two moved up;
each is inside its own bounds, since X3 holds, and none is read as better or worse. The semiconductor split is the one thing
here that is not stable; it is a sector the earlier medical text did not read low, so it is the cost of this wording to
watch on a repeat, not a rule failure.

**Predictions scored.** P19 (X2) **holds**, P20 (X4) **holds**, P21 (X3) **holds**, P22 (cost and time) **half falsified**: the
arm is complete under '$0.14' ('$0.1176') and took 80 minutes, not the 60 to 70 predicted.

**What it means by the rules written beforehand:** the medical text is supported on this model with its default thinking, as
finance and legal are, at one run. A pin of the medical triage tier to `tencent/hy4-flash` is **the thing to propose, and the
owner's to ratify (G-2); it is not made**. The medical arm is one run, where finance and legal have two each.

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
| `medical-fix-Mx.jsonl` | `5e4af2a0b6d61295914b575bca7baea6b96b284a0e71e2f645782e69d22b1c4b` |
| `triage-oss-probe-medium.jsonl` | `91d06551db6a5c2c03942facc2477f2c209983c4ca6cea16d79e2c547298af4c` |
| `triage-oss-probe-high.jsonl` | `76c3b70a79e135c62710adb58b8f39040aecba0ba2e605f519f4b558d942e437` |
| `triage-oss-high-E0.jsonl` | `21dda3f59ffb9e1d2bfaaa5a471e67d62a89763cd5b9c0de16f10715146b6d4c` |
| `triage-oss-high-Ef.jsonl` | `fe6418fa1c492333c2fce171d9557068a611eab6f915afc989833d5237924735` |
| `triage-oss-high-El.jsonl` | `78de6b0148b8900b24ee81bf86502d0ce69f942fbdf090943ffd72f3da7150b2` |

The effort wrapper, `docs/probes/triage_effort_wrapper.py`: `5b313d26d2a57a5e03cb4effbaf2d9ebcf2972b3cba3d676ff1509aa3ec463f1`.
The wrapper, `docs/probes/triage_thinking_off_wrapper.py`: `10904e36a001e3dcb76301aad093516da644e266197f1f49a840d3d8225508fe`.
The first probe call's caps were set wrong by me (a unit reserves its cap against the sweep cap), so it ran one of three
units; the other two ran as `probe-on-2` ('$0.0003' of the study's spend is the first, '$0.0010' the second).

## Found, not touched

- **Three lanes at once on one provider drew upstream 429s** (11 of 540 units, the first model through Crusoe); five lanes on the
  second model's provider drew none. The client retries for about 31 seconds and then ends the unit as blocked.

- **The thinking-on arms' per-arm cap was mine and too low for the slowest two.** Noted above; the cost of a complete
  `medical` arm is about '$0.11'.
- **The control worktree runs the older code**, so its unit records carry no `models_by_function`; the header and the
  provider record carry the model instead (H0 and T0).
- **No harness setting sends `reasoning: {"enabled": false}` for triage.** Adopting thinking off for the seat would need
  one and a ruling of its own; it would also need a measurement of the readings it costs (here, 6 floor misses on the old
  text where thinking on has 0).
- **The ledger of servings counts a unit by its header's tiers**, as the first record notes.
- **The owner's global answer model is blind to the spend guard, and now says so in a live run** (run A of the model line-up smoke,
  `docs/traces/lineup-smoke-A.jsonl`, sha256 `3ba6e7f030fa89777c3a59f78a7d2ae954f38754644a7358902aea533e134ca8`). The catalogue
  entry for `deepseek/deepseek-v4.1-flash-1017` carries an `overrides` list (a price by day and UTC hour, up to twice the base
  rate); `_prices_what_the_guard_cannot_bound` reads any component it does not know as unboundable, so the engineering tier
  runs with the guard blind (`spend_guard_blind` names it), as the recompute tier does for the same reason (a
  `min_prompt_tokens` override). Every engineering run on that model is affected, not only the smoke. The fix would be to
  bound a call by the highest price across the overrides; it changes how the cost guard counts, so it is the owner's ruling and
  is **not made**. The call itself cost '$0.0019'.
