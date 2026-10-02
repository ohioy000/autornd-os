# Pre-registration — ARCH-20261002-106: the golden set re-run on arm B

Committed BEFORE any spend. Branch `arch/20261002-106-golden-rerun`, from
main `504b576` (104 and 105 merged: D42, the figure parser, the spend
guard, D43). The scenarios' timeouts are twice each time target (`29b015a`);
the pass rule stays `keys.json`'s time_target_s.

## Predictions and decision rule (the advisor's, verbatim)

P1, at least 5 of 6 golden questions PASS. P2, Q2, Q3 and Q6 each ship, the questions 102 lost to the apparatus and to scope. P3, Q1, Q4 and Q5 still pass. P4, no run's spend exceeds its cap (104's guard). P5, the median sprawl ratio (answer characters to model-answer characters) falls below 10 (D43). P6, every shipped answer is within its time target. P7 (side test), the IA run ships with all six core items. DECISION RULE: 5 or 6 passes lifts D41's freeze; the next work is the owner's standing lineup and ceilings (G-2, G-3) and the fast-path design. 3 or 4 passes means each failure is diagnosed by question, with no new arm. Fewer than 3 means a redesign of the default path.

## Spend authorisation (the owner's, verbatim)

> raise the caps to 50 cent a piece

> keep watch for new merge then act i command .50 cent per instance

> do all those things without my input

So: the golden sweep `--max-spend 0.50 --max-spend-sweep 3.00` (exactly
six runs fit the fit rule), then the IA side test `--max-spend 0.50
--max-spend-sweep 0.50`. Total at most $3.50. Both with `--skip-preflight`,
the override recorded, as in 102/103 (the gate's false refusals of these
pins are unrepaired under D41 and disputed by the live record).

## The 104 warning for the arm B prefix and the owner's current ceilings

```
worst-case single call (completion side, max_tokens x rate): triage $0.0014, research $0.0410, search $0.0160, architecture $0.0936, engineering $0.1498, judge $0.1344, escalation $0.3200
```

The ceilings in force: plan 78000, judge 70000, escalation 32000, validate
16000, search 16000. The command's formula (the largest worst case, $0.32,
plus $0.09) gives $0.41 per run. The owner's $0.50 is above it, so the
guard refuses no first call on any tier.

## Run shape

- Arm B as an environment prefix only: the identical 09-26 models and
  pins, with MODEL_JUDGE empty.
- The requests are byte-identical to `keys.json`.
- Detached (`setsid nohup`) and sequential: the golden sweep, then the IA
  side test. No git operation during a run.
