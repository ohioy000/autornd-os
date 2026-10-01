# Pre-registration — ARCH-20260930-098: which layer catches a missing real figure

Committed BEFORE any spend on this command. Three runs, one invocation, under
the owner's caps below. The paid step starts only after this commit, the
preflight gate, and the owner's authorisation, which is quoted below.

## Setup

- Branch `arch/20260930-098-d37-firing`, cut by the advisor at `8f6fdc6` on
  main `fe5b170`. The watchdog (D38, `5a05bdd`) and the preflight gate (096,
  `d1f4e3f`) are both on main.
- Scenario `evals/scenarios/convergence/conv_cup_line_sensor_regrounding.yaml`
  (committed at `768740d`): timeout 1800, `expect.max_calls` 40. Its request
  differs from `conv_cup_line_sensor` in exactly the two stated ways, read on
  the loaded strings: `'stranded copper (16.1 ohm per 1000 ft)'` becomes
  `'solid copper'`, and the `'If the PCB input type (NPN vs PNP) cannot be
  verified from the request, ...'` sentence is removed (1031 to 858
  characters).
- Corpus `docs/cupline/` and profile `profiles/cupline.yaml`, unchanged since
  094. `grep -rn '16\.1\|16\.14\|ohm' docs/cupline/` is empty: neither the
  request nor the corpus carries the resistance.
- No code, prompt, tier, pin or workflow change. The owner's current `.env`
  lineup, recorded by the results header.

## Run shape

```
AUTORND_PROFILE=cupline .venv/bin/python3 -m autornd.evals.cli \
  --scenarios evals/scenarios/convergence/conv_cup_line_sensor_regrounding.yaml \
  --workflow engineering-rnd --repeat 3 --timeout 1800 \
  --max-spend 0.50 --max-spend-sweep 1.20 \
  --results-file evals/results/098-d37-firing.jsonl
```

No `--skip-preflight`. The gate runs before any client exists, and its
findings land in the results header.

## Spend authorisation (the owner's, verbatim)

> i allow 1.20 envelope for first test

and, asked how to cap the runs inside it:

> .50 1.20 the runs dont usually go higher than 30 cents

So the caps are `--max-spend 0.50` per run and `--max-spend-sweep 1.20`, in
place of the command's proposed 0.60 and 1.80. **What the fit rule permits:**
a run starts only if spent-so-far + 0.50 <= 1.20 (`autornd/evals/runner.py`,
`SweepBudget.can_start`). Runs 1 and 2 always start. Run 3 starts if and
only if runs 1 and 2 together spent $0.70 or less. The CLI prints its static
warning ("permits at most 2 unit(s)", which is floor(1.20 / 0.50)) on
arrival. That is the worst case, not a prediction. If run 3 is skipped, it
is reported as a fit-rule skip with the two runs' spend, not as a sample.

A run that reaches its $0.50 cap ends `blocked` on the spend ceiling with a
runner `stop_reason`, and that counts against P5 as written. It is reported
as a spend stop, not as a watchdog failure.

## Answer key (the advisor's, verbatim)

(1) 24 VDC, identical everywhere; (2) 22 AWG, identical everywhere; (3) resistance 16.14 ohm/1000 ft (16.1 to 16.2 accepted) WITH ITS SOURCE STATED, and drop = 2 x 3 ft x R x 0.05 A, about 0.00484 V (0.00483 to 0.00486 accepted), arithmetic shown; (4) head voltage 23.995 V nominal and 22.795 V at the 22.8 V rail minimum, both passing 21.6 to 26.4 V; (5) NPN open-collector matching the CF-IO8 inputs, cited from the docs; (6) Keyence LV-N11N at $214.00, identical everywhere; (7) commissioning thresholds exactly as the docs state.

## Paths (the advisor's, verbatim, scored per run)

A, the first grounding catches it: the resistance enters the context through grounding's own lookup, rounds 0, one search call. B, D37 catches it: the plan names the resistance as a blocker, reground_context passes, reground_lookup runs once, and the second plan pass uses the finding: rounds 1, two search calls. Both are correct harness behaviour. Failures: C, no lookup anywhere and a resistance figure used without a source (a silent assumption, against D36 rule 2); D, D37 fires but the lookup returns nothing usable; E, a figure outside the accepted band reaches the last agreed implementation.

## Predictions (the advisor's, verbatim)

P1: triage is not low in any run (094 read high, 085 read medium), so D37 is eligible. P2: path A in at least 2 of 3 runs, because the grounding phase marks figures that set the answer as blocking, and wire resistance is one. P3: zero runs on path C. P4: the last agreed implementation in every run that reaches agreement scores all seven key items. P5: every run ends by its own terminal, with stop_reason None in all three. That makes it D38's first live reading too. P6: if path B occurs, the re-grounding lookup returns at least one finding and the second plan cites the resistance. Each repetition is a sample, not a confirmation (convention 27); report per run, never as a rate across differing criteria.

## Scoring sources (the advisor's, verbatim)

Which path comes from the written record: the regrounding block (serialised since 095), path (whether reground_lookup is present), calls_by_tier.search, and steps. Do not infer the path from prose.

The unit-record keys these name, as `ResultsLog.record` writes them:
`regrounding`, `regrounding_rounds`, `path`, `calls_by_tier`, `steps`,
plus `watchdog`, `status`, `stop_reason` and `iterations` for P4 and P5.
Key items 1 to 7 are scored against the implementation the watchdog
record's pointer names as last agreed, or, for a run that completes, the
final implementation.

## Executor's notes, before the run

- **The command's first verification is blind to one of the two
  differences.** `grep -A12 '^request:'` shows the request's first 12 lines,
  and the removed sentence sits on lines 13 to 15. It could never show the
  second difference. The full request block and the loaded strings both show
  exactly the two stated changes and nothing else.
- Run stdout and stderr go to the scratchpad during the run and are copied to
  `docs/traces/098-d37-firing-STDOUT.txt` and `-STDERR.txt` afterwards. The
  JSONL is copied from `evals/results/` (git-ignored, with its mirror outside
  the repo). No git operation while the run is in flight.
